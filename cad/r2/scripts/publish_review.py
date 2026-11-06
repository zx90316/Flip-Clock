"""Publish one explicit self-contained run, preserving evidence byte hashes."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main(run, comparisons=(), destination=None, scenario_runs=()):
    run = Path(run).resolve(); out = Path(destination).resolve() if destination else ROOT / "review"
    if not out.is_relative_to(ROOT.resolve()): raise ValueError("Publication must stay in the R2 project")
    out.mkdir(parents=True, exist_ok=True)
    summary = json.loads((run / "summary.json").read_text()); config = json.loads((run / "run_config.json").read_text())
    if (out / "PUBLISH_MANIFEST.json").is_file() and json.loads((out / "PUBLISH_MANIFEST.json").read_text())["run_id"] != summary["run_id"]:
        raise ValueError("Preserve the existing run; choose --out for a new publication directory")
    required = ["summary.json", "run_config.json", "states.npz", "trajectory.csv", "contact_pairs.json", "render_provenance.json", "desktop.mp4", "cutaway.mp4", "front.mp4", "front.png"]
    for name in required:
        if not (run / name).exists(): raise FileNotFoundError(run / name)
        shutil.copy2(run / name, out / name)
    validation = None
    if (run / "validation.json").is_file():
        validation = json.loads((run / "validation.json").read_text())
        shutil.copy2(run / "validation.json", out / "validation.json")
    elif config.get("runtime_sha256"):
        raise ValueError("Evaluate the complete run before publication")
    shutil.copytree(run / "model", out / "model", dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.mjb", "compiled.json"))
    shutil.copytree(run / "source", out / "source", dirs_exist_ok=True)
    if config.get("drag_config_sha256"):
        drag = run / "source/drag_candidate.json"
        if not drag.is_file(): drag = ROOT / "config/drag_candidate.json"
        if sha(drag) != config["drag_config_sha256"]: raise ValueError("Drag configuration changed after integration")
        shutil.copy2(drag, out / "source" / "drag_candidate.json")
    comparison_paths = list(dict.fromkeys(Path(p).resolve() for p in (*comparisons, *scenario_runs)))
    for directory in comparison_paths:
        directory = Path(directory).resolve()
        target = out / "comparison" / directory.name
        (target / "source").mkdir(parents=True, exist_ok=True)
        for name in ("summary.json", "run_config.json", "contact_pairs.json"):
            shutil.copy2(directory / name, target / name)
        shutil.copytree(directory / "source", target / "source", dirs_exist_ok=True)
        other_config = json.loads((directory / "run_config.json").read_text())
        if other_config["model_sha256"] != config["model_sha256"]:
            shutil.copytree(directory / "model", target / "model", dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.mjb", "compiled.json"))
        for name in ("front.mp4", "front.png", "render_provenance.json", "states.npz", "trajectory.csv", "validation.json"):
            if (directory / name).is_file(): shutil.copy2(directory / name, target / name)
        if (directory / "source/render_r2.py").is_file():
            shutil.copy2(directory / "source/render_r2.py", target / "source/render_r2.py")
    with (run / "contact_points.json").open("rb") as source, gzip.open(out / "contact_points.json.gz", "wb", compresslevel=9) as target:
        shutil.copyfileobj(source, target)
    cycles = [r for r in summary.get("results", []) if r.get("cycle") == 2]
    okay = len(cycles) == 2 and all(abs(r["error_deg"]) <= (.25 if r["branch"] == "M" else .4) and abs(r["inactive_drift_deg"]) <= .25 and r.get("drive_end_reason") != "timeout" for r in cycles)
    okay = okay and summary["initial_penetration_mm"] < .001 and summary["peak_penetration_mm"] <= .2 and not summary["warnings"] and not summary["iteration_limit_steps"] and not summary.get("diagnostic_geometry_override")
    if validation is not None: okay = okay and validation["status"] == "PASS_NOMINAL_SIMULATION"
    result = {"motion_acceptance": "PASS_SIMULATION_ONLY" if okay else "NOT_PASSED", "run_id": summary["run_id"], "cycles": cycles, "timestep_s": config["dt"], "peak_penetration_mm": summary["peak_penetration_mm"],
              "criteria": {"M_absolute_error_deg": .25, "H_absolute_error_deg": .4, "inactive_drift_deg": .25, "peak_penetration_mm": .2, "initial_penetration_mm": .001, "solver_warnings": 0, "iteration_limit_steps": 0},
              "hardware_verified": False, "manufacturing_ready": False, "physics_predictive_validation": False}
    result["all_step_validation"] = validation
    comparison = ROOT / "reports/timestep_comparison.json"
    if comparison.is_file():
        check = json.loads(comparison.read_text())
        if summary["run_id"] in check["run_ids"]:
            result["timestep_validation"] = check
            shutil.copy2(comparison, out / "timestep_comparison.json")
            if not check.get("timestep_consistency_passed", False): result["motion_acceptance"] = "NOT_PASSED"
    invariant_keys = ("model_sha256", "source_sha256", "runtime_sha256", "gravity", "friction", "spring_scale",
                      "solver_parameters", "torque_limit", "output_drag", "hour_output_drag", "release_deg", "coast",
                      "speed", "drive_timeout", "velocity_kp", "velocity_ki", "initial_flap_bias_deg",
                      "trial_plate_thickness", "checkpoint")
    scenarios = []
    for path in scenario_runs:
        directory = Path(path).resolve()
        other = json.loads((directory / "run_config.json").read_text())
        check = json.loads((directory / "validation.json").read_text())
        differences = [key for key in invariant_keys if other.get(key) != config.get(key)]
        scenarios.append({"run_id": directory.name, "case": other["case"], "commands": check["requested_commands"],
                          "status": check["status"], "same_physical_candidate": not differences,
                          "changed_candidate_fields": differences,
                          "validation": "comparison/" + directory.name + "/validation.json"})
        if differences or check["status"] != "PASS_NOMINAL_SIMULATION": result["motion_acceptance"] = "NOT_PASSED"
    result["extended_scenarios"] = scenarios
    (out / "acceptance.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out / "README.md").write_text("""# FC-R2 物理回放

