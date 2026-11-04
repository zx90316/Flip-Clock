"""Export new-design prototype parts from saved STEP, never import author files."""
from __future__ import annotations
import csv
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from settings import values
from cadgen import read_scene, build123d as bd


def flattened(nodes):
    for node in nodes:
        yield node
        yield from flattened(node.children)


def is_printed(label):
    if not label:return False
    if label.startswith("A") and label not in ("A10_common_input_shaft",):return True
    if label.startswith(("CM_","CH_")):
        return label.split("_",1)[1] in ("output","carrier","pawl","bushing","cover")
    if label.startswith(("DM_","DH_")):return "shaft" not in label
    if label.startswith(("DEM_","DEH_")):return any(t in label for t in ("scallop_disc","pivot_arm","bracket"))
    if label.startswith(("KM_","KH_","RM_","RH_","GM_","GH_")):return True
    if label.startswith(("SM_","SH_")):return "pedestal" in label or "magnet_cap" in label
    return False


def stl_quality(path):
    data=path.read_bytes()
    if len(data)<84:return {"status":"FAIL","reason":"not binary STL"}
    count=struct.unpack_from("<I",data,80)[0]
    if len(data)!=84+50*count:return {"status":"FAIL","reason":"unexpected STL byte length"}
    edges={}
    signed=0.0
    degenerate=0
    for index in range(count):
        raw=struct.unpack_from("<12fH",data,84+50*index)
        tri=[tuple(round(v,5) for v in raw[start:start+3]) for start in (3,6,9)]
        if len(set(tri))<3:degenerate+=1
        a,b,c=tri
        signed+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
        for j in range(3):
            edge=tuple(sorted((tri[j],tri[(j+1)%3])))
            edges[edge]=edges.get(edge,0)+1
    bad=sum(1 for times in edges.values() if times!=2)
    return {"status":"PASS" if bad==0 and degenerate==0 and signed>0 else "FAIL",
            "triangles":count,"nonmanifold_edges":bad,"degenerate_triangles":degenerate,
            "signed_volume_mm3":signed,"vertex_matching_mm":1e-5}


def to_print_pose(shape):
    # Source placements stay in STEP/assembly.step. These are fabrication copies.
    bbox=shape.bounding_box()
    center=(bbox.min+bbox.max)*.5
    shape=shape.moved(bd.Location((-center.X,-center.Y,-center.Z)))
    sizes=(bbox.size.X,bbox.size.Y,bbox.size.Z)
    minimum=min(range(3),key=lambda i:sizes[i])
    orientation="Z flat"
    if minimum==0:shape=shape.rotate(bd.Axis.Y,90);orientation="X rotated 90 degrees about Y"
    elif minimum==1:shape=shape.rotate(bd.Axis.X,90);orientation="Y rotated 90 degrees about X"
    bbox=shape.bounding_box()
    return shape.moved(bd.Location((0,0,-bbox.min.Z))),orientation


