from cadgen import step
from assembly import assembly
from drag_rings import drag_rings
import r2_geometry as g

@step(out="../STEP/assembly_with_drag.step", mesh_tolerance=.02)
def assembly_with_drag():
    return g.group("FC_R2_passive_drag_CANDIDATE_NOT_HARDWARE_VERIFIED", [assembly(), drag_rings()])

if __name__ == "__main__": assembly_with_drag()
