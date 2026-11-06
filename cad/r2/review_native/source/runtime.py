"""Explicit numerical solver assumptions, separate from physical drag targets."""
import mujoco as mj


def apply_solver_parameters(model, settings):
    if not settings: return
    contact = settings["contact"]
    if contact["time_constant_s"] < 2 * model.opt.timestep:
        raise ValueError("Contact time constant must resolve at least two integration steps")
    model.geom_solref[:] = [contact["time_constant_s"], 1]
    model.geom_solimp[:] = [contact["impedance_min"], contact["impedance_max"], contact["width_m"], .5, 2]
    model.opt.cone = {"elliptic": mj.mjtCone.mjCONE_ELLIPTIC, "pyramidal": mj.mjtCone.mjCONE_PYRAMIDAL}[contact["cone"]]
    if settings.get("collision_pipeline") == "native":
        model.opt.disableflags &= ~int(mj.mjtDisableBit.mjDSBL_NATIVECCD)
    elif settings.get("collision_pipeline") == "libccd":
        model.opt.disableflags |= int(mj.mjtDisableBit.mjDSBL_NATIVECCD)
    friction = settings.get("joint_friction")
    if not friction: return
    if friction["time_constant_s"] < 2 * model.opt.timestep:
        raise ValueError("Joint-friction time constant must resolve at least two integration steps")
    selected = model.dof_frictionloss > 0
    model.dof_solref[selected] = [friction["time_constant_s"], 1]
    model.dof_solimp[selected] = [friction["impedance"], friction["impedance"], .0001, .5, 2]


def friction_rows(data, dofs):
    kind = int(mj.mjtConstraint.mjCNSTR_FRICTION_DOF)
    return {name: next((i for i in range(data.nefc) if int(data.efc_type[i]) == kind and int(data.efc_id[i]) == dof), None) for name, dof in dofs.items()}
