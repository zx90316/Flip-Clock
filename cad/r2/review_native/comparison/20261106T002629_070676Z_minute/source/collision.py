"""CAD-face tessellation to exact convex prisms. Concave voids stay empty."""
from __future__ import annotations
import math
from pathlib import Path
import sys
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from cadgen import build123d as bd


def convex_regions(face,tolerance_mm=.005,max_vertices=24):
    faces=list(face.faces())
    vertices=[];triangles=[];lookup={}
    for native in faces:
        vv,tt=native.tessellate(tolerance_mm,.08)
        mapping=[]
        for v in vv:
            key=(round(v.X,8),round(v.Y,8))
            if key not in lookup:lookup[key]=len(vertices);vertices.append(key)
            mapping.append(lookup[key])
        for a,b,c in tt:
            ids=[mapping[a],mapping[b],mapping[c]]
            xy=np.array([vertices[i] for i in ids])
            u,v=xy[1]-xy[0],xy[2]-xy[0]
            area=float(u[0]*v[1]-u[1]*v[0])
            if abs(area)<1e-14:continue
            if area<0:ids.reverse()
            triangles.append(ids)
    polygons={i:p for i,p in enumerate(triangles)}
    def convex(poly):
        xy=np.asarray([vertices[i] for i in poly]);d=np.roll(xy,-1,axis=0)-xy
        cross=d[:,0]*np.roll(d,-1,axis=0)[:,1]-d[:,1]*np.roll(d,-1,axis=0)[:,0]
        return bool(np.all(cross>=-1e-9))
    # Rebuild adjacency per pass; deterministic greedy coarsening preserves all boundaries.
    for _ in range(20):
        edges={}
        for pid,poly in polygons.items():
            for j,a in enumerate(poly):edges.setdefault(tuple(sorted((a,poly[(j+1)%len(poly)]))),[]).append(pid)
        changes=0
        for edge,owners in sorted(edges.items()):
            if len(owners)!=2 or any(pid not in polygons for pid in owners):continue
            ia,ib=owners;a,b=polygons[ia],polygons[ib]
            shared=None
            for j,va in enumerate(a):
                vb=a[(j+1)%len(a)]
                if {va,vb}==set(edge):shared=(j,va,vb);break
            if shared is None:continue
            j,va,vb=shared
            try:k=next(k for k in range(len(b)) if b[k]==vb and b[(k+1)%len(b)]==va)
            except StopIteration:continue
            aa=a[j+1:]+a[:j+1]
            bb=b[k+1:]+b[:k+1]
            merged=aa+bb[1:-1]
            if len(merged)>max_vertices or len(set(merged))!=len(merged) or not convex(merged):continue
            polygons[ia]=merged;del polygons[ib];changes+=1
        if not changes:break
    regions=[np.array([vertices[i] for i in ids],dtype=float) for ids in polygons.values()]
    triangle_area=sum(Polygon([vertices[i] for i in ids]).area for ids in triangles)
    area=sum(Polygon(poly).area for poly in regions)
    if abs(area-triangle_area)>max(1e-7,triangle_area*1e-8):raise ValueError("Convex merge changed section area")
    reference=unary_union([Polygon([vertices[i] for i in ids]) for ids in triangles])
    hulls=[Polygon(poly).convex_hull for poly in regions]
    union=unary_union(hulls)
    difference=reference.symmetric_difference(union).area
    if difference>max(1e-7,triangle_area*1e-8):raise ValueError("Convex decomposition filled a void or removed material")
    regions=[np.asarray(poly.exterior.coords[:-1]) for poly in hulls]
    return regions,{"native_area_mm2":sum(f.area for f in faces),"triangulated_area_mm2":triangle_area,
                    "convex_area_mm2":area,"symmetric_difference_mm2":difference,
                    "triangles":len(triangles),"regions":len(regions),"chord_tolerance_mm":tolerance_mm,
                    "hull_union_hausdorff_mm":reference.hausdorff_distance(union)}


def prism_vertices(poly,height_mm,z_mm=0):
    return np.array([(x,y,z) for z in (z_mm-height_mm/2,z_mm+height_mm/2) for x,y in poly],dtype=float)


def probe():
    import geometry as g
    profile=g.gear_profile(40,1.8,.22)-g.ratchet_cavity(36,1)
    regions,report=convex_regions(profile)
    print(report,flush=True)
    print("vertices",min(map(len,regions)),max(map(len,regions)),flush=True)


if __name__=="__main__":probe()
