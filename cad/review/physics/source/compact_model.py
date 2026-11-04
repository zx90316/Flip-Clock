"""Bounded planar simplification of CAD collision profiles for usable dynamics.

Retains holes and concavity, validates Hausdorff distance of all boundaries.
No complete-gear convex hulls, no collision exclusions, no joint constraints.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union


def partition(reference,tolerance_mm=.005):
    simplified=reference.simplify(tolerance_mm,preserve_topology=True)
    error=reference.boundary.hausdorff_distance(simplified.boundary)
    if error>tolerance_mm+1e-7:raise ValueError("Boundary simplification exceeds tolerance")
    old_holes=sum(len(p.interiors) for p in ([reference] if reference.geom_type=="Polygon" else reference.geoms))
    new_holes=sum(len(p.interiors) for p in ([simplified] if simplified.geom_type=="Polygon" else simplified.geoms))
    if old_holes!=new_holes:raise ValueError("Simplification changed hole topology")
    triangles=shapely.constrained_delaunay_triangles(simplified)
    vertices=[];lookup={};polygons={}
    for triangle in triangles.geoms:
        coords=np.array(triangle.exterior.coords[:-1]);cross=np.linalg.det(np.array([coords[1]-coords[0],coords[2]-coords[0]]))
        if cross<0:coords=coords[::-1]
        ids=[]
        for v in coords:
            key=tuple(np.round(v,9))
            if key not in lookup:lookup[key]=len(vertices);vertices.append(key)
            ids.append(lookup[key])
        polygons[len(polygons)]=ids
    def convex(ids):
        xy=np.asarray([vertices[i] for i in ids]);dd=np.roll(xy,-1,axis=0)-xy
        cross=dd[:,0]*np.roll(dd,-1,axis=0)[:,1]-dd[:,1]*np.roll(dd,-1,axis=0)[:,0]
        return bool(np.all(cross>=-1e-10))
    for _ in range(60):
        edges=defaultdict(list)
        for pid,ids in polygons.items():
            for a,b in zip(ids,ids[1:]+ids[:1]):edges[tuple(sorted((a,b)))].append(pid)
        changes=0
        for edge,owners in sorted(edges.items()):
            if len(owners)!=2 or any(i not in polygons for i in owners):continue
            ia,ib=owners;a,b=polygons[ia],polygons[ib]
            j=next((j for j in range(len(a)) if {a[j],a[(j+1)%len(a)]}==set(edge)),None)
            if j is None:continue
            va,vb=a[j],a[(j+1)%len(a)]
            k=next((k for k in range(len(b)) if b[k]==vb and b[(k+1)%len(b)]==va),None)
            if k is None:continue
            aa=a[j+1:]+a[:j+1];bb=b[k+1:]+b[:k+1];merged=aa+bb[1:-1]
            if len(merged)>96 or len(set(merged))!=len(merged) or not convex(merged):continue
            polygons[ia]=merged;del polygons[ib];changes+=1
        if not changes:break
    regions=[Polygon([vertices[i] for i in ids]).convex_hull for ids in polygons.values()]
    union=unary_union(regions)
    difference=simplified.symmetric_difference(union).area
    if difference>max(1e-7,simplified.area*1e-8):raise ValueError("Convex merge changes simplified outline")
    report={"original_area_mm2":reference.area,"simplified_area_mm2":simplified.area,"boundary_hausdorff_mm":error,
        "simplification_tolerance_mm":tolerance_mm,"symmetric_difference_mm2":reference.symmetric_difference(union).area,
        "simplified_union_error_mm2":difference,"holes_retained":old_holes,"triangles":len(triangles.geoms),"regions":len(regions)}
    return [np.array(p.exterior.coords[:-1]) for p in regions],report


def compact_model(directory,tolerance_mm=.005):
    directory=Path(directory);manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("collision_compaction",{}).get("schema")==1:
        print("Collision model already compacted",flush=True);return
    source=(directory/"model.xml").read_bytes();tree=ET.ElementTree(ET.fromstring(source));root=tree.getroot();assets=root.find("asset")
    by_name={e.get("name"):e for e in assets.findall("mesh")}
    geom_elements={e.get("name"):e for e in root.findall(".//geom")}
    bodies={e.get("name"):e for e in root.findall(".//body")}
    groups=defaultdict(list)
    for row in manifest["collision_geoms"]:
        if row["representation"]=="native_CAD_convex_prism":groups[(row["body"],row["profile"])].append(row)
    reports={};replacement=[]
    for (body,profile),rows in groups.items():
        polygons=[];axial=[]
        for row in rows:
            geom=geom_elements[row["geom"]];mesh=by_name[geom.get("mesh")]
            vertices=np.fromstring(mesh.get("vertex"),sep=" ").reshape(-1,3)*1000
            axial.extend(vertices[:,0].tolist());polygons.append(Polygon(vertices[:len(vertices)//2,1:]))
        reference=unary_union(polygons);regions,report=partition(reference,tolerance_mm)
        key=body+"/"+profile;report["original_regions"]=len(rows);reports[key]=report
        low,high=min(axial),max(axial)
        for row in rows:
            geom=geom_elements[row["geom"]];mesh=by_name[geom.get("mesh")];bodies[body].remove(geom);assets.remove(mesh)
        for i,poly in enumerate(regions):
            vertices=np.array([(x,y,z) for x in (low,high) for y,z in poly])*.001
            name="compact_"+body+"_"+profile+"_"+str(i)
            ET.SubElement(assets,"mesh",name=name,vertex=" ".join(f"{v:.12g}" for v in vertices.reshape(-1)),maxhullvert="-1")
            ET.SubElement(bodies[body],"geom",name="c_"+name,type="mesh",mesh=name,group="3",rgba="0 0 0 0")
            replacement.append({"geom":"c_"+name,"body":body,"representation":"native_CAD_bounded_convex_prism","profile":profile})
        print(json.dumps({"profile":key,"old":len(rows),"new":len(regions),"boundary_error_mm":report["boundary_hausdorff_mm"]}),flush=True)
    ET.indent(root,space="  ");tree.write(directory/"model.xml",encoding="utf-8",xml_declaration=True)
    manifest["collision_geoms"]=[r for r in manifest["collision_geoms"] if r["representation"]!="native_CAD_convex_prism"]+replacement
    manifest["xml_sha256"]=hashlib.sha256((directory/"model.xml").read_bytes()).hexdigest()
    manifest["collision_compaction"]={"schema":1,"native_decomposition_xml_sha256":hashlib.sha256(source).hexdigest(),"tolerance_mm":tolerance_mm,"reports":reports,
        "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"shapely":shapely.__version__}
    manifest["assumptions"].append(f"Working CAD outlines use .005 mm native tessellation plus <= {tolerance_mm} mm measured planar simplification; holes preserved.")
    (directory/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")


if __name__=="__main__":compact_model(Path(sys.argv[1]))
