"""Short finite-input torque probes from an actual saved stall sample.

These isolate control effort and numerical contact settings. They are not
complete clock cycles, measured contact properties or manufacturing acceptance.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import mujoco as mj
from calibrate import load
from diagnose_contact_balance import configure

ROOT = Path(__file__).resolve().parents[1]


def main(args):
    source = Path(args.run).resolve(); cfg = json.loads((source / "run_config.json").read_text())
    states = np.load(source / "states.npz", allow_pickle=False)
    index = int(np.argmin(np.abs(states["time_s"] - args.time)))
    output = ROOT / "runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_stall_probe")
    output.mkdir(parents=True)
    shutil.copy2(Path(__file__), output / "probe_stall.py")
    results = []
    variants = [("recorded_effort", .0006, .9, .95, "pyramidal", abs(float(states["input_torque_Nm"][index]))),
                ("full_50mNm", .0006, .9, .95, "pyramidal", .05),
                ("elliptic_50mNm", .0006, .9, .95, "elliptic", .05),
                ("stiffer_elliptic_50mNm", .0002, .95, .995, "elliptic", .05)]
    for label, timeconst, dmin, dmax, cone, budget in variants:
        model, data, dyn, _ = load(source / "model"); configure(model, dyn, cfg)
        model.geom_solref[:] = [timeconst, 1]
        model.geom_solimp[:] = [dmin, dmax, .0001, .5, 2]
        model.opt.cone = mj.mjtCone.mjCONE_ELLIPTIC if cone == "elliptic" else mj.mjtCone.mjCONE_PYRAMIDAL
        model.actuator_ctrlrange[0] = [-budget, budget]; model.actuator_forcerange[0] = [-budget, budget]
        data.qpos[:] = states["qpos"][index]; data.qvel[:] = states["qvel"][index]
        names = {mj.mj_id2name(model, mj.mjtObj.mjOBJ_JOINT, j): int(model.jnt_dofadr[j]) for j in range(model.njnt)}
        mj.mj_forward(model, data); initial = data.qpos.copy(); peak = 0.; trace = []; reached = False
        for step in range(int(args.duration / cfg["dt"])):
            velocity = float(data.qvel[names["I"]]); limit = budget * max(0., 1 - abs(velocity) / 3) if velocity < 0 else budget
            data.ctrl[0] = -limit
            mj.mj_step(model, data)
            peak = max(peak, max((-float(c.dist) * 1000 for c in data.contact), default=0.))
            if step % 20 == 0: trace.append([data.time, float(data.ctrl[0])] + [float(data.qpos[names[b]]) for b in ("I", "M", "H")])
            if data.qpos[names["M"]] <= np.deg2rad(-12): reached = True; break
        np.savez_compressed(output / (label + ".npz"), initial_qpos=initial, final_qpos=data.qpos, final_qvel=data.qvel, trace=np.asarray(trace))
        row = {"label": label, "duration_s": float(data.time), "finite_input_budget_Nm": budget, "time_constant_s": timeconst,
               "impedance_min_max": [dmin, dmax], "cone": cone, "peak_penetration_mm": peak,
               "start_angles_deg": {b: float(np.rad2deg(initial[names[b]])) for b in ("I", "M", "H")},
               "end_angles_deg": {b: float(np.rad2deg(data.qpos[names[b]])) for b in ("I", "M", "H")},
               "crossed_minus12_deg": reached, "warnings": {mj.mjtWarning(i).name: int(w.number) for i, w in enumerate(data.warning) if w.number}}
        results.append(row); print(json.dumps(row), flush=True)
    report = {"source_run": source.name, "sample_time_s": float(states["time_s"][index]), "cases": results,
              "source_sha256": hashlib.sha256((output / "probe_stall.py").read_bytes()).hexdigest(),
              "recorded_state_sha256": hashlib.sha256((source / "states.npz").read_bytes()).hexdigest(),
              "diagnostic_only": True, "complete_cycle_acceptance": False, "hardware_verified": False}
    (output / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "reports/torque_probes.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("run"); parser.add_argument("--time", type=float, default=9.5); parser.add_argument("--duration", type=float, default=.3)
    main(parser.parse_args())
