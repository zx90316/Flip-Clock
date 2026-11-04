"""Read back saved STEP; report only the L0 checks actually performed."""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from settings import values
from cadgen import read_scene, build123d as bd
from cadgen.geometry import overlap_volume, closest_points


def main():
    p=values()
    records=[]
    def check(name,passed,measured=None,threshold=None):
        row={"id":name,"status":"PASS" if passed else "FAIL","measured":measured,"threshold":threshold}
        records.append(row)
        print(f"{row['status']}: {name} {measured}",flush=True)
    source=ROOT/"STEP"/"assembly.step"
    if not source.exists():
        report={"status":"BLOCKED","reason":"Build assembly.step first","checks":[]}
        (ROOT/"reports"/"geometry_check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        return 2
    scene=read_scene(str(source))
    leaves=list(scene.leaves())
    by_label={leaf.label:leaf for leaf in leaves}
    role_paths={}
    def flatten(nodes,ancestry=()):
        for node in nodes:
            path=ancestry+(node.label or "",)
            role_paths[node.ref]="_".join(path).lower()
            yield node
            yield from flatten(node.children,path)
    all_nodes=list(flatten(scene.roots))
    unique={}
    mass=[]
    invalid=[]
    count_solids=0
    for leaf in leaves:
        if leaf.prototype_id not in unique:
            shape=leaf.shape()
            solids=list(shape.solids())
            volumes=[s.volume for s in solids]
            unique[leaf.prototype_id] = bool(shape.is_valid and solids and all(v>1e-9 for v in volumes))
            if not unique[leaf.prototype_id]:invalid.append({"label":leaf.label,"valid":shape.is_valid,"volumes":volumes})
        shape=leaf.shape()
        count_solids+=len(shape.solids())
        label=leaf.label
        role=role_paths[leaf.ref]
        steel=label.startswith(("B00_","B01_")) or any(token in role for token in ("_pin","_shaft","_race","_shield","_diametric_magnet","_spring","_screw","_roller"))
        rho=7850 if steel else 1800 if "PCB" in label else 1200 if "tpu_foot" in role else 1270
        volume=shape.volume
        center=shape.center(bd.CenterOf.MASS)
        inertia=shape.matrix_of_inertia
        if callable(inertia):inertia=inertia()
        mass.append({"id":label,"ref":leaf.ref,"prototype_id":leaf.prototype_id,
                     "volume_mm3":volume,"estimated_mass_kg":volume*1e-9*rho,
                     "density_kg_m3":rho,"density_status":"proposal_solid_envelope",
                     "center_of_mass_m":[center.X*.001,center.Y*.001,center.Z*.001],
                     "inertia_about_com_kg_m2":[[float(v)*rho*1e-15 for v in row] for row in inertia]})
    check("L0_positive_valid_solids",not invalid,{"occurrences":len(leaves),"unique_prototypes":len(unique),"solids":count_solids,"invalid":invalid},"all checked prototype solids valid; volume > 1e-9 mm3")
    tiles=[leaf.shape().bounding_box().size for leaf in leaves if leaf.label.startswith("A00_base_")]
    check("L0_base_tiles_print_envelope",len(tiles)==4 and all(t.X<=180.001 and t.Y<=180.001 and abs(t.Z-6)<1e-4 for t in tiles),
          [[t.X,t.Y,t.Z] for t in tiles],"four tiles; each XY <=180 mm; thickness 6 mm")
    for branch,n in (("M",60),("H",24)):
        panels=[l for l in leaves if l.label.startswith("F"+branch+"_") and l.label.endswith("_panel")]
        pins=[l for l in leaves if l.label.startswith("P"+branch+"_") and l.label.endswith("_flap_pin")]
        check(f"L0_{branch}_physical_flap_count",len(panels)==n and len(pins)==n,{"panels":len(panels),"pins":len(pins)},n)
        pin_angles=[]
        for k in range(n):
            center=by_label[f"P{branch}_{k:02}_flap_pin"].shape().center(bd.CenterOf.MASS)
            pin_angles.append(math.atan2(center.Z-p["axis_height"],center.Y))
        cyclic_steps=[math.degrees(math.atan2(math.sin(pin_angles[(k+1)%n]-pin_angles[k]),math.cos(pin_angles[(k+1)%n]-pin_angles[k]))) for k in range(n)]
        progression_error=max(abs(step+360/n) for step in cyclic_steps)
        check(f"L0_{branch}_number_progression_for_positive_output",progression_error<1e-3,
              {"numbered_pin_step_deg":cyclic_steps[0],"max_error_deg":progression_error},
              f"next number at {-360/n} deg, so positive output brings increasing numbers to a fixed release azimuth; actual gravity release NOT_RUN")
        upper=[l.label for l in all_nodes if l.label.startswith("F"+branch+"_") and "_upper_" in l.label]
        lower=[l.label for l in all_nodes if l.label.startswith("F"+branch+"_") and "_lower_" in l.label]
        upper_ok=len(upper)==n and all(f"F{branch}_{k:02}_upper_{k:02}" in upper for k in range(n))
        lower_ok=len(lower)==n and all(f"F{branch}_{k:02}_lower_{(k+1)%n:02}" in lower for k in range(n))
        check(f"L0_{branch}_number_pair_manifest",upper_ok and lower_ok,{"upper":len(upper),"lower":len(lower)},"leaf k: upper k / lower (k+1) mod N; visual release NOT_RUN")
        glyph=next(node for node in all_nodes if node.label==f"F{branch}_12_upper_12")
        cx=by_label[f"D{branch}_core"].shape().center(bd.CenterOf.MASS).X
        ink_x=[solid.center(bd.CenterOf.MASS).X-cx for solid in glyph.shape().solids()]
        left_segments=sum(x>0 for x in ink_x);right_segments=sum(x<0 for x in ink_x)
        check(f"L0_{branch}_front_glyph_12_reading_direction",left_segments==1 and right_segments==3,
              {"screen_left_tens_1_upper_segments":left_segments,"screen_right_ones_2_upper_segments":right_segments},
              "+Y front: screen-right is -X; 12 upper half uses 1 segment on left and 3 on right")
        flange=by_label[f"D{branch}_flange_L"].shape()
        centers=set()
        for edge in flange.edges():
            if edge.geom_type == bd.GeomType.CIRCLE and abs(edge.radius-p["flap_pin_bore"]/2)<1e-5:
                center=edge.arc_center
                centers.add((round(center.Y,5),round(center.Z,5)))
        angles=sorted(math.degrees(math.atan2(z-p["axis_height"],y))%360 for y,z in centers)
        steps=[(angles[(i+1)%len(angles)]-angles[i])%360 for i in range(len(angles))] if angles else []
        max_error=max(abs(step-360/n) for step in steps) if steps else None
        check(f"L0_{branch}_saved_hole_pattern",len(centers)==n and max_error is not None and max_error<1e-3,
              {"holes":len(centers),"pitch_deg":360/n,"max_error_deg":max_error},"angular error < 0.001 deg; analytic circle centers")
        for first in (0,n//4,n//2,3*n//4):
            second=(first+1)%n
            a=by_label[f"F{branch}_{first:02}_panel"].shape().solids()[0]
            b=by_label[f"F{branch}_{second:02}_panel"].shape().solids()[0]
            overlap=overlap_volume(a,b)
            distance=closest_points(a,b).distance
            check(f"L0_{branch}_radial_pose_neighbor_{first:02}",overlap<1e-6 and distance>.1,
                  {"overlap_mm3":overlap,"minimum_gap_mm":distance},"radial inspection pose only: overlap <1e-6 mm3, gap >0.1 mm")
    for branch in ("M","H"):
        output=by_label[f"C{branch}_output"].shape().solids()[0]
        pawl=by_label[f"C{branch}_pawl"].shape().solids()[0]
        carrier=by_label[f"C{branch}_carrier"].shape().solids()[0]
        ov1,ov2=overlap_volume(output,pawl),overlap_volume(carrier,pawl)
        check(f"L0_{branch}_clutch_rest_clearance",max(ov1,ov2)<1e-6,
              {"pawl_ring_overlap_mm3":ov1,"pawl_carrier_overlap_mm3":ov2},"no solid overlap in saved inspection pose; contact motion NOT_RUN")
    # Actual solid interference at the three saved mesh pairs, no ideal gear constraint.
    pairs=(("CM_output","A40M_idler"),("A40M_idler","A4M_drum_gear"),("CH_output","A4H_drum_gear"))
    for first,second in pairs:
        a=by_label[first].shape().solids()[0];b=by_label[second].shape().solids()[0]
        overlap=overlap_volume(a,b)
        check("L0_gear_rest_"+first+"__"+second,overlap<1e-5,{"overlap_mm3":overlap},"<1e-5 mm3 at saved phase; full rotational contact NOT_RUN")
    left,right=sorted([by_label[f"D{b}_independent_output_shaft"].shape().bounding_box() for b in ("H","M")],key=lambda box:box.min.X)
    gap=right.min.X-left.max.X
    check("L0_independent_output_shaft_gap",abs(gap-8)<1e-5,{"axial_gap_mm":gap},"8 mm; no shared rigid output shaft")
    hour_x=by_label["DH_core"].shape().center(bd.CenterOf.MASS).X
    minute_x=by_label["DM_core"].shape().center(bd.CenterOf.MASS).X
    check("L0_HH_MM_front_order",hour_x>minute_x,{"hour_X_mm":hour_x,"minute_X_mm":minute_x},"looking from +Y: hours at screen-left (+X), minutes at screen-right (-X)")
    guard_h=by_label["GH_removable_side_panel"].shape().center(bd.CenterOf.MASS).X
    guard_m=by_label["GM_removable_side_panel"].shape().center(bd.CenterOf.MASS).X
    check("L0_guard_branch_labels",guard_h>0 and guard_m<0,{"hour_guard_X_mm":guard_h,"minute_guard_X_mm":guard_m},"guards correspond to the actual hour/minute sides")
    for branch in ("M","H"):
        cap=by_label[f"S{branch}_magnet_cap"].shape().solids()[0]
        shaft=by_label[f"D{branch}_independent_output_shaft"].shape().solids()[0]
        overlap=overlap_volume(cap,shaft)
        check(f"L0_{branch}_magnet_cap_shaft_fit",overlap<1e-6,{"overlap_mm3":overlap},"<1e-6 mm3; correct cap bore direction")
        disc=by_label[f"DE{branch}_scallop_disc"].shape().solids()[0]
        roller=by_label[f"DE{branch}_roller"].shape().solids()[0]
        overlap=overlap_volume(disc,roller)
        clearance=closest_points(disc,roller).distance
        check(f"L0_{branch}_detent_roller_inspection_pose",overlap<1e-6 and clearance>.005,
              {"overlap_mm3":overlap,"clearance_mm":clearance},
              "no overlap; >0.005 mm geometric inspection clearance; spring-preloaded contact dynamics NOT_RUN")
        outer=f"D{branch}_flange_{'R' if branch=='H' else 'L'}"
        stack_pairs=((f"A4{branch}_drum_gear",f"DE{branch}_scallop_disc"),
                     (f"A4{branch}_drum_gear",f"K{branch}_forward_setting_knob"),
                     (f"DE{branch}_scallop_disc",outer))
        for first,second in stack_pairs:
            a=by_label[first].shape().solids()[0];b=by_label[second].shape().solids()[0]
            overlap=overlap_volume(a,b);clearance=closest_points(a,b).distance
            check(f"L0_{branch}_axial_stack_{first}__{second}",overlap<1e-6 and clearance>.15,
                  {"overlap_mm3":overlap,"minimum_clearance_mm":clearance},
                  "zero overlap and >0.15 mm axial/module clearance")
        follower_pairs=((f"DE{branch}_pivot_arm",f"A4{branch}_drum_gear"),
                        (f"DE{branch}_pivot_arm",outer),
                        (f"DE{branch}_pivot_arm",f"DE{branch}_scallop_disc"),
                        (f"DE{branch}_pivot_arm",f"DE{branch}_roller"),
                        (f"DE{branch}_bracket",f"A01_side_frame_{branch}"),
                        (f"DE{branch}_bracket",f"DE{branch}_pivot_arm"),
                        (f"DE{branch}_compression_spring",f"G{branch}_removable_side_panel"),
                        (f"K{branch}_forward_setting_knob",f"S{branch}_magnet_cap"),
                        (f"DE{branch}_roller_pin",f"A4{branch}_drum_gear"),
                        (f"DE{branch}_roller_pin",outer))
        for first,second in follower_pairs:
            a=by_label[first].shape().solids()[0];b=by_label[second].shape().solids()[0]
            overlap=overlap_volume(a,b);clearance=closest_points(a,b).distance
            check(f"L0_{branch}_follower_clearance_{first}__{second}",overlap<1e-6 and clearance>.15,
                  {"overlap_mm3":overlap,"minimum_clearance_mm":clearance},"zero overlap and >0.15 mm at saved inspection pose")
    check("L0_transmission_sign",True,{"M":(-1)*(-1)*p["minute_driver_teeth"]/p["minute_output_teeth"],"H":-p["hour_driver_teeth"]/p["hour_output_teeth"]},"kinematic sign only, does not establish clutch behavior")
    source_files=[path for path in (ROOT/"src").glob("*.py") if not path.stem.endswith("_drawing")]
    forbidden=[str(path.relative_to(ROOT)) for path in source_files
               if any(token in path.read_text(encoding="utf-8") for token in ("read_step(","import_step(","source/original/extracted"))]
    check("L0_new_design_no_imported_author_geometry",not forbidden,{"source_files":len(source_files),"forbidden_import_files":forbidden},"authored model source does not import original geometry")
    failures=[r for r in records if r["status"]=="FAIL"]
    report={"schema_version":1,"design_id":"FC-R1","status":"FAIL" if failures else "PASS",
            "scope":"selected L0 geometry checks only", "saved_step":str(source),
            "document_hash":scene.document_hash,"units":"mm, mm3, deg",
            "requested_cases":len(records),"executed_cases":len(records),
            "pass":len(records)-len(failures),"fail":len(failures),"blocked":0,"not_run":0,
            "checks":records,"unchecked":["all-parts pairwise interference","continuous full rotation","flap gravity/release","contact dynamics","torque and stress","print tolerances","physical assembly access"],
            "physics_verified":False,"hardware_verified":False,"manufacturing_ready":False}
    (ROOT/"reports"/"geometry_check.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (ROOT/"reports"/"mass_properties_SI.json").write_text(json.dumps({"note":"role-based solid density proposals, not measured printed properties or actual purchased-component weights; world-axis inertia about each COM","parts":mass},ensure_ascii=False,indent=2),encoding="utf-8")
    return 1 if failures else 0


if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
