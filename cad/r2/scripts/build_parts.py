"""Read saved R2 STEP, check selected mates, export explicit fabrication poses.

CAD mass is an estimated solid-density mass, never a weighed FDM part.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import r2_geometry as g
from cadgen import build123d as bd, read_scene
from cadgen.geometry import overlap_volume, closest_points


def output_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk(nodes, path=()):
    for node in nodes:
        chain = path + (node.label or "",)
        yield node, chain
        yield from walk(node.children, chain)


def part_pose(shape, label):
    # Named, intentional build directions; do not rotate the hood onto a wall.
    if label == "A01_inverted_print_hood":
        shape = bd.Rot(180, 0, 0) * shape
        orientation = "roof outside on plate; walls grow upward"
    elif label in ("A02_front_panel", "A03_rear_panel", "A04_display_bezel") or label.startswith("A05_colon_"):
        shape = bd.Rot(-90 if label != "A03_rear_panel" else 90, 0, 0) * shape
        orientation = "outer face on textured plate"
    elif label.startswith("F") and label.endswith("_panel"):
        orientation = "flat front on plate; trunnion front flat coplanar with six-layer panel"
        shape = bd.Rot(-90, 0, 0) * shape
    elif label.startswith(("CM_", "CH_", "DM_", "DH_", "TM_", "TH_", "B")) or label in ("T_idler", "T_idler_pedestal", "A10_M_internal_frame", "A10_H_internal_frame", "A11_center_plain_bearing_pedestal", "E_motor_top_clamp"):
        shape = bd.Rot(0, 90 if label.endswith("_backplate") else -90, 0) * shape
        orientation = "axle vertical; planar functional profile in XY"
    elif label.startswith(("DEM_", "DEH_")) and label.endswith(("_cam", "_arm")):
        shape = bd.Rot(0, -90, 0) * shape
        orientation = "cam/arm broad face on plate"
    elif label.startswith(("SM_", "SH_")) and label.endswith("_magnet_cap"):
        shape = bd.Rot(0, -90, 0) * shape
        orientation = "axle vertical; open end upwards if possible"
    elif label.startswith(("KM_", "KH_")):
        shape = bd.Rot(0, 90 if label.startswith("KH_") else -90, 0) * shape
        orientation = "knob broad outer face on plate; axle vertical"
    else:
        orientation = "designed base on plate"
    box = shape.bounding_box()
    center = (box.min + box.max) * .5
    shape = bd.Pos(-center.X, -center.Y, -box.min.Z) * shape
    return shape, orientation


def printed(label):
    if "ENVELOPE" in label or "paint" in label:
        return False
    return True


def main():
    source = ROOT / "STEP" / "assembly.step"
    scene = read_scene(str(source)); leaves = list(scene.leaves())
    by_label = {n.label: n for n in leaves}; tree = list(walk(scene.roots))
    paths = {n.ref: chain for n, chain in tree}
    mass = []; checks = []; native_bad = []; parts = []
    p = g.config()
    def check(name, passed, measured, threshold):
        checks.append({"id": name, "status": "PASS" if passed else "FAIL", "measured": measured, "threshold": threshold})
        print(checks[-1]["status"], name, flush=True)
    for leaf in leaves:
        shape = leaf.shape(); label = leaf.label
        if not shape.is_valid or not shape.solids() or shape.volume <= 0:
            native_bad.append(label)
        rho = 1200 if "paint" in label else 1800 if "PCB" in label else 7850 if "ENVELOPE" in label and any(k in label.lower() for k in ("shaft", "wire", "pin", "bearing", "608", "magnet", "spring", "pulley", "gearmotor")) else 1410 if "bush" in label else 1270
        if "belt" in label.lower(): rho = 1200
        center = shape.center(bd.CenterOf.MASS); tensor = shape.matrix_of_inertia
        if callable(tensor): tensor = tensor()
        mass.append({"ref": leaf.ref, "label": label, "mass_kg": shape.volume * rho * 1e-9,
                     "volume_mm3": shape.volume, "density_kg_m3": rho, "density_status": "proposal_not_weighed",
                     "com_m": [center.X * .001, center.Y * .001, center.Z * .001],
                     "inertia_kg_m2": (np.asarray(tensor) * rho * 1e-15).tolist()})
    check("saved_native_solids", not native_bad, {"leaf_occurrences": len(leaves), "invalid": native_bad}, "valid positive volume solids")
    whole = scene.roots[0].shape().bounding_box()
    check("desktop_envelope", whole.size.X <= 190.01 and whole.size.Y <= 176 and whole.size.Z <= 120.01,
          [whole.size.X, whole.size.Y, whole.size.Z], "W190 x D<=176 including bezel x H120 mm")
    for b in ("M", "H"):
        labels = [l for l in by_label if l.startswith("F" + b + "_") and l.endswith("_panel")]
        check(b + "_flap_count", len(labels) == g.count(b), len(labels), g.count(b))
        f = p["flap"]; ligament = 2 * g.pivot_r(b) * math.sin(math.pi / g.count(b)) - f["bearing_bore_d"]
        check(b + "_hole_ligament", ligament >= 1.2, ligament, ">=1.2 mm analytic chord between authored bore centres")
        part = by_label["D" + b + "_flange_-1"].shape()
        # Source mates, read back STEP; output shafts must remain separated.
        a = by_label["D" + b + "_shaft_ENVELOPE"].shape()
        check(b + "_shaft_flange_axial_fit", a.bounding_box().size.X > 80, a.bounding_box().size.X, "independent shaft, nominal 83.1 mm")
        actual_y = a.center(bd.CenterOf.MASS).Y
        check(b + "_saved_axis_matches_parameters", abs(actual_y - g.axis_y(b)) < 1e-5, actual_y, g.axis_y(b))
        actual = by_label[f"F{b}_00_panel"].shape().bounding_box()
        expected = (g.flap_pose(0, b) * g.flap_blank()).bounding_box()
        error = max(abs(a_ - e_) for a_, e_ in zip((*actual.min, *actual.max), (*expected.min, *expected.max)))
        check(b + "_saved_initial_leaf_pose", error < 1e-4, error, "bbox error <0.0001 mm vs declared initial pose")
    mshaft = by_label["DM_shaft_ENVELOPE"].shape(); hshaft = by_label["DH_shaft_ENVELOPE"].shape()
    gap = hshaft.bounding_box().min.X - mshaft.bounding_box().max.X
    check("independent_output_gap", gap >= .79, gap, ">=0.79 mm")
    if any(c["status"] != "PASS" for c in checks):
        output_json(ROOT / "reports" / "geometry_check.json", {"status": "FAIL", "checks": checks})
        raise RuntimeError("Saved STEP does not match current geometry; rebuild before exporting")
    # Deterministic mating checks do not constitute an exhaustive motion sweep.
    for a, b in (("A01_inverted_print_hood", "SM_PCB_ENVELOPE"), ("A01_inverted_print_hood", "SH_PCB_ENVELOPE"),
                 ("A00_single_base", "DEM_cam"), ("A00_single_base", "DEH_cam")):
        av, bv = by_label[a].shape(), by_label[b].shape()
        ov = sum(overlap_volume(x, y) for x in av.solids() for y in bv.solids())
        check("clear_" + a + "_" + b, ov < 1e-5, ov, "overlap <1e-5 mm3 at source pose")
    # Export print parts from the saved source. Canonical flaps undo their source
    # pose so both output angles and repeated numbering remain independent.
    stldir = ROOT / "STL" / "parts"; stepdir = ROOT / "STEP" / "parts"
    stldir.mkdir(parents=True, exist_ok=True); stepdir.mkdir(parents=True, exist_ok=True)
    for leaf in leaves:
        label = leaf.label
        if not printed(label) or any("paint" in token for token in paths[leaf.ref]): continue
        shape = leaf.shape()
        if label.startswith("F") and label.endswith("_panel"):
            b = label[1]; k = int(label[3:5]); shape = shape.moved(g.flap_pose(k, b).inverse())
        placed, orientation = part_pose(shape, label)
        stepfile = stepdir / (label + ".step"); stlfile = stldir / (label + ".stl")
        bd.export_step(placed, str(stepfile)); bd.export_stl(placed, str(stlfile), tolerance=.01, angular_tolerance=.06)
        box = placed.bounding_box(); fits = box.size.X <= 256 and box.size.Y <= 256
        parts.append({"id": label, "stl": str(stlfile.relative_to(ROOT)).replace("\\", "/"),
                      "step": str(stepfile.relative_to(ROOT)).replace("\\", "/"), "stl_sha256": sha(stlfile),
                      "size_mm": [box.size.X, box.size.Y, box.size.Z], "fits_256_bed": fits,
                      "orientation": orientation, "native_valid": bool(placed.is_valid), "native_solids": len(placed.solids())})
    check("all_part_bed_envelopes", all(r["fits_256_bed"] for r in parts), {"parts": len(parts), "oversize": [r["id"] for r in parts if not r["fits_256_bed"]]}, "XY <=256 mm in declared print pose")
    check("single_connected_print_parts", all(r["native_solids"] == 1 for r in parts), [r["id"] for r in parts if r["native_solids"] != 1], "one connected solid per fabrication part")
    output_json(ROOT / "reports" / "mass_properties.json", {"source_sha256": sha(source), "estimated_not_measured": True, "parts": mass})
    output_json(ROOT / "reports" / "parts.json", {"source_sha256": sha(source), "parts": parts})
    output_json(ROOT / "reports" / "geometry_check.json", {"source_sha256": sha(source), "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL", "checks": checks,
                "limitations": ["Selected static mates, not an exhaustive swept collision check.", "Printer envelopes do not prove slicing or material fit.", "Named purchased parts are envelopes unless separately vendor verified."]})
    print("Estimated mass kg", sum(r["mass_kg"] for r in mass), "parts exported", len(parts), flush=True)
    return 0 if all(c["status"] == "PASS" for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
