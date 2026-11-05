"""Contact-free conjugate sweep of authored gear profiles (not a motion model).

This isolates tooth interference from inertia, springs and contact-solver errors.
Its prescribed poses are geometry checks only; never physics evidence.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.affinity import rotate, translate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import r2_geometry as g


def profile(prefix):
    files = sorted((ROOT / "simulation" / "generated" / "profile_cache").glob(prefix + "_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    file = files[0]; data = json.loads(file.read_text())
    return unary_union([Polygon(r) for r in data["regions"]]), str(file.relative_to(ROOT)), hashlib.sha256(file.read_bytes()).hexdigest()


def main():
    p40, f40, h40 = profile("gear_M"); p20, f20, h20 = profile("idler"); p60, f60, h60 = profile("clutch_H")
    ht = g.hour_train(); c1, c2 = ht["centres"]; phases = ht["phases"]
    pairs = [("M_input_idler", p40, p20, (0, 36), 0, 9, 1, -2, 9),
             ("M_idler_output", p20, p40, (0, 36), 9, 0, -2, 1, 9),
             ("H_input_idler", p60, p20, (-(c1[1] - 61), c1[0] + 72), 0, phases[0], 1, -3, 6),
             ("H_idlers", p20, p20, (0, 24), phases[0], phases[1], -3, 3, 6),
             ("H_idler_output", p20, p40, (c2[1] - 61, g.axis_y("H") - c2[0]), phases[1], ht["output_phase"], 3, -1.5, 6)]
    rows = []
    for name, a, b, delta, pa, pb, ra, rb, period in pairs:
        values = []
        for k in range(181):
            q = period * k / 180
            aa = rotate(a, pa + ra * q, origin=(0, 0))
            bb = translate(rotate(b, pb + rb * q, origin=(0, 0)), xoff=delta[0], yoff=delta[1])
            values.append(float(aa.intersection(bb).area))
        peak = max(values)
        rows.append({"pair": name, "max_overlap_mm2": peak, "angle_of_max_deg": period * values.index(peak) / 180, "samples": 181, "status": "PASS" if peak < .0001 else "FAIL"})
    report = {"status": "PASS" if all(r["status"] == "PASS" for r in rows) else "FAIL", "pairs": rows,
              "profiles": [{"file": f, "sha256": h} for f, h in ((f40, h40), (f20, h20), (f60, h60))],
              "scope": "2D conjugate pose sweep of CAD tessellations; prescribed poses only for static geometry checks, no physics claim"}
    (ROOT / "reports" / "gear_mesh_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["pairs"], indent=2), flush=True)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
