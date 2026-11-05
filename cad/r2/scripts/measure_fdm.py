"""Run the bundled fact-only DfAM tool on exact fabrication STLs.

Supported walls use the skill's conservative 1.2-mm floor. A wall result is
not reclassified as a small tooth merely to turn a failed measurement green.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("DFAM_SKILL_DIR", Path.home() / ".codex/plugins/cache/openai-curated-remote/text-to-cad/0.7.17/skills/dfam-check"))
TOOL = SKILL / "scripts" / "dfam_tool.py"


def measure(row):
    path = ROOT / row["stl"]; out = ROOT / "reports" / "dfam" / "parts"; out.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(TOOL), "measure", str(path), "--samples", "2000", "--angle-limit", "45"]
    run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    try:
        facts = json.loads(run.stdout)
    except Exception:
        facts = {"error": run.stderr or run.stdout, "partial": True}
    (out / (row["id"] + ".json")).write_text(json.dumps(facts, indent=2), encoding="utf-8")
    record = {"id": row["id"], "source_stl": row["stl"], "stl_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "tool_exit": run.returncode,
              "facts": str((out / (row["id"] + ".json")).relative_to(ROOT)).replace("\\", "/"), "build_orientation": row["orientation"]}
    if run.returncode != 0 or facts.get("partial"):
        record["verdict"] = "UNMEASURED_OR_PARTIAL"
    else:
        record.update(watertight=facts["mesh"]["watertight"], body_count=facts["mesh"]["body_count"], min_mm=facts["wall_thickness"]["min_mm"], p05_mm=facts["wall_thickness"]["p05_mm"],
                      support_area_mm2=facts["overhangs"]["down_facing_area_below_limit_mm2"], supported_wall_floor_mm=1.2)
        record["wall_verdict"] = "PASS" if record["p05_mm"] >= 1.2 else "FAIL"
        record["verdict"] = "MEASURED" if record["watertight"] else "FAIL_NONWATERTIGHT"
        if record["support_area_mm2"] > 0:
            orient = subprocess.run([sys.executable, str(TOOL), "orientations", str(path), "--angle-limit", "45"], capture_output=True, text=True, encoding="utf-8")
            file = out / (row["id"] + "_orientations.json")
            try:
                file.write_text(json.dumps(json.loads(orient.stdout), indent=2), encoding="utf-8")
                record["orientations"] = str(file.relative_to(ROOT)).replace("\\", "/")
            except Exception:
                record["orientation_error"] = orient.stderr or orient.stdout
            record["orientation_exit"] = orient.returncode
        else:
            old_orientation = out / (row["id"] + "_orientations.json")
            if old_orientation.exists(): old_orientation.unlink()
    print(row["id"], record.get("wall_verdict", record["verdict"]), record.get("p05_mm"), record.get("support_area_mm2"), flush=True)
    return record


def main():
    parts = json.loads((ROOT / "reports" / "parts.json").read_text())["parts"]
    # Full structural parts; selected numeral variants include dense 08 and 59.
    selected = [r for r in parts if not r["id"].startswith(("FM_", "FH_")) or r["id"] in ("FM_00_panel", "FM_08_panel", "FM_59_panel", "FH_23_panel")]
    owned = ROOT / "reports" / "dfam" / "parts"
    allowed = {r["id"] + suffix for r in selected for suffix in (".json", "_orientations.json")}
    if owned.exists():
        for stale in owned.glob("*.json"):
            if stale.name not in allowed and ROOT.resolve() in stale.resolve().parents: stale.unlink()
    prior_file = ROOT / "reports" / "dfam" / "summary.json"
    prior = {r["id"]: r for r in json.loads(prior_file.read_text())["parts"]} if prior_file.exists() else {}
    fresh = [r for r in selected if r["id"] not in prior or prior[r["id"]].get("tool_exit") != 0
             or prior[r["id"]].get("stl_sha256") != hashlib.sha256((ROOT / r["stl"]).read_bytes()).hexdigest()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        updated = {r["id"]: r for r in pool.map(measure, fresh)}
    results = [updated.get(r["id"], prior.get(r["id"])) for r in selected]
    report = {"process": "FDM", "printer_user_supplied": "Bambu X2D", "nozzle_mm": .4, "layer_mm": .2, "materials": ["PETG", "PLA"],
              "limit_source": str(SKILL / "references" / "process-limits.md"), "wall_floor_mm": 1.2, "unsupported_wall_floor_mm": 1.6,
              "wall_comparison_scope": "Supported fabrication faces; unsupported freestanding walls also need 1.6 mm. These numbers do not waive support findings.",
              "angle_limit_deg": 45, "samples_per_part": 2000, "selected_parts": len(selected), "omitted_numeral_variants": len(parts) - len(selected), "parts": results,
              "tool_source_sha256": hashlib.sha256(TOOL.read_bytes()).hexdigest(),
              "not_checked_by_mesh_tool": ["Minimum hole diameter", "Minimum positive feature", "Maximum unsupported bridge", "Slicer perimeter continuity", "Material shrinkage and wear", "Spring/fit measurements"],
              "manufacturing_ready": False}
    (ROOT / "reports" / "dfam" / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 1 if any(r.get("wall_verdict") == "FAIL" or r["verdict"].startswith(("FAIL", "UNMEASURED")) for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
