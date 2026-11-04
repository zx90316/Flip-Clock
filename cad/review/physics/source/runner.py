"""Record actual MuJoCo integration, forces and states for audit and replay."""
from __future__ import annotations
from collections import defaultdict
import csv
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import time
import numpy as np
import mujoco as mj
from dynamics import load_model,seed_flaps,contact_settings,solver_settings

ROOT=Path(__file__).resolve().parents[1]


def request_at(case,t,duration):
    if case=="gravity":return 0.
    if case=="drive":
        if .60<=t<.90:return 1.
        if 1.05<=t<1.35:return -1.
        return 0.
    if case=="clutch_forward":return 1. if .05<=t<duration-.1 else 0.
    if case=="clutch_reverse":return -1. if .05<=t<duration-.1 else 0.
    raise ValueError("Unknown case: "+case)


def run_case(args):
    directory=ROOT/"simulation"/"generated"/args.scope
    if not (directory/"model.xml").exists():
        from export_model import build_model
        build_model(args.scope)
    # Refuse stale geometry instead of silently simulating another revision.
    manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
    for key,path in (("cad_sha256",ROOT/"STEP"/"assembly.step"),("geometry_source_sha256",ROOT/"src"/"geometry.py"),("parameters_sha256",ROOT/"config"/"parameters.yaml")):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest[key]:raise ValueError("Stale model: rebuild before running ("+key+")")
    run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")+"_"+args.scope+"_"+args.case
    output=ROOT/"runs"/run_id;output.mkdir(parents=True)
    m,d,dynamics,manifest=load_model(directory)
    shutil.copytree(directory,output/"model")
    source=output/"source";source.mkdir()
    for path in (ROOT/"simulation").glob("*.py"):shutil.copy2(path,source/path.name)
    m.opt.timestep=args.dt;m.opt.gravity[:]=[0,0,-args.gravity]
    contact_settings(m,args.contact_time)
    solver_settings(m,args.solver,args.iterations)
    if args.no_pawl_contact:
        for geom in range(m.ngeom):
            body=mj.mj_id2name(m,mj.mjtObj.mjOBJ_BODY,int(m.geom_bodyid[geom])) or ""
            if body.startswith("pawl_"):m.geom_contype[geom]=m.geom_conaffinity[geom]=0
    seed_flaps(m,d,args.seed)
    if m.neq!=0 or m.nu!=1:raise ValueError("Only one finite input actuator, no equality/gear constraints, expected")
    names=[mj.mj_id2name(m,mj.mjtObj.mjOBJ_JOINT,i) for i in range(m.njnt)]
    qadr=[int(m.jnt_qposadr[i]) for i in range(m.njnt)]
    vadr=[int(m.jnt_dofadr[i]) for i in range(m.njnt)]
    initial_q=d.qpos.copy();initial_v=d.qvel.copy()
    geom_names=[mj.mj_id2name(m,mj.mjtObj.mjOBJ_GEOM,i) or str(i) for i in range(m.ngeom)]
    body_names=[mj.mj_id2name(m,mj.mjtObj.mjOBJ_BODY,i) or str(i) for i in range(m.nbody)]
    config={"run_id":run_id,"case":args.case,"scope":args.scope,"engine":"MuJoCo","version":mj.__version__,
        "requested_duration_s":args.duration,"timestep_s":args.dt,"gravity_m_s2":[0,0,-args.gravity],"seed":args.seed,
        "initial_flap_perturbation_deg":.1,"initialization":"One-time seeded CAD-pose perturbation; zero initial velocities.",
        "pawl_contacts_enabled":not args.no_pawl_contact,"torque_scale":args.torque_scale,
        "motor_schedule":"No prescribed output angles; input ctrl=request_at(case,t), torque-speed callback finite.",
        "joints":names,"nbody":m.nbody,"nq":m.nq,"nv":m.nv,"ngeom":m.ngeom,"equality_constraints":m.neq,"actuators":m.nu,
        "parent_child_collision_enabled":bool(m.opt.disableflags & mj.mjtDisableBit.mjDSBL_FILTERPARENT),
        "solver":{"algorithm":args.solver,"jacobian":"dense","integrator":"implicitfast","cone":"pyramidal","narrowphase":"libccd","ccd_tolerance_m":float(m.opt.ccd_tolerance),"ccd_iterations":int(m.opt.ccd_iterations),"iterations":int(m.opt.iterations),"tolerance":float(m.opt.tolerance),"disableflags":int(m.opt.disableflags),"enableflags":int(m.opt.enableflags)},"contact_model":{"friction":m.geom_friction[0].tolist(),"solref":m.geom_solref[0].tolist(),"solimp":m.geom_solimp[0].tolist()},
        "calibrated":False,"physics_verified":False,
        "assets_sha256":{str(p.relative_to(output/"model")).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in (output/"model").rglob("*") if p.is_file()},
        "code_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"simulation").glob("*.py")}}
    (output/"run_config.json").write_text(json.dumps(config,indent=2),encoding="utf-8")
    mj.mj_saveModel(m,str(output/"active_model.mjb"),None)
    frames_t=[0.];frames_q=[d.qpos.copy()];frames_v=[d.qvel.copy()];frame_contacts=[d.ncon]
    frame_contact_points=[np.array([np.r_[c.pos,-c.dist] for c in d.contact],dtype=float).reshape(-1,4)]
    max_penetration=max((max(0.,-c.dist) for c in d.contact),default=0.)
    initial_penetration=max_penetration;peak_force=0.;max_contacts=d.ncon;contact_samples=0
    pair_stats=defaultdict(lambda:{"samples":0,"max_penetration_mm":0.,"peak_normal_force_N":0.})
    force=np.zeros(6);motor_work=0.;started=time.perf_counter();progress=started
    status="COMPLETED";reason=None;next_sample=0.;next_frame=1/120
    max_iterations=0;iteration_limit_steps=0
    steps=int(round(args.duration/args.dt));completed_steps=0
    with (output/"trajectory.csv").open("w",newline="",encoding="utf-8") as tf,gzip.open(output/"contacts.csv.gz","wt",newline="",encoding="utf-8") as cf,(output/"energy.csv").open("w",newline="",encoding="utf-8") as ef:
        tw=csv.writer(tf);cw=csv.writer(cf);ew=csv.writer(ef)
        tw.writerow(["time_s","input_request","motor_torque_Nm","contacts","max_penetration_mm"]+[n+"_rad" for n in names]+[n+"_rad_s" for n in names])
        cw.writerow(["solver_time_s","geom_a","geom_b","distance_mm","normal_force_N","friction1_N","friction2_N","x_m","y_m","z_m"])
        ew.writerow(["solver_time_s","potential_builtin_J","kinetic_J","compression_spring_J","input_work_J"])
        for step in range(steps):
            t=float(d.time);d.ctrl[0]=np.clip(request_at(args.case,t,args.duration)*args.torque_scale,-1,1)
            d.qfrc_applied[:]=0
            # Bench-only fixed load. It never chooses a direction based on input.
            if args.scope=="clutch" and args.case.startswith("clutch_"):
                jid=mj.mj_name2id(m,mj.mjtObj.mjOBJ_JOINT,"OM")
                d.qfrc_applied[m.jnt_dofadr[jid]]=-.0005
            old_input=float(d.qpos[qadr[names.index("I")]])
            mj.mj_step(m,d);completed_steps+=1
            niter=int(np.max(d.solver_niter));max_iterations=max(max_iterations,niter)
            if niter>=m.opt.iterations:iteration_limit_steps+=1
            torque=float(d.actuator_force[0]);motor_work+=torque*(float(d.qpos[qadr[names.index("I")]])-old_input)
            penetration=max((max(0.,-c.dist) for c in d.contact),default=0.)
            max_penetration=max(max_penetration,penetration);max_contacts=max(max_contacts,int(d.ncon))
            if not np.isfinite(d.qpos).all() or not np.isfinite(d.qvel).all():status="FAILED";reason="nonfinite_state";break
            bad=[mj.mjtWarning(i).name for i,w in enumerate(d.warning) if w.number and i in (int(mj.mjtWarning.mjWARN_BADQPOS),int(mj.mjtWarning.mjWARN_BADQVEL),int(mj.mjtWarning.mjWARN_BADQACC))]
            if bad:status="FAILED";reason=",".join(bad);break
            if t+1e-12>=next_sample:
                tw.writerow([float(d.time),float(d.ctrl[0]),torque,int(d.ncon),penetration*1000]+d.qpos[qadr].tolist()+d.qvel[vadr].tolist())
                ew.writerow([t,float(d.energy[0]),float(d.energy[1]),dynamics.spring_energy(d),motor_work])
                for ci,c in enumerate(d.contact):
                    mj.mj_contactForce(m,d,ci,force)
                    normal=abs(float(force[0]));peak_force=max(peak_force,normal)
                    cw.writerow([t,geom_names[c.geom1],geom_names[c.geom2],float(c.dist)*1000,*map(float,force[:3]),*map(float,c.pos)])
                    key=" / ".join(sorted([body_names[m.geom_bodyid[c.geom1]],body_names[m.geom_bodyid[c.geom2]]]))
                    stats=pair_stats[key];stats["samples"]+=1;stats["max_penetration_mm"]=max(stats["max_penetration_mm"],max(0.,-float(c.dist))*1000);stats["peak_normal_force_N"]=max(stats["peak_normal_force_N"],normal)
                    contact_samples+=1
                next_sample+=.001
            if d.time+args.dt/2>=next_frame or step==steps-1:
                frames_t.append(float(d.time));frames_q.append(d.qpos.copy());frames_v.append(d.qvel.copy());frame_contacts.append(int(d.ncon))
                frame_contact_points.append(np.array([np.r_[c.pos,-c.dist] for c in d.contact],dtype=float).reshape(-1,4))
                next_frame+=1/120
            now=time.perf_counter()
            if now-progress>8:
                print(json.dumps({"run":run_id,"t_s":round(float(d.time),4),"requested_s":args.duration,"contacts":d.ncon,"peak_penetration_mm":round(max_penetration*1000,4),"wall_s":round(now-started,1)}),flush=True);progress=now
    np.savez_compressed(output/"states.npz",time=np.array(frames_t),qpos=np.array(frames_q),qvel=np.array(frames_v),ncon=np.array(frame_contacts),initial_qpos=initial_q,initial_qvel=initial_v)
    # Ragged contact point arrays stay in JSON; no pickle is needed to replay.
    with gzip.open(output/"contact_points.json.gz","wt",encoding="utf-8") as stream:json.dump([a.tolist() for a in frame_contact_points],stream)
    end={n:{"initial_rad":float(initial_q[a]),"final_rad":float(d.qpos[a]),"travel_deg":float(np.rad2deg(d.qpos[a]-initial_q[a]))} for n,a in zip(names,qadr)}
    flap_names=[n for n in names if n.startswith(("FM_","FH_"))]
    summary={"status":status,"failure":reason,"run_id":run_id,"case":args.case,"scope":args.scope,"simulated_duration_s":float(d.time),"steps":completed_steps,
        "wall_seconds":time.perf_counter()-started,"recorded_frames":len(frames_t),"initial_penetration_mm":initial_penetration*1000,"peak_penetration_mm":max_penetration*1000,
        "peak_normal_force_N_sampled_1kHz":peak_force,"maximum_simultaneous_contacts":max_contacts,"contact_rows":contact_samples,
        "motor_work_J":motor_work,"joints":end,"contact_body_pairs":dict(sorted(pair_stats.items())),
        "maximum_solver_iterations":max_iterations,"steps_at_solver_iteration_limit":iteration_limit_steps,
        "flaps":len(flap_names),"flaps_travel_above_1deg":sum(abs(end[n]["travel_deg"])>1 for n in flap_names),
        "warning_counts":{mj.mjtWarning(i).name:int(w.number) for i,w in enumerate(d.warning) if w.number},
        "calibrated":False,"physics_verified":False,"hardware_verified":False,
        "limitations":manifest["assumptions"]+["Uncalibrated friction, springs, motor curve and joint losses; rigid contact has finite penetration.","Recordings show prototype behavior, not proof of a functioning clock or manufacturing acceptance."]}
    (output/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    if status=="COMPLETED":
        (ROOT/"reports"/"physics_latest.json").write_text(json.dumps({"run_id":run_id,"directory":str(output),"summary":"summary.json","status":status,"physics_verified":False},indent=2),encoding="utf-8")
    print(json.dumps({"status":status,"run":str(output),"duration_s":float(d.time),"peak_penetration_mm":max_penetration*1000,"flaps_moved":summary["flaps_travel_above_1deg"]}),flush=True)
    return 0 if status=="COMPLETED" else 1

