"""Check the published run, portable assets, provenance and decodable videos."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]


def main():
    review=ROOT/"review"/"physics";failures=[]
    manifest=json.loads((review/"PUBLISH_MANIFEST.json").read_text(encoding="utf-8"))
    forbidden=set(manifest["excluded_author_payload_sha256"])
    matches=[]
    for name,digest in manifest["files"].items():
        path=(review/name).resolve()
        if not path.is_relative_to(review.resolve()) or not path.is_file():failures.append("Missing/outside bundle: "+name);continue
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=digest:failures.append("Bundle hash mismatch: "+name)
        if actual in forbidden:matches.append(name)
        if path.suffix==".mjb" or "source/original" in name:failures.append("Excluded cache/source included: "+name)
    if matches:failures.append("Original payload hashes matched: "+str(matches))
    config=json.loads((review/"run_config.json").read_text());summary=json.loads((review/"summary.json").read_text())
    for name,digest in config["assets_sha256"].items():
        path=review/"model"/name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:failures.append("Model asset mismatch: "+name)
    for name,digest in config["code_sha256"].items():
        path=review/"source"/name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:failures.append("Simulation source mismatch: "+name)
    render=json.loads((review/"render.json").read_text())
    if hashlib.sha256((review/"provenance"/"render_source.py").read_bytes()).hexdigest()!=render["render_code_sha256"]:failures.append("Render source mismatch")
    model=ET.parse(review/"model"/"model.xml").getroot()
    for mesh in model.findall("asset/mesh"):
        if mesh.get("file") and not (review/"model"/"assets"/mesh.get("file")).is_file():failures.append("Unresolvable portable mesh: "+mesh.get("name"))
    if len(model.findall(".//body"))!=96:failures.append("Moving body count mismatch")
    if len(model.findall(".//body[@name]"))!=config["nbody"]-1:failures.append("Recorded model body count mismatch")
    if model.find("equality") is not None or len(list(model.find("actuator")))!=1:failures.append("Unexpected prescribed motion/actuator structure")
    flags=model.find("option/flag")
    if flags.get("diagexact")!="enable" or flags.get("filterparent")!="disable" or flags.get("autoreset")!="disable":failures.append("Expected exact contact and collision flags missing")
    states=np.load(review/"states.npz",allow_pickle=False)
    if states["qpos"].shape!=(193,96) or not np.isfinite(states["qpos"]).all() or not np.isfinite(states["qvel"]).all():failures.append("Invalid recorded states")
    if not np.all(np.diff(states["time"])>0) or abs(states["time"][-1]-1.6)>1e-8:failures.append("Incomplete timeline")
    if summary["status"]!="COMPLETED" or summary["warning_counts"] or summary["steps_at_solver_iteration_limit"]:failures.append("Main run not warning-free/converged per-step")
    videos=[]
    for name in ("physics.mp4","front.mp4","rear.mp4"):
        reader=imageio_ffmpeg.read_frames(str(review/name),pix_fmt="rgb24")
        metadata=next(reader);frames=sum(1 for _ in reader)
        videos.append({"file":name,"frames_decoded":frames,"size":metadata["size"],"fps":metadata["fps"],"duration_s":metadata["duration"]})
        if metadata["size"]!=(1280,720) or abs(metadata["fps"]-30)>1e-6 or frames!=253:failures.append("Video does not decode to expected timeline: "+name)
    report={"status":"FAIL" if failures else "PASS","scope":"Published artifact integrity, model flags, recorded states, video decoding; no desktop/UI automation.",
        "bundle_files_checked":len(manifest["files"]),"original_payload_hashes_checked":len(forbidden),"original_payload_matches":matches,
        "moving_bodies":96,"recorded_states":len(states["time"]),"videos":videos,"interactive_desktop_check":"MANUAL_CHECK_PENDING","physics_verified":False,"failures":failures}
    (ROOT/"reports"/"physics_review_check.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2),flush=True)
    return 1 if failures else 0


if __name__=="__main__":raise SystemExit(main())