def main():
    source=ROOT/"STEP"/"assembly.step"
    if not source.exists():print("BLOCKED: build assembly first");return 2
    scene=read_scene(str(source))
    nodes=list(flattened(scene.roots))
    step_dir=ROOT/"STEP"/"parts";stl_dir=ROOT/"STL"/"prototype"
    step_dir.mkdir(parents=True,exist_ok=True);stl_dir.mkdir(parents=True,exist_ok=True)
    candidates=[]
    for leaf in scene.leaves():
        if is_printed(leaf.label):candidates.append((leaf.label,leaf.shape(),leaf.prototype_id))
    coupon_source=ROOT/"STEP"/"coupon_plate.step"
    if coupon_source.exists():
        coupon_scene=read_scene(str(coupon_source))
        for leaf in coupon_scene.leaves():
            if leaf.label.startswith("CP_") and any(leaf.label.endswith(t) for t in ("_output","_fit_ladder","_hinge_blank")):
                candidates.append((leaf.label,leaf.shape(),"coupon_"+leaf.prototype_id))
    p=values()
    for node in nodes:
        label=node.label
        if len(label)==5 and label[:2] in ("FM","FH") and label[2]=="_" and label[3:].isdigit():
            branch=label[1];k=int(label[3:]);n=p["minute_flaps"] if branch=="M" else p["hour_flaps"]
            sign=-1 if branch=="M" else 1
            angle=-360*k/n;phi=math.radians(angle)
            pose=bd.Pos(sign*p["drum_center_x"],p["flap_pivot_radius"]*math.cos(phi),p["axis_height"]+p["flap_pivot_radius"]*math.sin(phi))*bd.Rot(angle-90,0,0)
            solids=list(node.shape().solids())
            fused=solids[0].fuse(*solids[1:])
            fused=fused.moved(pose.inverse())
            candidates.append((label+"_complete_numbered_flap",fused,None))
    catalog=[];seen={}
    for label,shape,pid in candidates:
        if pid and pid in seen:
            seen[pid]["quantity"]+=1
            seen[pid]["occurrences"].append(label)
            continue
        printed,orientation=to_print_pose(shape)
        printed.label=label
        step_path=step_dir/(label+".step");stl_path=stl_dir/(label+".stl")
        bd.export_step(printed,str(step_path))
        bd.export_stl(printed,str(stl_path),tolerance=.01,angular_tolerance=.05)
        mesh=stl_quality(stl_path)
        size=printed.bounding_box().size
        row={"id":label,"quantity":1,"occurrences":[label],
             "step":str(step_path.relative_to(ROOT)).replace("\\","/"),
             "stl":str(stl_path.relative_to(ROOT)).replace("\\","/"),
             "stl_sha256":hashlib.sha256(stl_path.read_bytes()).hexdigest(),
             "step_sha256":hashlib.sha256(step_path.read_bytes()).hexdigest(),
             "prototype_only":True,"material":"TPU proposal" if label.startswith("A04_") else "PETG proposal; bushings may be purchased POM",
             "print_orientation":orientation,"size_mm":[size.X,size.Y,size.Z],
             "native_valid":bool(printed.is_valid),"native_solids":len(printed.solids()),
             "mesh_check":mesh}
        catalog.append(row)
        if pid:seen[pid]=row
        print(f"{mesh['status']}: {label}",flush=True)
    # Cover posts are reusable manufactured spacers. Their occurrence group has
    # three leaves without separate names, so export one canonical spacer here.
    from geometry import ring
    spacer=ring(2.6,1.65,3.15).moved(bd.Location((0,0,1.575)))
    label="C_cover_spacer";sp=step_dir/(label+".step");st=stl_dir/(label+".stl")
    bd.export_step(spacer,str(sp));bd.export_stl(spacer,str(st),tolerance=.01,angular_tolerance=.05)
    catalog.append({"id":label,"quantity":6,"occurrences":["CM_posts","CH_posts"],
                    "step":str(sp.relative_to(ROOT)).replace("\\","/"),"stl":str(st.relative_to(ROOT)).replace("\\","/"),
                    "stl_sha256":hashlib.sha256(st.read_bytes()).hexdigest(),"prototype_only":True,
                    "material":"PETG proposal","print_orientation":"Z flat","size_mm":[5.2,5.2,3.15],
                    "native_valid":bool(spacer.is_valid),"native_solids":1,"mesh_check":stl_quality(st)})
    failed=[r["id"] for r in catalog if r["mesh_check"]["status"]!="PASS" or not r["native_valid"]]
    report={"design_id":"FC-R1","state":"concept_only","status":"FAIL" if failed else "PASS",
            "source_document_hash":scene.document_hash,"original_geometry_included":False,
            "chord_tolerance_mm":.01,"parts":catalog,"failures":failed,
            "not_included":"purchased hardware, motor and encoder envelopes are not print parts"}
    previous=ROOT/"reports"/"parts_catalog.json"
    if previous.exists():
        old=json.loads(previous.read_text(encoding="utf-8"))
        current_ids={r["id"] for r in catalog}
        for row in old.get("parts",[]):
            if row["id"] not in current_ids:
                old_stl=(ROOT/row["stl"]).resolve()
                old_step=(ROOT/row["step"]).resolve()
                if not old_stl.is_relative_to(stl_dir.resolve()) or not old_step.is_relative_to(step_dir.resolve()):
                    raise ValueError("Obsolete generated output escaped expected folders")
                if old_stl.exists() and hashlib.sha256(old_stl.read_bytes()).hexdigest()==row["stl_sha256"]:
                    old_stl.unlink()
                    if old_step.exists():old_step.unlink()
    (ROOT/"reports"/"parts_catalog.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (ROOT/"reports"/"bom.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.writer(stream);writer.writerow(["ID","quantity","material_proposal","print_orientation","STEP","STL","status"])
        for row in catalog:writer.writerow([row["id"],row["quantity"],row["material"],row["print_orientation"],row["step"],row["stl"],row["mesh_check"]["status"]])
    print(f"Exported {len(catalog)} prototype part definitions; {len(failed)} failed.")
    return 1 if failed else 0


if __name__=="__main__":raise SystemExit(main())
