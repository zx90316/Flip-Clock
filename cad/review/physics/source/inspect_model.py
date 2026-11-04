"""Inspect compilation and initial contacts; retained diagnostic, not acceptance."""
import json
from pathlib import Path
import sys
import time
import numpy as np
import mujoco as mj
from dynamics import load_model,seed_flaps

root=Path(__file__).resolve().parents[1]
scope=sys.argv[1] if len(sys.argv)>1 else "clutch"
started=time.perf_counter()
print("LOAD "+scope,flush=True)
m,d,dynamics,manifest=load_model(root/"simulation"/"generated"/scope)
seed_flaps(m,d)
print(json.dumps({"scope":scope,"compile_seconds":time.perf_counter()-started,"bodies":m.nbody,"joints":m.njnt,"geoms":m.ngeom,"meshes":m.nmesh,"initial_contacts":d.ncon}),flush=True)
def contacts():
    return sorted([{"a":mj.mj_id2name(m,mj.mjtObj.mjOBJ_GEOM,c.geom1),"b":mj.mj_id2name(m,mj.mjtObj.mjOBJ_GEOM,c.geom2),"distance_mm":float(c.dist*1000)} for c in d.contact],key=lambda r:r["distance_mm"])
initial=contacts()
for row in initial[:24]:print(json.dumps(row),flush=True)
started=time.perf_counter()
mj.set_mjcb_time(time.perf_counter)
peak=0.
steps=int(sys.argv[2]) if len(sys.argv)>2 else 100
for i in range(steps):
    mj.mj_step(m,d)
    peak=max(peak,max((-c.dist for c in d.contact),default=0))
print(json.dumps({"simulation_seconds":d.time,"wall_seconds":time.perf_counter()-started,"peak_penetration_mm":peak*1000,"contacts":d.ncon,"finite":bool(np.isfinite(d.qpos).all()),"qpos":d.qpos[:12].tolist()}),flush=True)
print(json.dumps({mj.mjTIMERSTRING[i]:{"seconds":float(v.duration),"count":int(v.number)} for i,v in enumerate(d.timer)}),flush=True)
report={"scope":scope,"initial_contacts":initial,"final_contacts":contacts(),"peak_penetration_mm":peak*1000}
(root/"tmp"/"physics"/("initial_"+scope+".json")).write_text(json.dumps(report,indent=2),encoding="utf-8")

