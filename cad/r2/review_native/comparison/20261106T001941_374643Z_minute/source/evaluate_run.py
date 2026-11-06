"""Check every commanded step, transient idle drift and final settling."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CRITERIA = {"M_error_deg": .25, "H_error_deg": .4, "inactive_peak_excursion_deg": .25,
            "settling_window_s": .25, "settling_range_deg": .1, "settling_mean_abs_velocity_deg_s": 1.,
            "initial_penetration_mm": .001, "peak_penetration_mm": .2, "net_positive_axle_friction_work_J": 1e-6}


def main(directory):
    directory = Path(directory).resolve(); summary = json.loads((directory / "summary.json").read_text())
    config = json.loads((directory / "run_config.json").read_text())
    trajectory = np.genfromtxt(directory / "trajectory.csv", delimiter=",", names=True)
    events = summary["events"]; drives = [(i, e) for i, e in enumerate(events) if e["stage"].endswith("_drive")]
    rows = []
    for result, (event_i, drive) in zip(summary["results"], drives):
        branch = result["branch"]; other = "H" if branch == "M" else "M"
        end = events[event_i + 2]["time_s"] if event_i + 2 < len(events) else summary["simulated_duration_s"]
        span = trajectory[(trajectory["time_s"] >= drive["time_s"]) & (trajectory["time_s"] <= end)]
        window = span[span["time_s"] >= end - CRITERIA["settling_window_s"]]
        if len(window) < 20: raise ValueError("Insufficient settling-window samples")
        idle_peak = max(float(np.max(abs(np.rad2deg(span[other + "_rad"]) - result.get("inactive_reference_deg", drive[other + "_deg"])))), result.get("inactive_peak_excursion_deg", 0.))
        ranges = {b: float(np.ptp(np.rad2deg(window[b + "_rad"]))) for b in ("M", "H")}
        speeds = {b: float(np.mean(abs(np.rad2deg(window[b + "_rad_s"])))) for b in ("M", "H")}
        okay = abs(result["error_deg"]) <= CRITERIA[branch + "_error_deg"] and result["drive_end_reason"] != "timeout"
        okay = okay and idle_peak <= CRITERIA["inactive_peak_excursion_deg"] and max(ranges.values()) <= CRITERIA["settling_range_deg"] and max(speeds.values()) <= CRITERIA["settling_mean_abs_velocity_deg_s"]
        rows.append({**result, "status": "PASS" if okay else "FAIL", "inactive_peak_excursion_deg": idle_peak,
                     "settling_range_deg": ranges, "settling_mean_abs_velocity_deg_s": speeds, "window_samples": len(window)})
    requested = config["cycles"] * (2 if config["case"] == "drive" else 1)
    basic = summary["status"] == "COMPLETED" and summary["finished_controller"] and len(rows) == requested and len(rows) > 0 and all(r["status"] == "PASS" for r in rows)
    basic = basic and summary["initial_penetration_mm"] < CRITERIA["initial_penetration_mm"] and summary["peak_penetration_mm"] <= CRITERIA["peak_penetration_mm"] and not summary["warnings"] and not summary["iteration_limit_steps"] and not summary.get("diagnostic_geometry_override")
    friction = summary.get("axle_friction_work_J")
    if friction is not None: basic = basic and max(friction.values()) <= CRITERIA["net_positive_axle_friction_work_J"]
    report = {"status": "PASS_NOMINAL_SIMULATION" if basic else "NOT_PASSED", "run_id": summary["run_id"], "criteria": CRITERIA,
              "case": config["case"], "requested_commands": requested,
              "all_commanded_cycles_included": True, "steps": rows, "peak_penetration_mm": summary["peak_penetration_mm"],
              "initial_penetration_mm": summary["initial_penetration_mm"], "axle_friction_work_J": friction,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scope": "Recorded 200-Hz output traces and all-step penetration maximum. No hardware, lifetime, material or display-readability validation.",
              "hardware_verified": False, "physics_predictive_validation": False}
    (directory / "source/evaluate_run.py").write_bytes(Path(__file__).read_bytes())
    (directory / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "reports/latest_motion_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "run_id": summary["run_id"], "peak_penetration_mm": summary["peak_penetration_mm"], "steps": rows}, indent=2), flush=True)
    return 0 if basic else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("run"); raise SystemExit(main(parser.parse_args().run))
