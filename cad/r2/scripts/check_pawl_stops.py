"""Native swept check of working heel stops and freewheel clearance.

The prescribed poses here are static interference samples only. They never
drive the physics model or replace contact with a joint limit.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import r2_geometry as g
from cadgen import build123d as bd
from cadgen.geometry import overlap_volume


def overlap(a, b):
    return sum(overlap_volume(x, y) for x in a.solids() for y in b.solids())


def main():
    rows = []
    for branch in ("M", "H"):
        d = g.direction(branch); parts = g.clutch_parts(branch)
        pivot = bd.Axis((9.2, -3 * d, 0), (0, 0, 1))
        pawn, carrier = parts["pawl"], parts["carrier"]
        freewheel = [{"angle_deg": float(a), "overlap_mm3": overlap(carrier, pawn.rotate(pivot, d * a))} for a in np.arange(0, 35.01, 2.5)]
        engaging = [{"angle_deg": float(-d * a), "overlap_mm3": overlap(carrier, pawn.rotate(pivot, -d * a))} for a in np.arange(0, 6.01, .25)]
        old_points = [(8, -4.9), (10.2, -5), (12, -1.1), (14.35, -.7), (14.35, .7), (13.15, 1.1), (9.4, -.5), (8, -1.3)]
        old = g.rounded_polygon([(u, v * d) for u, v in old_points], .25)
        old += bd.Pos(9.2, -3 * d) * bd.Circle(2.5)
        old -= bd.Pos(9.2, -3 * d) * bd.Circle(1.1)
        old = bd.Pos(0, 0, 1.9) * bd.extrude(old, amount=1.4, both=True)
        old_stop = bd.Pos(9.2, -6.8 * d, 1.4) * bd.Box(2, 2, 3.8)
        old_max = max(overlap(old_stop, old.rotate(pivot, -d * a)) for a in np.arange(0, 8.01, .5))
        contacts = [r for r in engaging if r["overlap_mm3"] > 1e-5]
        first = contacts[0]["angle_deg"] if contacts else None
        okay = max(r["overlap_mm3"] for r in freewheel) < 1e-5 and first is not None and 1 < abs(first) < 4.5 and carrier.is_valid and pawn.is_valid and len(carrier.solids()) == 1 and len(pawn.solids()) == 1
        rows.append({"branch": branch, "status": "PASS" if okay else "FAIL", "freewheel_sweep": freewheel, "engagement_sweep": engaging,
                     "first_engagement_interference_deg": first, "legacy_stop_max_overlap_in_first_8deg_mm3": old_max,
                     "native_carrier_solids": len(carrier.solids()), "native_pawl_solids": len(pawn.solids())})
    report = {"status": "PASS_STATIC_ONLY" if all(r["status"] == "PASS" for r in rows) else "FAIL", "rows": rows,
              "source_sha256": hashlib.sha256((ROOT / "src/r2_geometry.py").read_bytes()).hexdigest(),
              "scope": "Native carrier/pawl only; zero-pose clearance, freewheel fold through 35 degrees, physical engagement by 4.5 degrees. Not a dynamic or strength test.",
              "hardware_verified": False}
    (ROOT / "reports/pawl_stops.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "rows": [{k: v for k, v in r.items() if k not in ("freewheel_sweep", "engagement_sweep")} for r in rows]}, indent=2), flush=True)
    return 0 if report["status"] == "PASS_STATIC_ONLY" else 1


if __name__ == "__main__": raise SystemExit(main())
