"""Check saved native envelopes for the unmeasured passive-drag proposal."""
import hashlib
import json
from pathlib import Path
from cadgen import read_scene
from cadgen.geometry import overlap_volume

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / "config/drag_candidate.json").read_text())
    scene = read_scene(str(ROOT / "STEP/assembly_with_drag.step"))
    leaves = {leaf.label: leaf.shape() for leaf in scene.leaves()}
    rows = []
    for branch, side, yy in (("M", -1, 0), ("H", 1, 21.6)):
        ring = leaves[f"W{branch}_felt_drag_RING_ENVELOPE_NOT_FDM"]
        bearing = leaves[f"B{branch}_{int(yy)}_608_ENVELOPE"]
        knob = leaves[f"K{branch}_service_knob"]
        bounds = ring.bounding_box()
        overlap = {name: overlap_volume(ring, shape) for name, shape in (("bearing", bearing), ("knob", knob))}
        rho, ri = config["outer_radius_mm"], config["inner_radius_mm"]
        mean_r = (2 / 3) * (rho ** 3 - ri ** 3) / (rho ** 2 - ri ** 2) / 1000
        drag = config["target_drag_Nm"][branch]
        rows.append({"branch": branch, "valid_native_solid": ring.is_valid and len(ring.solids()) == 1,
                     "x_bounds_mm": [bounds.min.X, bounds.max.X], "nominal_axial_space_mm": 1.1,
                     "overlap_mm3": overlap, "target_drag_Nm": drag,
                     "assumed_uniform_pressure_mean_radius_m": mean_r,
                     "normal_force_proposal_N": drag / (config["friction_coefficient_assumed"] * mean_r),
                     "tangential_force_at_knob_13mm_N": drag / .013})
    okay = all(row["valid_native_solid"] and max(row["overlap_mm3"].values()) < 1e-5 and abs(row["x_bounds_mm"][1] - row["x_bounds_mm"][0] - 1.1) < 1e-5 for row in rows)
    report = {"status": "PASS_NOMINAL_GEOMETRY_ONLY" if okay else "FAIL", "rows": rows,
              "candidate_step_sha256": hashlib.sha256((ROOT / "STEP/assembly_with_drag.step").read_bytes()).hexdigest(),
              "scope": "Saved STEP envelopes; no felt constitutive law, preload measurement, bearing-load or material validation",
              "hardware_verified": False}
    (ROOT / "reports/drag_fit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0 if okay else 1


if __name__ == "__main__": raise SystemExit(main())
