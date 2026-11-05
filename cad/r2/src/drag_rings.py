"""Nonprinted force-equivalent drag-ring envelopes for the tuned candidate."""
from pathlib import Path
import json
from cadgen import step
import r2_geometry as g

ROOT = Path(__file__).resolve().parents[1]

@step(out="../STEP/drag_rings.step", mesh_tolerance=.01)
def drag_rings():
    p = json.loads((ROOT / "config" / "drag_candidate.json").read_text())
    rings = []
    for b in ("M", "H"):
        shape = g.ring(p["outer_radius_mm"], p["inner_radius_mm"], p["installed_thickness_mm"])
        shape = g.place_axial(shape, g.sign(b) * p["x_abs_mm"], g.axis_y(b), g.config()["axis_z"])
        rings.append(g.named(shape, "W" + b + "_felt_drag_RING_ENVELOPE_NOT_FDM", "#8C806E"))
    return g.group("Proposed_passive_drag_rings_UNMEASURED", rings)

if __name__ == "__main__": drag_rings()
