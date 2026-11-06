"""Cross-check reports against the exact current CAD and print meshes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name): return json.loads((ROOT / name).read_text(encoding="utf-8"))


def main():
    errors = []
    parts = read("reports/parts.json")["parts"]
    geometry = read("reports/geometry_check.json")
    if geometry["status"] != "PASS" or geometry["source_sha256"] != sha(ROOT / "STEP/assembly.step"):
        errors.append("Native assembly check is failed or stale")
    for name in ("static_interference", "gear_mesh_check"):
        if read("reports/" + name + ".json")["status"] != "PASS": errors.append(name)
    stops = read("reports/pawl_stops.json")
    if stops["status"] != "PASS_STATIC_ONLY" or stops["source_sha256"] != sha(ROOT / "src/r2_geometry.py"):
        errors.append("Physical pawl-stop check is failed or stale")
    drag = read("reports/drag_fit.json")
    if drag["status"] != "PASS_NOMINAL_GEOMETRY_ONLY" or drag["candidate_step_sha256"] != sha(ROOT / "STEP/assembly_with_drag.step"):
        errors.append("Drag-ring envelope check is failed or stale")
    for part in parts:
        if sha(ROOT / part["stl"]) != part["stl_sha256"]: errors.append("Printed STL: " + part["id"])
    dfam = read("reports/dfam/summary.json")
    for row in dfam["parts"]:
        if sha(ROOT / row["source_stl"]) != row["stl_sha256"]: errors.append("DfAM mesh hash: " + row["id"])
        if row["tool_exit"] != 0 or not row["watertight"] or row["p05_mm"] < dfam["wall_floor_mm"] - 1e-6:
            errors.append("DfAM supported-wall measurement: " + row["id"])
        if row["support_area_mm2"] > 0 and row.get("orientation_exit") != 0:
            errors.append("Missing support-orientation measurement: " + row["id"])
    rebuild = read("reports/package_rebuild.json")
    if rebuild["status"] != "PASS" or any(sha(REPO / name) != value for name, value in rebuild["sources_sha256"].items()):
        errors.append("Extracted-package model-source rebuild is failed or stale")
    report = {"status": "PASS_RECORDED_ARTIFACT_CONSISTENCY" if not errors else "FAIL", "errors": errors,
              "printed_parts": len(parts), "dfam_measured_parts": len(dfam["parts"]),
              "supported_wall_p05_floor_mm": dfam["wall_floor_mm"],
              "minimum_measured_p05_mm": min(row["p05_mm"] for row in dfam["parts"]),
              "rebuilt_native_leaves": rebuild["native_leaf_count"], "rebuild_volume_difference_mm3": rebuild["volume_difference_mm3"],
              "source_sha256": sha(Path(__file__)),
              "scope": "Byte consistency and existing native/DfAM/rebuild checks. Unsupported walls, holes, strength, slicing and motion need their separate evidence.",
              "hardware_verified": False, "manufacturing_ready": False}
    (ROOT / "reports/delivery_consistency.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0 if not errors else 1


if __name__ == "__main__": raise SystemExit(main())
