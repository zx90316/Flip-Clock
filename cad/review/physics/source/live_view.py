"""Launch the native MuJoCo physics window; no prescribed output motion."""
from __future__ import annotations
import json
from pathlib import Path
import time
import numpy as np
import mujoco as mj
import mujoco.viewer
from dynamics import load_model,seed_flaps,contact_settings,solver_settings
from render import camera

ROOT=Path(__file__).resolve().parents[1]


def launch(args):
    if args.command=="replay":
        run=Path(args.run).resolve();directory=run/"model"
        config=json.loads((run/"run_config.json").read_text(encoding="utf-8"));states=np.load(run/"states.npz",allow_pickle=False)
    else:
        directory=ROOT/"simulation"/"generated"/args.scope
        if not (directory/"model.xml").exists():
            from export_model import build_model
            build_model(args.scope)
    m,d,dynamics,manifest=load_model(directory)
    if args.command=="replay":
        m.opt.timestep=config["timestep_s"];m.opt.gravity[:]=config["gravity_m_s2"]
        if isinstance(config.get("contact_model"),dict):contact_settings(m,config["contact_model"]["solref"][0])
        if isinstance(config.get("solver"),dict):solver_settings(m,config["solver"]["algorithm"],config["solver"]["iterations"])
        with mj.viewer.launch_passive(m,d) as viewer:
            viewer.cam.lookat[:]=camera().lookat;viewer.cam.distance=.49;viewer.cam.azimuth=70;viewer.cam.elevation=-23
            viewer.opt.geomgroup[:]=[1,1,1,0,0,0];viewer.opt.flags[mj.mjtVisFlag.mjVIS_CONTACTPOINT]=True
            viewer.set_texts([(None,None,"FC-R1 | RECORDED PHYSICS REPLAY | 0.25x","Gravity and collision solver output; uncalibrated parameters")])
            index=0
            while viewer.is_running():
                tick=time.perf_counter()
                with viewer.lock():
                    d.qpos[:]=states["qpos"][index];d.qvel[:]=states["qvel"][index];d.time=float(states["time"][index]);mj.mj_forward(m,d)
                viewer.sync();index=(index+1)%len(states["time"])
                time.sleep(max(0,1/30-(time.perf_counter()-tick)))
    else:
        seed_flaps(m,d,0)
        print("LIVE PHYSICS: Space pause, right panel Control slider -1..+1, mouse orbit/zoom; input torque limited to 0.025 N m.",flush=True)
        # Managed viewer owns actual mj_step integration, native pause and speed
        # controls. Dynamics callbacks supply forces, never motion targets.
        mj.viewer.launch(model=m,data=d)
    return 0

