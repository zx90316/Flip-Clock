"""Integrate R2 contacts with bounded INPUT torque and simulated encoder feedback.

Writes state only at t=0 (optional saved integrated checkpoint); all subsequent
outputs and flaps move through the solver. Completion is never proof of hardware.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import numpy as np
import mujoco as mj

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "simulation"))
from dynamics import Dynamics, contact_settings, solver_settings


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(directory):
    Dynamics.clear(); directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    signature = hashlib.sha256((directory / "model.xml").read_bytes())
    for path in sorted((directory / "assets").glob("*.stl")): signature.update(path.read_bytes())
    stamp = {"sha256": signature.hexdigest(), "mujoco": mj.__version__}
    cache = directory / "model.mjb"; stampfile = directory / "compiled.json"
    if cache.exists() and stampfile.exists() and json.loads(stampfile.read_text()) == stamp:
        model = mj.MjModel.from_binary_path(str(cache))
    else:
        model = mj.MjModel.from_xml_path(str(directory / "model.xml"))
        mj.mj_saveModel(model, str(cache), None); stampfile.write_text(json.dumps(stamp))
    contact_settings(model); solver_settings(model)
    dynamics = Dynamics(model, manifest)
    # Torque is directly limited by the one input motor. No user gain callback:
    # this is a current/torque-controlled motor envelope, not a 28BYJ phase model.
    mj.set_mjcb_passive(dynamics.passive)
    data = mj.MjData(model); mj.mj_forward(model, data)
    return model, data, dynamics, manifest


class Controller:
    def __init__(self, model, data, args):
        self.args = args; self.model = model
        self.adr = {mj.mj_id2name(model, mj.mjtObj.mjOBJ_JOINT, j): (int(model.jnt_qposadr[j]), int(model.jnt_dofadr[j])) for j in range(model.njnt)}
        self.stage = "settle"; self.events = []; self.ierror = 0.; self.command_v = 0.; self.phase_start = float(data.time)
        self.baseline = None; self.target = None; self.completed = 0
        self.results = []
        self.cycle = 1

    def q(self, data, b): return float(data.qpos[self.adr[b][0]])
    def v(self, data, b): return float(data.qvel[self.adr[b][1]])
    def switch(self, stage, data):
        self.stage = stage; self.phase_start = float(data.time); self.ierror = 0.; self.command_v = 0.
        self.events.append({"time_s": float(data.time), "stage": stage, "I_deg": float(np.rad2deg(self.q(data, "I"))), "M_deg": float(np.rad2deg(self.q(data, "M"))), "H_deg": float(np.rad2deg(self.q(data, "H")))})
        print("stage", self.events[-1], flush=True)

    def __call__(self, data):
        args = self.args; now = float(data.time)
        if args.case == "gravity": return 0.
        if self.stage == "settle":
            if now >= args.settle:
                self.baseline = {b: self.q(data, b) for b in ("M", "H")}
                self.target = np.deg2rad(6 * (round(np.rad2deg(self.baseline["M"]) / 6) - args.minute_steps))
                self.switch("M_drive", data)
            return 0.
        if self.stage.endswith("_drive"):
            b = self.stage[0]; err = self.target - self.q(data, b)
            input_sign = 1 if b == "M" else -2 / 3
            # Only negative output movement is requested. Slow near the passive
            # detent's basin; release torque before the nominal target angle.
            speed_out = -min(args.speed, max(0., 4 * (-err - np.deg2rad(args.release_deg))))
            desired = input_sign * speed_out
            dv = np.clip(desired - self.command_v, -.8 * self.model.opt.timestep, .8 * self.model.opt.timestep)
            self.command_v += float(dv)
            if -err <= np.deg2rad(args.release_deg) or now - self.phase_start > args.drive_timeout:
                self.stop_reason = "capture_basin" if -err <= np.deg2rad(args.release_deg) else "timeout"
                self.switch(b + "_coast", data); return 0.
            velocity_error = self.command_v - self.v(data, "I")
            candidate = self.ierror + velocity_error * self.model.opt.timestep
            torque = args.velocity_kp * velocity_error + args.velocity_ki * candidate
            if abs(torque) <= args.torque_limit: self.ierror = candidate
            # Finite torque-speed envelope: zero motoring torque at no-load
            # speed. Regenerative braking remains limited by the same 25mNm.
            if torque * self.v(data, "I") > 0:
                limit = args.torque_limit * max(0., 1 - abs(self.v(data, "I")) / 3)
                return float(np.clip(torque, -limit, limit))
            return float(np.clip(torque, -args.torque_limit, args.torque_limit))
        if self.stage.endswith("_coast"):
            if now - self.phase_start >= args.coast:
                b = self.stage[0]; inactive = "H" if b == "M" else "M"
                self.results.append({"branch": b, "cycle": self.cycle, "target_deg": float(np.rad2deg(self.target)), "final_deg": float(np.rad2deg(self.q(data, b))),
                                     "travel_deg": float(np.rad2deg(self.q(data, b) - self.baseline[b])),
                                     "step_error_deg": float(np.rad2deg(self.q(data, b) - self.baseline[b])) + (6 * args.minute_steps if b == "M" else 15 * args.hour_steps),
                                     "error_deg": float(np.rad2deg(self.q(data, b) - self.target)), "inactive_drift_deg": float(np.rad2deg(self.q(data, inactive) - self.baseline[inactive])), "coast_seconds": args.coast, "drive_end_reason": self.stop_reason})
                if b == "M" and args.case == "drive":
                    self.baseline = {b_: self.q(data, b_) for b_ in ("M", "H")}
                    self.target = np.deg2rad(15 * (round(np.rad2deg(self.baseline["H"]) / 15) - args.hour_steps))
                    self.switch("H_drive", data)
                elif b == "H" and self.cycle < args.cycles:
                    self.cycle += 1
                    self.baseline = {b_: self.q(data, b_) for b_ in ("M", "H")}
                    self.target = np.deg2rad(6 * (round(np.rad2deg(self.baseline["M"]) / 6) - args.minute_steps))
                    self.switch("M_drive", data)
                else:
                    self.switch("done", data)
            return 0.
        return 0.


def run(args):
    directory = Path(args.model_dir).resolve() if args.model_dir else ROOT / "simulation" / "generated" / "full"
    manifest = json.loads((directory / "manifest.json").read_text())
    if args.torque_limit is None: args.torque_limit = manifest["motor"]["stall_torque_Nm"]
    if not args.model_dir:
        for rel, value in manifest["sources_sha256"].items():
            if sha(ROOT / rel) != value: raise ValueError("Stale CAD/model input: " + rel)
    elif sha(directory / "model.xml") != manifest["model_sha256"]:
        raise ValueError("Archived physics model hash mismatch")
    model, data, dynamics, manifest = load(directory)
    model.opt.timestep = args.dt; model.opt.gravity[:] = [0, 0, -args.gravity]
    model.actuator_ctrlrange[0] = [-args.torque_limit, args.torque_limit]
    model.actuator_forcerange[0] = [-args.torque_limit, args.torque_limit]
    model.geom_friction[:, 0] = args.friction
    if args.output_drag is not None or args.hour_output_drag is not None:
        for name in ("M", "H"):
            joint = mj.mj_name2id(model, mj.mjtObj.mjOBJ_JOINT, name)
            value = args.hour_output_drag if name == "H" and args.hour_output_drag is not None else args.output_drag
            if value is not None: model.dof_frictionloss[model.jnt_dofadr[joint]] = value
    if args.trial_plate_thickness is not None:
        # Diagnostic isolation of plate packing ONLY. Original CAD inertia is
        # retained deliberately. This variant cannot qualify a manufactured part.
        for geom in range(model.ngeom):
            name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, geom) or ""
            if name.startswith(("FM_", "FH_")) and name.endswith("_plate"):
                model.geom_size[geom, 1] = args.trial_plate_thickness * .0005
    for spec, _, _, _ in dynamics.springs:
        spec["stiffness_N_m"] *= args.spring_scale
    if args.checkpoint:
        state = np.load(args.checkpoint, allow_pickle=False)
        data.qpos[:] = state["qpos"]; data.qvel[:] = state["qvel"]
        mj.mj_forward(model, data)
    else:
        # One-time initial assembly pose, 2 degrees clear of the retaining wire.
        # This is recorded in q0. No pose/velocity writes occur in integration.
        for j in range(model.njnt):
            name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_JOINT, j) or ""
            if name.startswith(("FM_", "FH_")):
                data.qpos[model.jnt_qposadr[j]] = np.deg2rad(args.initial_flap_bias_deg)
        mj.mj_forward(model, data)
    if model.neq or model.nu != 1: raise ValueError("Unexpected output constraint/actuator")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + args.case
    output = ROOT / "runs" / run_id; output.mkdir(parents=True)
    print("RUN_START", run_id, flush=True)
    # Snapshot model/source once; each run is self-contained and reproducible.
    shutil.copytree(directory, output / "model", ignore=shutil.ignore_patterns("*.mjb", "compiled.json", "model_full.xml"))
    (output / "source").mkdir()
    for path in (Path(__file__), ROOT / "simulation" / "export_r2.py", ROOT / "src" / "r2_geometry.py", ROOT / "parameters.json", ROOT.parent / "simulation" / "dynamics.py", ROOT.parent / "simulation" / "collision.py", ROOT.parent / "simulation" / "export_model.py"):
        shutil.copy2(path, output / "source" / path.name)
    if args.model_dir and (directory.parent / "source").is_dir():
        for path in (directory.parent / "source").iterdir():
            if path.is_file() and path.name != "calibrate.py": shutil.copy2(path, output / "source" / path.name)
    controller = Controller(model, data, args)
    q0 = data.qpos.copy(); v0 = data.qvel.copy()
    times = [0.]; qs = [q0.copy()]; vs = [v0.copy()]; controls = [0.]; stages = ["settle"]; points = [[]]; contacts = [int(data.ncon)]
    frame_next = 1 / 60; sample_next = 0.; force = np.zeros(6); stats = defaultdict(lambda: {"sample_count": 0, "peak_force_N": 0., "peak_penetration_mm": 0.})
    initial_pen = max((-c.dist * 1000 for c in data.contact), default=0.); peak_pen = max(0., initial_pen); maxiter = 0; limits = 0
    trajectory = []; work = 0.; start = time.perf_counter(); last_progress = start; status = "COMPLETED"; failure = None
    nsteps = int(args.duration / args.dt)
    for step in range(nsteps):
        data.ctrl[0] = controller(data); old_q = controller.q(data, "I")
        mj.mj_step(model, data)
        work += float(data.actuator_force[0]) * (controller.q(data, "I") - old_q)
        pen = max((-c.dist * 1000 for c in data.contact), default=0.); peak_pen = max(peak_pen, pen)
        niter = int(np.max(data.solver_niter)); maxiter = max(maxiter, niter); limits += int(niter >= model.opt.iterations)
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all(): status = "FAILED"; failure = "nonfinite_state"; break
        if any(data.warning[i].number for i in (int(mj.mjtWarning.mjWARN_BADQPOS), int(mj.mjtWarning.mjWARN_BADQVEL), int(mj.mjtWarning.mjWARN_BADQACC))): status = "FAILED"; failure = "engine_state_warning"; break
        if data.time >= sample_next:
            trajectory.append([float(data.time), float(data.ctrl[0]), float(data.actuator_force[0]), int(data.ncon), pen] + [controller.q(data, b) for b in ("I", "M", "H")] + [controller.v(data, b) for b in ("I", "M", "H")])
            for ci, c in enumerate(data.contact):
                mj.mj_contactForce(model, data, ci, force)
                pair = " / ".join(sorted(mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[k])) or "world" for k in (c.geom1, c.geom2)))
                r = stats[pair]; r["sample_count"] += 1; r["peak_force_N"] = max(r["peak_force_N"], abs(float(force[0]))); r["peak_penetration_mm"] = max(r["peak_penetration_mm"], -float(c.dist) * 1000)
            sample_next += .005
        if data.time + args.dt / 2 >= frame_next:
            times.append(float(data.time)); qs.append(data.qpos.copy()); vs.append(data.qvel.copy()); controls.append(float(data.ctrl[0])); stages.append(controller.stage); contacts.append(int(data.ncon))
            points.append([[*map(float, c.pos), -float(c.dist)] for c in data.contact]); frame_next += 1 / 60
        if time.perf_counter() - last_progress > 15:
            print(f"t={data.time:.3f}s {controller.stage} I/M/H=" + str([round(np.rad2deg(controller.q(data, b)), 3) for b in ("I", "M", "H")]) + f" contacts={data.ncon} penetration={pen:.4f}mm", flush=True)
            last_progress = time.perf_counter()
        if controller.stage == "done": break
    names = [mj.mj_id2name(model, mj.mjtObj.mjOBJ_JOINT, j) for j in range(model.njnt)]
    summary = {"status": status, "failure": failure, "run_id": run_id, "engine": "MuJoCo", "version": mj.__version__, "simulated_duration_s": float(data.time), "wall_seconds": time.perf_counter() - start,
               "steps": step + 1, "initial_penetration_mm": max(0., initial_pen), "peak_penetration_mm": peak_pen, "max_solver_iterations": maxiter, "iteration_limit_steps": limits,
               "warnings": {mj.mjtWarning(i).name: int(w.number) for i, w in enumerate(data.warning) if w.number}, "motor_work_J": work, "events": controller.events, "results": controller.results,
               "finished_controller": controller.stage == "done", "joints": names, "q0": q0.tolist(), "q_final": data.qpos.tolist(), "nbody": model.nbody, "nq": model.nq, "nu": model.nu, "neq": model.neq,
               "calibrated_hardware": False, "manufacturing_ready": False, "assumed_feedback": "Perfect simulated input and final-output encoders; no measured sensor noise or electronic latency"}
    summary["diagnostic_geometry_override"] = args.trial_plate_thickness is not None
    np.savez_compressed(output / "states.npz", time_s=times, qpos=np.asarray(qs), qvel=np.asarray(vs), input_torque_Nm=controls, stage=np.asarray(stages), contacts=contacts)
    np.savez_compressed(output / "checkpoint.npz", qpos=data.qpos, qvel=data.qvel, model_sha256=sha(directory / "model.xml"))
    np.savetxt(output / "trajectory.csv", np.asarray(trajectory), delimiter=",", header="time_s,ctrl_Nm,actual_input_torque_Nm,contacts,penetration_mm,I_rad,M_rad,H_rad,I_rad_s,M_rad_s,H_rad_s", comments="")
    for name, obj in (("summary.json", summary), ("contact_pairs.json", stats), ("contact_points.json", points), ("run_config.json", {**vars(args), "source_sha256": sha(output / "source" / "calibrate.py"), "model_sha256": sha(directory / "model.xml"), "controller_source": "source/calibrate.py", "units": "SI"})):
        (output / name).write_text(json.dumps(obj, indent=2), encoding="utf-8")
    (ROOT / "reports" / "latest_run.json").write_text(json.dumps({"directory": str(output.relative_to(ROOT)).replace("\\", "/"), "run_id": run_id}, indent=2))
    print(json.dumps({k: summary[k] for k in ("run_id", "status", "simulated_duration_s", "wall_seconds", "initial_penetration_mm", "peak_penetration_mm", "results", "finished_controller", "warnings")}, indent=2), flush=True)
    Dynamics.clear()
    return 0 if status == "COMPLETED" else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--case", choices=("drive", "minute", "gravity"), default="drive")
    ap.add_argument("--duration", type=float, default=6); ap.add_argument("--dt", type=float, default=.00005); ap.add_argument("--gravity", type=float, default=9.81)
    ap.add_argument("--friction", type=float, default=.25); ap.add_argument("--spring-scale", type=float, default=1)
    ap.add_argument("--speed", type=float, default=.22); ap.add_argument("--release-deg", type=float, default=.65)
    ap.add_argument("--settle", type=float, default=.6); ap.add_argument("--coast", type=float, default=.7); ap.add_argument("--drive-timeout", type=float, default=3)
    ap.add_argument("--minute-steps", type=int, default=1); ap.add_argument("--hour-steps", type=int, default=1); ap.add_argument("--checkpoint")
    ap.add_argument("--initial-flap-bias-deg", type=float, default=2)
    ap.add_argument("--torque-limit", type=float)
    ap.add_argument("--velocity-kp", type=float, default=.02); ap.add_argument("--velocity-ki", type=float, default=.15)
    ap.add_argument("--trial-plate-thickness", type=float)
    ap.add_argument("--model-dir")
    ap.add_argument("--cycles", type=int, default=1)
    ap.add_argument("--output-drag", type=float)
    ap.add_argument("--hour-output-drag", type=float)
    raise SystemExit(run(ap.parse_args()))
