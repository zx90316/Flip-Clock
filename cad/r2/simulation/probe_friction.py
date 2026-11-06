"""Controlled free-coast probes of the numerical dry-friction enforcement.

Restore one genuine recorded state once, then integrate zero input torque.
Changing numerical parameters at a penetrated state is diagnostic only.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import mujoco as mj
from calibrate import load
from diagnose_contact_balance import configure
from runtime import apply_solver_parameters, friction_rows

ROOT = Path(__file__).resolve().parents[1]


def main(args):
    source = Path(args.run).resolve(); cfg = json.loads((source / "run_config.json").read_text())
    states = np.load(source / "states.npz", allow_pickle=False); index = int(np.argmin(abs(states["time_s"] - args.time)))
    settings = json.loads((ROOT / "config/solver_candidate.json").read_text())
    dry_only = deepcopy(settings)
    dry_only["contact"].update(time_constant_s=.0006, impedance_min=.9, impedance_max=.95, width_m=.0001, cone="pyramidal")
    output = ROOT / "runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_friction_probe")
    output.mkdir(parents=True)
    for filename in ("probe_friction.py", "runtime.py", "diagnose_contact_balance.py"):
        shutil.copy2(Path(__file__).with_name(filename), output / filename)
    results = []
    for label, parameters in (("baseline_default_joint_friction", None), ("tight_joint_friction_only", dry_only), ("tight_contact_and_joint_friction", settings)):
        model, data, dyn, _ = load(source / "model"); configure(model, dyn, cfg)
        apply_solver_parameters(model, parameters)
        data.qpos[:] = states["qpos"][index]; data.qvel[:] = states["qvel"][index]
        data.ctrl[0] = 0.
        adr = {b: int(model.jnt_dofadr[mj.mj_name2id(model, mj.mjtObj.mjOBJ_JOINT, b)]) for b in ("I", "M", "H")}
        mj.mj_forward(model, data)
        initial_energy = float(np.sum(data.energy)) + dyn.spring_energy(data)
        begin = {b: float(np.rad2deg(data.qpos[j])) for b, j in adr.items()}
        begin_v = {b: float(np.rad2deg(data.qvel[j])) for b, j in adr.items()}
        rows = friction_rows(data, {b: adr[b] for b in ("M", "H")})
        work = {b: 0. for b in rows}; positive = work.copy(); peak = 0.; trace = []
        for step in range(round(args.duration / cfg["dt"])):
            before = {b: float(data.qpos[adr[b]]) for b in rows}
            mj.mj_step(model, data)
            torques = {b: float(data.efc_force[i]) if i is not None else 0. for b, i in rows.items()}
            for b in rows:
                delta = torques[b] * (float(data.qpos[adr[b]]) - before[b]); work[b] += delta; positive[b] += max(0., delta)
            peak = max(peak, max((-float(c.dist) * 1000 for c in data.contact), default=0.))
            if step % 10 == 0: trace.append([float(data.time)] + [float(data.qpos[adr[b]]) for b in ("I", "M", "H")] + [torques[b] for b in rows])
        mj.mj_forward(model, data)
        np.savez_compressed(output / (label + ".npz"), trace=np.asarray(trace), final_qpos=data.qpos, final_qvel=data.qvel)
        result = {"label": label, "duration_s": float(data.time), "input_torque_Nm": 0,
                  "settings": parameters, "start_angles_deg": begin, "start_velocity_deg_s": begin_v,
                  "end_angles_deg": {b: float(np.rad2deg(data.qpos[j])) for b, j in adr.items()},
                  "end_velocity_deg_s": {b: float(np.rad2deg(data.qvel[j])) for b, j in adr.items()},
                  "friction_work_J": work, "friction_positive_work_J": positive, "peak_penetration_mm": peak,
                  "initial_mechanical_energy_J": initial_energy, "final_mechanical_energy_J": float(np.sum(data.energy)) + dyn.spring_energy(data),
                  "warnings": {mj.mjtWarning(i).name: int(w.number) for i, w in enumerate(data.warning) if w.number}}
        results.append(result); print(json.dumps(result), flush=True)
    report = {"source_run": source.name, "sample_time_s": float(states["time_s"][index]), "stage": str(states["stage"][index]),
              "cases": results, "diagnostic_only": True, "hardware_verified": False,
              "limits": "Mechanical energy excludes solver soft-contact storage. Parameter changes at the copied state are not a from-rest validation.",
              "model_sha256": hashlib.sha256((source / "model/model.xml").read_bytes()).hexdigest(),
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.py")}}
    (output / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "reports/friction_probes.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("run"); parser.add_argument("--time", type=float, default=5.0); parser.add_argument("--duration", type=float, default=.35)
    main(parser.parse_args())
