"""Compare the same candidate at two time steps without changing acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(coarse, fine):
    dirs = [Path(p).resolve() for p in (coarse, fine)]
    configs = [json.loads((p / "run_config.json").read_text()) for p in dirs]
    summaries = [json.loads((p / "summary.json").read_text()) for p in dirs]
    changed = {key: [configs[0].get(key), configs[1].get(key)] for key in configs[0].keys() | configs[1].keys()
               if configs[0].get(key) != configs[1].get(key)}
    controlled = set(changed) == {"dt"} and configs[1]["dt"] < configs[0]["dt"]
    for path, cfg in zip(dirs, configs):
        if hashlib.sha256((path / "source/calibrate.py").read_bytes()).hexdigest() != cfg["source_sha256"]:
            raise ValueError("Controller snapshot does not match recorded provenance")
    rows = []
    for branch in ("M", "H"):
        results = [next((r for r in s["results"] if r["cycle"] == 2 and r["branch"] == branch), None) for s in summaries]
        if any(r is None for r in results): raise ValueError("Both second-cycle outputs are required")
        rows.append({"branch": branch, "coarse": results[0], "fine": results[1],
                     "final_position_difference_deg": results[1]["final_deg"] - results[0]["final_deg"],
                     "both_meet_position_criteria": all(abs(r["error_deg"]) <= (.25 if branch == "M" else .4)
                                                        and abs(r["inactive_drift_deg"]) <= .25 and r["drive_end_reason"] != "timeout" for r in results)})
    validations = [json.loads((p / "validation.json").read_text()) if (p / "validation.json").is_file() else None for p in dirs]
    consistent = controlled and all(v and v["status"] == "PASS_NOMINAL_SIMULATION" for v in validations) and all(abs(r["final_position_difference_deg"]) <= .05 for r in rows)
    report = {"status": "PASS_TWO_TIMESTEP_CHECK" if consistent else "NOT_DEMONSTRATED", "timestep_consistency_passed": consistent,
              "final_position_difference_limit_deg": .05, "controlled_same_candidate": controlled, "changed_config_fields": changed,
              "run_ids": [s["run_id"] for s in summaries], "dt_s": [c["dt"] for c in configs],
              "peak_penetration_mm": [s["peak_penetration_mm"] for s in summaries], "second_cycle": rows,
              "run_validation_statuses": [v["status"] if v else "NOT_EVALUATED" for v in validations],
              "reason": "Both runs must pass every commanded step, idle excursion, settling and penetration; second-cycle position difference must be <=0.05 deg. Two sizes do not establish hardware prediction.",
              "physics_predictive_validation": False, "hardware_verified": False}
    if not controlled: report["reason"] = "Other configuration differences prevent a controlled time-step comparison."
    (ROOT / "reports/timestep_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("coarse"); ap.add_argument("fine")
    args = ap.parse_args(); main(args.coarse, args.fine)
