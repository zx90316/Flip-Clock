"""Small independently checkable engine tests, not clock acceptance tests."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import mujoco as mj

ROOT=Path(__file__).resolve().parents[1]


def run_selftests():
    records=[]
    def check(name,value,passed,criterion):
        records.append({"id":name,"status":"PASS" if passed else "FAIL","value":value,"criterion":criterion})
        print(json.dumps(records[-1]),flush=True)
    xml='''<mujoco><option timestep="0.000025" gravity="0 0 -9.81" integrator="implicitfast"/>
      <default><geom solref=".0001 1" solimp=".99 .999 .0001"/></default><worldbody>
      <geom name="floor" type="plane" size=".1 .1 .01" friction=".25 .001 .0001"/>
      <body pos="0 0 .02"><freejoint/><geom name="ball" type="sphere" size=".005" mass=".01" friction=".25 .001 .0001"/></body>
      </worldbody></mujoco>'''
    m=mj.MjModel.from_xml_string(xml);d=mj.MjData(m)
    for _ in range(1200):mj.mj_step(m,d)
    expected=.02-.5*9.81*.03**2
    err=abs(float(d.qpos[2])-expected)
    check("freefall_analytic",{"z_m":float(d.qpos[2]),"analytic_z_m":expected,"error_m":err},err<1e-5,"error < 10 micrometres at t=0.03s")
    peak=0
    for _ in range(12000):
        mj.mj_step(m,d)
        peak=max(peak,max((-c.dist for c in d.contact),default=0))
    check("floor_contact",{"z_m":float(d.qpos[2]),"contacts":int(d.ncon),"max_penetration_m":peak},abs(float(d.qpos[2])-.005)<5e-5 and d.ncon>0 and peak<5e-5,"ball retained by floor; final position and peak penetration <0.05 mm")
    slide='''<mujoco><option timestep=".00005"/><worldbody><geom type="plane" size="1 1 .1" friction=".3 .001 .0001"/>
      <body pos="0 0 .005"><freejoint/><geom type="box" size=".005 .005 .005" mass=".02" friction=".3 .001 .0001" solref=".001 1"/></body></worldbody></mujoco>'''
    m=mj.MjModel.from_xml_string(slide);d=mj.MjData(m);d.qvel[0]=.1
    for _ in range(4000):mj.mj_step(m,d)
    check("friction_dissipation",{"final_vx_m_s":float(d.qvel[0])},abs(float(d.qvel[0]))<.01,"dry friction arrests initial 0.1 m/s slide")
    spring='''<mujoco><option timestep=".00005" gravity="0 0 0"/><worldbody><body><joint type="hinge" axis="1 0 0" stiffness=".005" damping=".0001"/>
      <inertial pos="0 0 0" mass=".01" diaginertia=".000001 .000001 .000001"/><geom type="box" size=".005 .01 .005"/></body></worldbody></mujoco>'''
    m=mj.MjModel.from_xml_string(spring);d=mj.MjData(m);d.qpos[0]=.2
    for _ in range(8000):mj.mj_step(m,d)
    check("spring_restoring",{"final_angle_rad":float(d.qpos[0])},abs(float(d.qpos[0]))<.005,"0.2 rad initial spring deflection decays toward rest")
    finite='''<mujoco><option timestep=".00005" gravity="0 0 0"/><worldbody><body><joint name="j" type="hinge" axis="1 0 0"/>
      <inertial pos="0 0 0" mass=".01" diaginertia=".0001 .0001 .0001"/><geom type="box" size=".005 .01 .005"/></body></worldbody>
      <actuator><motor joint="j" ctrlrange="-.002 .002" forcerange="-.002 .002"/></actuator></mujoco>'''
    m=mj.MjModel.from_xml_string(finite);a=mj.MjData(m);b=mj.MjData(m)
    a.ctrl[0]=b.ctrl[0]=.002
    for _ in range(1000):
        b.qfrc_applied[0]=-.004
        mj.mj_step(m,a);mj.mj_step(m,b)
    check("finite_torque_not_position_constraint",{"unloaded_rad":float(a.qpos[0]),"overloaded_rad":float(b.qpos[0])},a.qpos[0]>0 and b.qpos[0]<0,"opposing load exceeding torque limit prevents forward progress")
    render_status="NOT_RUN"
    try:
        with mj.Renderer(m,height=360,width=640) as renderer:
            renderer.update_scene(a)
            frame=renderer.render()
            from PIL import Image
            output=ROOT/"tmp"/"physics"/"engine_render.png";output.parent.mkdir(parents=True,exist_ok=True)
            Image.fromarray(frame).save(output)
            render_status="PASS"
            check("offscreen_renderer",{"size":[int(frame.shape[1]),int(frame.shape[0])]},True,"OpenGL renderer produced a 640x360 RGB frame")
    except Exception as exc:
        check("offscreen_renderer",str(exc),False,"working renderer required for video")
    report={"engine":"MuJoCo","version":mj.__version__,"python":sys.version,"interpreter":sys.executable,
            "status":"PASS" if all(r["status"]=="PASS" for r in records) else "FAIL",
            "tests":records,"clock_physics_verified":False,"scope":"engine self-tests only"}
    (ROOT/"reports"/"physics_engine_selftest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"interpreter":sys.executable,"version":mj.__version__}),flush=True)
    return 0 if report["status"]=="PASS" else 1
