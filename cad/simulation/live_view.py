"""Launch the native MuJoCo physics window; no prescribed output motion."""
from __future__ import annotations
import json
import gzip
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
        with gzip.open(run/"contact_points.json.gz","rt",encoding="utf-8") as stream:contact_points=json.load(stream)
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
        control={"index":0,"paused":False,"contacts":False}
        opaque=m.geom_rgba[:,3].copy()
        def on_key(key):
            if key in (80,112):control["paused"]=not control["paused"]
            elif key==262:control["index"]=(control["index"]+1)%len(states["time"]);control["paused"]=True
            elif key==263:control["index"]=(control["index"]-1)%len(states["time"]);control["paused"]=True
            elif key in (82,114):control["index"]=0
            elif key in (67,99):control["contacts"]=not control["contacts"]
        with mj.viewer.launch_passive(m,d,key_callback=on_key,show_left_ui=False,show_right_ui=False) as viewer:
            viewer.cam.lookat[:]=camera().lookat;viewer.cam.distance=.49;viewer.cam.azimuth=-70;viewer.cam.elevation=-23
            viewer.opt.geomgroup[:]=[1,1,1,0,0,0]
            while viewer.is_running():
                tick=time.perf_counter()
                with viewer.lock():
                    index=control["index"]
                    d.qpos[:]=states["qpos"][index];d.qvel[:]=states["qvel"][index];d.time=float(states["time"][index])
                    from runner import request_at
                    d.ctrl[0]=request_at(config["case"],d.time,config["requested_duration_s"])*config["torque_scale"];mj.mj_forward(m,d)
                    viewer.opt.flags[mj.mjtVisFlag.mjVIS_CONTACTPOINT]=False
                    m.geom_rgba[:,3]=opaque
                    if control["contacts"]:
                        for gid in range(m.ngeom):
                            if opaque[gid]>0 and m.geom_group[gid] in (0,2) and mj.mj_id2name(m,mj.mjtObj.mjOBJ_GEOM,gid)!="floor":m.geom_rgba[gid,3]=opaque[gid]*.25
                    viewer.user_scn.ngeom=0
                    if control["contacts"]:
                        for point in contact_points[index]:
                            if viewer.user_scn.ngeom>=viewer.user_scn.maxgeom:break
                            geom=viewer.user_scn.geoms[viewer.user_scn.ngeom]
                            mj.mjv_initGeom(geom,mj.mjtGeom.mjGEOM_SPHERE,np.array([.0008]*3),np.array(point[:3]),np.eye(3).reshape(-1),np.array([1.,.1,.08,1.]))
                            viewer.user_scn.ngeom+=1
                viewer.set_texts([(None,None,"FC-R1 | RECORDED PHYSICS | 0.25x | "+("PAUSED" if control["paused"] else "PLAY"),f"t={d.time:.3f}s  g={abs(config['gravity_m_s2'][2]):.2f} m/s^2\nP: pause/play   Arrows: frame   R: restart   C: contacts/xray\nMouse: orbit/zoom | Uncalibrated prototype")])
                viewer.sync()
                if not control["paused"]:control["index"]=(control["index"]+1)%len(states["time"])
                time.sleep(max(0,1/30-(time.perf_counter()-tick)))
    else:
        m.opt.timestep=.00005
        seed_flaps(m,d,0)
        print("LIVE PHYSICS: Space pause, right panel Control slider -1..+1, mouse orbit/zoom; input torque limited to 0.025 N m.",flush=True)
        # Managed viewer owns actual mj_step integration, native pause and speed
        # controls. Dynamics callbacks supply forces, never motion targets.
        mj.viewer.launch(model=m,data=d)
    return 0
