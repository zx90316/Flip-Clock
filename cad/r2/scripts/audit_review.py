"""Verify the published evidence bytes, recorded states and decoded videos.

This audits evidence integrity. It must never turn an unsuccessful physical
acceptance into PASS merely because its files are intact.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import imageio.v2 as imageio
import mujoco as mj

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulation"))
from calibrate import load
from runtime import apply_solver_parameters


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main(review_dir=None):
    review = Path(review_dir).resolve() if review_dir else ROOT / "review"
    manifest = json.loads((review / "PUBLISH_MANIFEST.json").read_text())
    cfg = json.loads((review / "run_config.json").read_text())
    summary = json.loads((review / "summary.json").read_text())
    render = json.loads((review / "render_provenance.json").read_text())
    errors = []
    for rel, value in manifest["files_sha256"].items():
        path = review / rel
        if not path.is_file() or sha(path) != value: errors.append("file hash: " + rel)
    original_check = ROOT.parent / "review/physics/PUBLISH_MANIFEST.json"
    excluded = set(json.loads(original_check.read_text())["excluded_author_payload_sha256"]) if original_check.is_file() else set()
    original_matches = [rel for rel, value in manifest["files_sha256"].items() if value in excluded]
    if original_matches: errors.append("Original archive payload bytes were found")
    for path, value in ((review / "source/calibrate.py", cfg["source_sha256"]),
                        (review / "model/model.xml", cfg["model_sha256"]),
                        (review / "source/render_r2.py", render["source_sha256"]),
                        (review / "states.npz", render["input_states_sha256"]),
                        (review / "source/drag_candidate.json", cfg["drag_config_sha256"])):
        if sha(path) != value: errors.append("provenance: " + path.name)
    if cfg.get("runtime_sha256") and sha(review / "source/runtime.py") != cfg["runtime_sha256"]: errors.append("integration runtime source")
    if cfg.get("solver_config_sha256") and sha(review / "source/solver_config.json") != cfg["solver_config_sha256"]: errors.append("solver settings snapshot")
    if render.get("runtime_sha256") and sha(review / "source/render_runtime.py") != render["runtime_sha256"]: errors.append("render runtime source")
    comparisons = []
    for directory in sorted((review / "comparison").iterdir()):
        other = json.loads((directory / "run_config.json").read_text())
        if sha(directory / "source/calibrate.py") != other["source_sha256"]: errors.append("comparison controller: " + directory.name)
        if other["model_sha256"] != cfg["model_sha256"]:
            if not (directory / "model/model.xml").is_file() or sha(directory / "model/model.xml") != other["model_sha256"]: errors.append("missing distinct comparison model: " + directory.name)
        if other.get("runtime_sha256") and sha(directory / "source/runtime.py") != other["runtime_sha256"]: errors.append("comparison runtime: " + directory.name)
        recorded = np.load(directory / "states.npz", allow_pickle=False)
        if not np.isfinite(recorded["qpos"]).all() or not np.isfinite(recorded["qvel"]).all(): errors.append("comparison states: " + directory.name)
        provenance = directory / "render_provenance.json"
        if provenance.is_file():
            other_render = json.loads(provenance.read_text())
            if sha(directory / "states.npz") != other_render["input_states_sha256"] or sha(directory / "source/render_r2.py") != other_render["source_sha256"]:
                errors.append("comparison render provenance: " + directory.name)
        comparisons.append({"run_id": directory.name, "recorded_frames": len(recorded["time_s"]), "same_geometry_model": other["model_sha256"] == cfg["model_sha256"]})
    states = np.load(review / "states.npz", allow_pickle=False)
    frames = len(states["time_s"])
    for name in states.files:
        if np.issubdtype(states[name].dtype, np.number) and not np.isfinite(states[name]).all(): errors.append("nonfinite states: " + name)
    if np.any(np.diff(states["time_s"]) <= 0): errors.append("time is not increasing")
    if states["qpos"].shape != (frames, 98) or states["qvel"].shape != (frames, 98): errors.append("state dimensions")
    if np.max(np.abs(states["input_torque_Nm"])) > cfg["torque_limit"] + 1e-10: errors.append("torque budget")
    with gzip.open(review / "contact_points.json.gz", "rt", encoding="utf-8") as stream:
        contacts = json.load(stream)
    if len(contacts) != frames: errors.append("contact frame count")
    model, _, _, _ = load(review / "model")
    apply_solver_parameters(model, cfg.get("solver_parameters"))
    if (model.nbody, model.nq, model.nu, model.neq) != (99, 98, 1, 0): errors.append("mechanism degrees of freedom")
    actuator_joint = int(model.actuator_trnid[0, 0])
    if mj.mj_id2name(model, mj.mjtObj.mjOBJ_JOINT, actuator_joint) != "I": errors.append("output actuator")
    videos = []
    for name in ("desktop", "cutaway", "front"):
        count = 0
        with imageio.get_reader(str(review / (name + ".mp4"))) as reader:
            meta = reader.get_meta_data()
            for frame in reader:
                count += 1
                if frame.shape[:2] != (896, 1280): errors.append("video dimensions: " + name); break
        if count != frames + 24: errors.append("video frame count: " + name)
        videos.append({"file": name + ".mp4", "decoded_frames": count, "fps": meta["fps"], "bytes": (review / (name + ".mp4")).stat().st_size})
    result = {"evidence_integrity": "PASS" if not errors else "FAIL", "errors": errors,
              "run_id": summary["run_id"], "hash_bound_files": len(manifest["files_sha256"]),
              "recorded_frames": frames, "nbody": model.nbody, "nq": model.nq, "actuators": model.nu, "equalities": model.neq,
              "videos": videos, "comparison_runs": comparisons, "physical_acceptance": manifest["motion_acceptance"], "hardware_verified": False}
    result["collision_pipeline"] = "libccd" if model.opt.disableflags & int(mj.mjtDisableBit.mjDSBL_NATIVECCD) else "native"
    result.update(original_payload_hashes_checked=len(excluded), original_payload_matches=original_matches,
                  original_comparison_scope="Exact payload byte hashes only; not a legal determination or proof of design independence")
    report_name = "review_audit.json" if review.name == "review" else review.name + "_audit.json"
    (ROOT / "reports" / report_name).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--review")
    raise SystemExit(main(parser.parse_args().review))
