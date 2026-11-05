"""Selected stationary fabrication solids, read from saved STEP.

Static-only check complements, and never replaces, the full contact simulation.
"""
import json
from pathlib import Path
from itertools import combinations
from cadgen import read_scene
from cadgen.geometry import overlap_volume

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"A00_single_base", "A01_inverted_print_hood", "A02_front_panel", "A03_rear_panel", "A04_display_bezel",
          "A10_M_internal_frame", "A10_H_internal_frame", "A11_center_plain_bearing_pedestal", "T_idler_pedestal", "TH_idler_bridge",
          "E_slotted_motor_saddle", "E_motor_top_clamp", "DEM_bracket", "DEH_bracket", "SM_encoder_holder", "SH_encoder_holder"}


def main():
    scene = read_scene(str(ROOT / "STEP" / "assembly.step"))
    shapes = {n.label: n.shape() for n in scene.leaves() if n.label in LABELS}
    overlaps = []; narrow = 0
    for (na, a), (nb, b) in combinations(shapes.items(), 2):
        ba, bb = a.bounding_box(), b.bounding_box()
        if any(hi_a < lo_b - .0001 or hi_b < lo_a - .0001 for hi_a, lo_a, hi_b, lo_b in zip(ba.max, ba.min, bb.max, bb.min)):
            continue
        narrow += 1
        volume = sum(overlap_volume(sa, sb) for sa in a.solids() for sb in b.solids())
        if volume > 1e-4: overlaps.append({"a": na, "b": nb, "volume_mm3": volume})
    report = {"status": "PASS" if not overlaps and len(shapes) == len(LABELS) else "FAIL", "selected_parts": sorted(shapes), "missing_parts": sorted(LABELS - shapes.keys()), "native_pair_queries": narrow,
              "overlap_threshold_mm3": .0001, "overlaps": overlaps, "scope": "stationary printed solids only; touching mates allowed; no swept-motion or purchased-component validation"}
    (ROOT / "reports" / "static_interference.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