這是求解器記錄的重力、碰撞與單一有限輸入扭矩運算。`COMPLETED` 只代表運算完成，定位驗收以 `acceptance.json` 為準；此包未宣稱實機或製造就緒。

- `desktop.mp4`：包覆式外觀。
- `front.mp4`：前方翻片與轉角。
- `cutaway.mp4`：隱藏外殼，紅點為抽樣的實際接觸位置。
- `states.npz`、`trajectory.csv`：求解器角度、速度與輸入扭矩。
- `model/`：相同版本 MuJoCo 可開啟的 XML 與碰撞／可視資產。
- `source/`：執行時來源快照；不是另一套維護中的 CAD 主檔。

影片由已記錄狀態慢放，沒有補造翻片姿態。完整參數、假設與輸出輪未通過項保留於 JSON。輸出輪無致動器，無理想齒輪／單向等式；彈簧與軸阻力為明列但未實測的力等效模型。

XML 是幾何與基準力學模型。重播或重跑時必須一併套用 `run_config.json` 的時間步長、重力、摩擦、分／時輪阻力與輸入扭矩限制；單獨開啟 XML 不會自動套用本輪整定。`simulation/render_r2.py` 已在回放前還原這些參數。影片以 60 Hz 紀錄、30 fps 慢放；接觸點為抽樣資料，全步長最大穿透以 `summary.json` 為準。

每個指令步進的角度、閒置輪瞬間偏移與最後停靠範圍見 `validation.json`；時間步長比較見 `timestep_comparison.json`。對照資料在 `comparison/`；若該運算的 XML 不同，另附其完整 `model/`。`acceptance.json` 的 `extended_scenarios` 列出額外納入驗收的連續分鐘／小時試驗，必須使用相同候選設定且各自通過。其餘對照可以是保留的失敗診斷，不能混作驗收。驗收門檻與結論均以 `acceptance.json` 為準。
""", encoding="utf-8")
    files = {str(p.relative_to(out)).replace("\\", "/"): sha(p) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "PUBLISH_MANIFEST.json" and p.suffix != ".pyc"}
    (out / "PUBLISH_MANIFEST.json").write_text(json.dumps({"run_id": summary["run_id"], "files_sha256": files, "motion_acceptance": result["motion_acceptance"], "hardware_verified": False}, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--compare", action="append", default=[]); ap.add_argument("--out")
    ap.add_argument("--scenario", action="append", default=[])
    args = ap.parse_args(); main(args.run, args.compare, args.out, args.scenario)
