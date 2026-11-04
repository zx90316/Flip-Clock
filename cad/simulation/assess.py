"""Compare recorded physics runs; numerical checks are not hardware acceptance."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def read(run):
    run=Path(run).resolve()
    return run,json.loads((run/"run_config.json").read_text()),json.loads((run/"summary.json").read_text()),np.load(run/"states.npz",allow_pickle=False)


def assess(main,zero,fine):
    run,c,s,x=read(main);zr,zc,zs,zx=read(zero);fr,fc,fs,fx=read(fine)
    for other in (zc,fc):
        if other["version"]!=c["version"] or other["joints"]!=c["joints"]:raise ValueError("Comparison requires same engine and DOFs")
        if other["assets_sha256"]["model.xml"]!=c["assets_sha256"]["model.xml"]:raise ValueError("Comparison requires same model")
    indices=[i for i,n in enumerate(c["joints"]) if n.startswith(("FM_","FH_"))]
    cutoff=float(zx["time"][-1])
    main_at_zero=np.array([np.interp(cutoff,x["time"],x["qpos"][:,j]) for j in indices])
    main_travel=np.rad2deg(main_at_zero-x["initial_qpos"][indices])
    zero_travel=np.rad2deg(zx["qpos"][-1,indices]-zx["initial_qpos"][indices])
    errors=[]
    for j in range(c["nq"]):
        base=np.interp(fx["time"],x["time"],x["qpos"][:,j])
        errors.append(np.rad2deg(fx["qpos"][:,j]-base))
    errors=np.array(errors)
    max_flap_error=float(np.max(np.abs(errors[indices])))
    with (run/"trajectory.csv").open(newline="",encoding="utf-8") as stream:rows=list(csv.DictReader(stream))
    peak_torque=max(abs(float(r["motor_torque_Nm"])) for r in rows)
    window_travel={}
    for label,start,end in (("positive_input",.6,.9),("negative_input",1.05,1.35)):
        window_travel[label]={}
        for name in ("I","OM","OH","M","H"):
            j=c["joints"].index(name)
            a=np.interp(start,x["time"],x["qpos"][:,j]);b=np.interp(end,x["time"],x["qpos"][:,j])
            window_travel[label][name+"_degrees"]=float(np.rad2deg(b-a))
    result={"status":"EXPLORATORY_COMPLETED","engine":"MuJoCo "+c["version"],"main_run":str(run.relative_to(ROOT)).replace("\\","/"),
        "simulated_seconds":s["simulated_duration_s"],"steps":s["steps"],"timestep_s":c["timestep_s"],
        "warnings":s["warning_counts"],"moving_bodies":c["nbody"]-1,"flaps":s["flaps"],"equality_constraints":c["equality_constraints"],"actuators":c["actuators"],
        "parent_child_collision_enabled":c["parent_child_collision_enabled"],"diagexact_enabled":False,
        "peak_penetration_mm":s["peak_penetration_mm"],"max_solver_iterations":s["maximum_solver_iterations"],"steps_at_solver_limit":s["steps_at_solver_iteration_limit"],
        "gravity_control":{"duration_s":cutoff,"main_g_m_s2":c["gravity_m_s2"],"control_g_m_s2":zc["gravity_m_s2"],"flaps_above_1deg_with_gravity":int(np.count_nonzero(np.abs(main_travel)>1)),"flaps_above_1deg_without_gravity":int(np.count_nonzero(np.abs(zero_travel)>1)),
            "control_run":str(zr.relative_to(ROOT)).replace("\\","/"),"input_torque_zero_throughout_comparison":cutoff<.6},
        "timestep_comparison":{"duration_s":float(fx["time"][-1]),"coarse_s":c["timestep_s"],"fine_s":fc["timestep_s"],"maximum_flap_angle_difference_deg":max_flap_error,"rms_flap_difference_deg":float(np.sqrt(np.mean(errors[indices]**2))),
            "maximum_all_joint_difference_deg":float(np.max(np.abs(errors))),"fine_run":str(fr.relative_to(ROOT)).replace("\\","/"),"scope":"Initial gravity interval only; no long-run convergence claim."},
        "motor":{"maximum_recorded_abs_torque_Nm":peak_torque,"proposed_limit_Nm":.025,"within_limit":peak_torque<=.025+1e-12,"window_joint_travel":window_travel},
        "physics_verified":False,"hardware_verified":False,"manufacturing_ready":False,
        "limits":["Unmeasured density, friction, spring and motor parameters.","Rigid soft-contact model has measured numerical penetration; no deformation/strength prediction.","Retracted release fingers do not establish a stable HH:MM display.","Time-step comparison covers 0.2 seconds only; 1.6-second run is not endurance evidence."]}
    # Resolve the actual enum bit, not a hardcoded numeric value.
    import mujoco as mj
    result["diagexact_enabled"]=bool(c["solver"]["enableflags"]&int(mj.mjtEnableBit.mjENBL_DIAGEXACT))
    (ROOT/"reports"/"physics_assessment.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    relative=str(run.relative_to(ROOT)).replace("\\","/")
    pointer={"run_id":s["run_id"],"directory":relative,"relative_directory":relative,"status":s["status"],"physics_verified":False,"assessment":"physics_assessment.json"}
    (ROOT/"reports"/"physics_latest.json").write_text(json.dumps(pointer,indent=2),encoding="utf-8")
    run_status={"status":"EXPLORATORY_COMPLETED","requested_cases":["drive","gravity_control","timestep_comparison"],"executed_cases":[result["main_run"],result["gravity_control"]["control_run"],result["timestep_comparison"]["fine_run"]],"evidence":"physics_assessment.json","calibrated":False,"physics_verified":False}
    (ROOT/"reports"/"simulate_status.json").write_text(json.dumps(run_status,indent=2)+"\n",encoding="utf-8")
    verify=json.loads((ROOT/"reports"/"verification.json").read_text(encoding="utf-8"))
    from datetime import datetime,timezone,timedelta
    verify["updated_at"]=datetime.now(timezone(timedelta(hours=8))).isoformat()
    verify["physics"]={"status":"EXPLORATORY_COMPLETED","engine":result["engine"],"evidence":"physics_assessment.json","run":result["main_run"],"simulated_seconds":result["simulated_seconds"],"calibrated":False,"physics_verified":False}
    verify["continuous_full_assembly_collision"]={"status":"APPROXIMATE_MODEL_RUN","exact_native_CAD_clearance_validated":False,"evidence":"physics_assessment.json"}
    verify["interactive_viewer"]={"status":"MANUAL_CHECK_PENDING","scope":"Native window controls and desktop appearance; video and recorded solver data checked separately."}
    (ROOT/"reports"/"verification.json").write_text(json.dumps(verify,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2),flush=True)
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--main",required=True);p.add_argument("--zero",required=True);p.add_argument("--fine",required=True);a=p.parse_args();assess(a.main,a.zero,a.fine)
