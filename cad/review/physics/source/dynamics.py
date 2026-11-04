"""Finite input actuator and unilateral compression springs for MuJoCo.

Output shafts, pawls, gears and flaps are moved exclusively by integrated
forces and contact. No callback writes qpos, qvel or constraint targets.
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
import numpy as np
import mujoco as mj


def contact_settings(model,time_constant=.0006):
    """Resolved soft-contact settings; conservative bandwidth for tiny pawls."""
    model.geom_solref[:]=[time_constant,1.]
    model.geom_solimp[:]=[.9,.95,.0001,.5,2.]


def solver_settings(model,solver="Newton",iterations=100):
    # Pyramidal Coulomb cone is the engine's convex quadratic formulation.
    # The classic libccd narrow phase handles these very thin convex prisms.
    model.opt.cone=mj.mjtCone.mjCONE_PYRAMIDAL
    model.opt.disableflags |= int(mj.mjtDisableBit.mjDSBL_NATIVECCD)
    model.opt.solver={"CG":mj.mjtSolver.mjSOL_CG,"Newton":mj.mjtSolver.mjSOL_NEWTON,"PGS":mj.mjtSolver.mjSOL_PGS}[solver]
    model.opt.jacobian=mj.mjtJacobian.mjJAC_DENSE
    model.opt.ccd_tolerance=1e-9
    model.opt.ccd_iterations=100
    model.opt.iterations=iterations
    if not hasattr(mj.mjtEnableBit,"mjENBL_DIAGEXACT"):
        raise RuntimeError("MuJoCo >=3.9 required: fixed-axis gear contacts need diagexact.")
    model.opt.enableflags |= int(mj.mjtEnableBit.mjENBL_DIAGEXACT)


class Dynamics:
    def __init__(self, model, manifest):
        self.model=model;self.manifest=manifest
        self.motor=manifest["motor"]
        jid=mj.mj_name2id(model,mj.mjtObj.mjOBJ_JOINT,"I")
        self.input_dof=int(model.jnt_dofadr[jid])
        self.springs=[]
        for spec in manifest["compression_springs"]:
            self.springs.append((spec,
                mj.mj_name2id(model,mj.mjtObj.mjOBJ_SITE,spec["base"]),
                mj.mj_name2id(model,mj.mjtObj.mjOBJ_SITE,spec["tip"]),
                mj.mj_name2id(model,mj.mjtObj.mjOBJ_BODY,spec["body"])))
        self._velocity=np.zeros(6)

    def gain(self, model, data, actuator_id):
        request=float(data.ctrl[actuator_id])
        direction=np.sign(request)
        omega=float(data.qvel[self.input_dof])
        speed_fraction=1-direction*omega/self.motor["no_load_speed_rad_s"]
        return self.motor["stall_torque_Nm"]*float(np.clip(speed_fraction,0,1))

    def spring_state(self, data, spec, base, tip):
        delta=data.site_xpos[tip]-data.site_xpos[base]
        length=float(np.linalg.norm(delta))
        direction=delta/max(length,1e-12)
        mj.mj_objectVelocity(self.model,data,mj.mjtObj.mjOBJ_SITE,tip,self._velocity,0)
        rate=float(np.dot(self._velocity[3:],direction))
        compression=max(0.,spec["free_length_m"]-length)
        # An unseated spring cannot pull the arm back to its base.
        force=0. if compression<=0 else float(np.clip(spec["stiffness_N_m"]*compression-spec["damping_N_s_m"]*rate,0,spec["max_force_N"]))
        return direction,length,compression,force

    def passive(self, model, data):
        for spec,base,tip,body in self.springs:
            direction,length,compression,force=self.spring_state(data,spec,base,tip)
            mj.mj_applyFT(model,data,direction*force,np.zeros(3),data.site_xpos[tip],body,data.qfrc_passive)

    def spring_energy(self, data):
        energy=0.
        for spec,base,tip,body in self.springs:
            _,_,compression,_=self.spring_state(data,spec,base,tip)
            limit=spec["max_force_N"]/spec["stiffness_N_m"]
            energy+=.5*spec["stiffness_N_m"]*min(compression,limit)**2+spec["max_force_N"]*max(0.,compression-limit)
        return energy

    def install(self):
        # Keep this instance alive while the model is used; callbacks are global
        # to one Python process, which uses one model at a time.
        mj.set_mjcb_act_gain(self.gain)
        mj.set_mjcb_passive(self.passive)

    @staticmethod
    def clear():
        mj.set_mjcb_act_gain(None);mj.set_mjcb_passive(None)


def load_model(directory):
    directory=Path(directory)
    Dynamics.clear()
    cache=directory/"model.mjb";stamp=directory/"compiled.json"
    fingerprint=hashlib.sha256((directory/"model.xml").read_bytes())
    for path in sorted((directory/"assets").glob("*.stl")):fingerprint.update(path.read_bytes())
    digest=fingerprint.hexdigest()
    cached=json.loads(stamp.read_text()) if stamp.exists() else {}
    if cache.exists() and cached.get("source_sha256")==digest and cached.get("mujoco")==mj.__version__:
        model=mj.MjModel.from_binary_path(str(cache))
    else:
        model=mj.MjModel.from_xml_path(str(directory/"model.xml"))
        mj.mj_saveModel(model,str(cache),None)
        stamp.write_text(json.dumps({"source_sha256":digest,"mujoco":mj.__version__}),encoding="utf-8")
    manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
    contact_settings(model)
    solver_settings(model)
    dynamics=Dynamics(model,manifest);dynamics.install()
    data=mj.MjData(model)
    mj.mj_forward(model,data)
    return model,data,dynamics,manifest


def seed_flaps(model,data,seed=0):
    """One initial 0.1-degree perturbation to break perfect inverted symmetry."""
    rng=np.random.default_rng(seed)
    for jid in range(model.njnt):
        name=mj.mj_id2name(model,mj.mjtObj.mjOBJ_JOINT,jid) or ""
        if name.startswith(("FM_","FH_")):
            data.qpos[model.jnt_qposadr[jid]]=rng.uniform(-1,1)*np.deg2rad(.1)
    mj.mj_forward(model,data)

