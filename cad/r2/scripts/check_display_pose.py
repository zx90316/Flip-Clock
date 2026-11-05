"""Ray-sample recorded front-facing leaves; no invented display/pose correction.

This identifies physical leaf faces only. It is not OCR or visual proof that
printed graphics are readable or registered across the split.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import mujoco as mj

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulation"))
from calibrate import load


def main(directory):
    directory = Path(directory).resolve()
    summary = json.loads((directory / "summary.json").read_text())
    model, data, _, _ = load(directory / "model")
    data.qpos[:] = summary["q_final"]
    mj.mj_forward(model, data)
    group = np.array([0, 0, 1, 0, 0, 0], dtype=np.uint8)
    direction = np.array([0., -1., 0.])
    hits = []
    for branch, centre in (("M", -.024), ("H", .024)):
        for half, heights in (("upper", (.067, .073)), ("lower", (.047, .053))):
            for dx in (-.012, 0., .012):
                for height in heights:
                    geom = np.zeros(1, dtype=np.int32)
                    distance = mj.mj_ray(model, data, np.array([centre + dx, .2, height]), direction, group, True, -1, geom)
                    gid = int(geom[0]); bid = int(model.geom_bodyid[gid]) if gid >= 0 else 0
                    body = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, bid)
                    row = {"branch": branch, "half": half, "x_mm": (centre + dx) * 1000, "z_mm": height * 1000, "body": body, "ray_distance_m": distance}
                    if body and body.startswith("F" + branch + "_"):
                        k = int(body[3:]); count = 60 if branch == "M" else 24
                        normal_y = float(data.xmat[bid].reshape(3, 3)[1, 1])
                        row.update(leaf_index=k, face="front_upper_artwork" if normal_y > 0 else "back_lower_artwork",
                                   artwork_value=k if normal_y > 0 else (k + 1) % count)
                    hits.append(row)
    result = {"run_id": summary["run_id"], "scope": "Final saved solver state; twelve front rays per wheel at fixed aperture coordinates, visible native meshes only",
              "status": "SAMPLED_NOT_READABILITY_VERIFIED", "hits": hits,
              "flip_evidence_verified": False, "hardware_verified": False}
    (ROOT / "reports/display_pose.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("run"); main(ap.parse_args().run)
