"""Reconstruct a recorded stall and attribute generalized contact reactions.

Only the initial diagnostic state is restored. Optional short torque probes
then integrate forces without assigning any output pose or velocity.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import numpy as np
import mujoco as mj
from calibrate import load

ROOT = Path(__file__).resolve().parents[1]


def configure(model, dynamics, cfg):
    model.opt.timestep = cfg["dt"]; model.opt.gravity[:] = [0, 0, -cfg["gravity"]]
    model.geom_friction[:, 0] = cfg["friction"]
    for branch in ("M", "H"):
        value = cfg.get("hour_output_drag") if branch == "H" and cfg.get("hour_output_drag") is not None else cfg.get("output_drag")
        if value is not None:
            j = mj.mj_name2id(model, mj.mjtObj.mjOBJ_JOINT, branch)
            model.dof_frictionloss[model.jnt_dofadr[j]] = value
    for spec, _, _, _ in dynamics.springs: spec["stiffness_N_m"] *= cfg["spring_scale"]


def main(args):
    run = Path(args.run).resolve(); cfg = json.loads((run / "run_config.json").read_text())
    states = np.load(run / "states.npz", allow_pickle=False)
    index = int(np.argmin(np.abs(states["time_s"] - args.time)))
    model, data, dyn, _ = load(run / "model"); configure(model, dyn, cfg)
    data.qpos[:] = states["qpos"][index]; data.qvel[:] = states["qvel"][index]
    data.ctrl[0] = states["input_torque_Nm"][index]
    model.actuator_ctrlrange[0] = [-cfg["torque_limit"], cfg["torque_limit"]]
    model.actuator_forcerange[0] = [-cfg["torque_limit"], cfg["torque_limit"]]
    mj.mj_forward(model, data)
    joints = {mj.mj_id2name(model, mj.mjtObj.mjOBJ_JOINT, j): int(model.jnt_dofadr[j]) for j in range(model.njnt)}
    selected = ("I", "M", "H", "OM", "OH", "PM", "PH")
    torque = lambda array: {name: float(array[joints[name]]) for name in selected}
    jac = data.efc_J.reshape(data.nefc, model.nv)
    pairs = defaultdict(lambda: {"generalized_Nm": np.zeros(model.nv), "contacts": 0, "penetration_mm": 0., "geoms": set()})
    summed = np.zeros(model.nv)
    for contact in data.contact:
        if contact.efc_address < 0: continue
        ids = (int(contact.geom1), int(contact.geom2))
        bodies = [mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[gid])) or "world" for gid in ids]
        label = " / ".join(sorted(bodies)); row = pairs[label]
        rows = 2 * (contact.dim - 1) if mj.mj_isPyramidal(model) and contact.dim > 1 else contact.dim
        first = contact.efc_address
        force = jac[first:first + rows].T @ data.efc_force[first:first + rows]
        row["generalized_Nm"] += force; summed += force
        row["contacts"] += 1; row["penetration_mm"] = max(row["penetration_mm"], -float(contact.dist) * 1000)
        row["geoms"].add(" / ".join(mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, gid) or str(gid) for gid in ids))
    rows = [{"pair": name, **{k: v for k, v in row.items() if k not in ("generalized_Nm", "geoms")}, "generalized_Nm": torque(row["generalized_Nm"]), "geom_pairs": sorted(row["geoms"])} for name, row in pairs.items()]
    rows.sort(key=lambda r: max(abs(v) for v in r["generalized_Nm"].values()), reverse=True)
    report = {"source_run": run.name, "recorded_time_s": float(states["time_s"][index]), "stage": str(states["stage"][index]),
              "angles_deg": {name: float(np.rad2deg(data.qpos[joints[name]])) for name in selected}, "velocity_rad_s": torque(data.qvel),
              "input_command_Nm": float(data.ctrl[0]), "generalized_forces": {name: torque(getattr(data, name)) for name in ("qfrc_actuator", "qfrc_passive", "qfrc_bias", "qfrc_constraint")},
              "contacts_generalized_Nm": torque(summed), "noncontact_constraint_Nm": torque(data.qfrc_constraint - summed),
              "acceleration_rad_s2": torque(data.qacc), "contact_pairs": rows,
              "limitations": "Recomputed forward dynamics at a saved solver sample, without the original warm-start vector; not a measured force balance.",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "hardware_verified": False}
    (ROOT / "reports/contact_balance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "contact_pairs"}, indent=2), flush=True)
    print(json.dumps(rows[:12], indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("run"); parser.add_argument("--time", type=float, default=9.5)
    main(parser.parse_args())
