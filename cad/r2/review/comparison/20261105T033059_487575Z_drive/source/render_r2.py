"""Render recorded MuJoCo states and contact points; never generate motion."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import mujoco as mj
import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "simulation"))
from render import contact_overlay
from calibrate import load


def font(size):
    return ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", size)


def render(run, snapshot=False):
    run = Path(run).resolve(); states = np.load(run / "states.npz", allow_pickle=False)
    summary = json.loads((run / "summary.json").read_text()); cfg = json.loads((run / "run_config.json").read_text())
    points = json.loads((run / "contact_points.json").read_text())
    measured = [r for r in summary.get("results", []) if r.get("cycle") == 2]
    passed = len(measured) == 2 and all(abs(r["error_deg"]) < (.25 if r["branch"] == "M" else .4) and abs(r["inactive_drift_deg"]) < .25 and r.get("drive_end_reason") != "timeout" for r in measured) and summary["peak_penetration_mm"] < .2
    model, data, dyn, manifest = load(run / "model")
    # Restore the runtime assumptions before forwarding recorded states. These
    # parameters were applied after XML loading during the actual integration.
    model.opt.timestep = cfg["dt"]; model.opt.gravity[:] = [0, 0, -cfg["gravity"]]
    model.geom_friction[:, 0] = cfg["friction"]
    model.actuator_ctrlrange[0] = [-cfg["torque_limit"], cfg["torque_limit"]]
    model.actuator_forcerange[0] = [-cfg["torque_limit"], cfg["torque_limit"]]
    for branch in ("M", "H"):
        value = cfg.get("hour_output_drag") if branch == "H" and cfg.get("hour_output_drag") is not None else cfg.get("output_drag")
        if value is not None:
            joint = mj.mj_name2id(model, mj.mjtObj.mjOBJ_JOINT, branch)
            model.dof_frictionloss[model.jnt_dofadr[joint]] = value
    for spec, _, _, _ in dyn.springs:
        spec["stiffness_N_m"] *= cfg["spring_scale"]
    opt = mj.MjvOption(); mj.mjv_defaultOption(opt); opt.geomgroup[:] = [1, 1, 1, 0, 1, 0]
    opt.flags[mj.mjtVisFlag.mjVIS_CONTACTPOINT] = False
    names = summary["joints"]; adr = {name: int(model.jnt_qposadr[i]) for i, name in enumerate(names)}
    titlefont = font(29); textfont = font(23); smallfont = font(19)
    frames = len(states["time_s"])
    with mj.Renderer(model, height=720, width=1280, max_geom=16000) as renderer:
        for kind in ("desktop", "cutaway", "front"):
            cam = mj.MjvCamera(); mj.mjv_defaultCamera(cam)
            cam.lookat[:] = [0, -.024 if kind != "front" else .025, .061]
            cam.distance = .26 if kind == "cutaway" else .245 if kind == "desktop" else .205
            cam.azimuth = 105 if kind == "cutaway" else -67 if kind == "desktop" else -90
            cam.elevation = -25 if kind != "front" else -5
            opt.geomgroup[4] = 0 if kind == "cutaway" else 1
            indices = [frames - 1] if snapshot else list(range(0, frames, 1))
            writer = None if snapshot else imageio.get_writer(str(run / (kind + ".mp4")), fps=30, codec="libx264", quality=8, macro_block_size=16, ffmpeg_log_level="error", output_params=["-movflags", "+faststart", "-pix_fmt", "yuv420p"])
            last = None
            try:
                for idx in indices:
                    data.qpos[:] = states["qpos"][idx]; data.qvel[:] = states["qvel"][idx]; data.time = float(states["time_s"][idx]); mj.mj_forward(model, data)
                    renderer.update_scene(data, camera=cam, scene_option=opt)
                    if kind == "front": renderer.scene.flags[mj.mjtRndFlag.mjRND_SHADOW] = False
                    raw = Image.fromarray(renderer.render())
                    if kind == "cutaway": contact_overlay(raw, renderer.scene, points[idx])
                    canvas = Image.new("RGB", (1280, 896), "#F0F1ED"); canvas.paste(raw, (0, 88)); draw = ImageDraw.Draw(canvas)
                    draw.text((26, 12), "FC-R2 桌面翻頁鐘｜" + ("機構剖視與實際接觸" if kind == "cutaway" else "重力與物理碰撞"), font=titlefont, fill="#203039")
                    state_label = "參數試驗" if cfg.get("output_drag") is not None or cfg.get("trial_plate_thickness") is not None else "原型整定"
                    state_label += "｜本輪物理驗收未通過" if not passed else "｜尚待實機校準"
                    draw.text((26, 52), f"g={cfg['gravity']:.2f} · {states['time_s'][idx]:.3f}s · 慢放0.5× · {state_label}", font=smallfont, fill="#8A4A2E" if not passed else "#52616A")
                    m = np.rad2deg(data.qpos[adr["M"]]); h = np.rad2deg(data.qpos[adr["H"]]); torque = states["input_torque_Nm"][idx]
                    draw.text((26, 816), f"分鐘輪 {m:+.3f}°     小時輪 {h:+.3f}°     馬達扭矩 {torque * 1000:+.2f} mN·m", font=textfont, fill="#203039")
                    draw.text((26, 855), "模擬參數尚未實測校準；僅輸入軸施力，翻片與輸出輪由重力、接觸和彈簧運動。", font=smallfont, fill="#8A4A2E")
                    if writer is not None: writer.append_data(np.asarray(canvas))
                    last = canvas
                if last is not None:
                    last.save(run / (kind + ".png"))
                    if writer is not None:
                        for _ in range(24): writer.append_data(np.asarray(last))
            finally:
                if writer is not None: writer.close()
            print("rendered", kind, flush=True)
    source = Path(__file__).read_bytes()
    (run / "source" / "render_r2.py").write_bytes(source)
    (run / "render_provenance.json").write_text(json.dumps({"source_sha256": hashlib.sha256(source).hexdigest(), "input_states_sha256": hashlib.sha256((run / "states.npz").read_bytes()).hexdigest(), "runtime_parameters_restored_from": "run_config.json", "source_timebase": "60 Hz recorded solver states, played 30 fps", "snapshot_only": snapshot, "engine": mj.__version__}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--snapshot", action="store_true")
    args = ap.parse_args(); render(args.run, args.snapshot)
