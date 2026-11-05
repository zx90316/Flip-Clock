"""Package only manifest-listed current CAD/meshes, never stale outputs or inputs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT.parent / "scripts"))
from export_parts import stl_quality


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    geometry = json.loads((ROOT / "reports" / "geometry_check.json").read_text())
    stationary = json.loads((ROOT / "reports" / "static_interference.json").read_text())
    if geometry["status"] != "PASS" or stationary["status"] != "PASS": raise RuntimeError("Native CAD checks must pass before packaging")
    catalog = json.loads((ROOT / "reports" / "parts.json").read_text())
    files = [ROOT / "STEP" / name for name in ("assembly.step", "assembly_with_drag.step", "drag_rings.step", "mechanism.step", "coupons.step")]
    files += [ROOT / "STL" / "coupons.stl", ROOT / "README.md", ROOT / "VIEWER.md", ROOT / "parameters.json", ROOT / "build.ps1", ROOT / "requirements-dfam.txt"]
    mesh_rows = []
    for row in catalog["parts"]:
        stl = ROOT / row["stl"]; step = ROOT / row["step"]
        if sha(stl) != row["stl_sha256"]: raise ValueError("Changed STL: " + row["id"])
        quality = stl_quality(stl); mesh_rows.append({"id": row["id"], **quality})
        if quality["status"] != "PASS": raise ValueError("Bad STL: " + row["id"] + str(quality))
        files += [stl, step]
    report = {"status": "PASS", "parts": mesh_rows, "scope": "All manifest-listed printed STL files; binary edge topology, positive signed volume, nondegenerate triangles", "manufacturing_ready": False}
    (ROOT / "reports" / "all_meshes_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for folder in ("src", "scripts", "simulation", "graphics", "reports", "config"):
        for path in (ROOT / folder).rglob("*"):
            relative = path.relative_to(ROOT)
            if not path.is_file() or any(p in relative.parts for p in ("generated", "__pycache__", "current")) or path.suffix in (".pyc", ".log"): continue
            files.append(path)
    # Physics videos stay beside the package; include the short result document.
    if (ROOT / "RESULTS.md").exists(): files.append(ROOT / "RESULTS.md")
    # Preserve the repository layout: R2 imports these self-authored shared
    # helpers. A flattened R2-only ZIP would not be independently rebuildable.
    shared = ["cad/src/geometry.py", "cad/src/settings.py", "cad/config/parameters.yaml",
              "cad/scripts/export_parts.py", "cad/simulation/export_model.py",
              "cad/simulation/collision.py", "cad/simulation/compact_model.py",
              "cad/simulation/dynamics.py", "cad/simulation/render.py"]
    files.extend(REPO / name for name in shared)
    rebuild = ROOT / "reports/package_rebuild.json"
    if rebuild.is_file():
        check = json.loads(rebuild.read_text())
        if check["status"] != "PASS": raise ValueError("Extracted-source rebuild failed")
        for rel, value in check["sources_sha256"].items():
            if sha(REPO / rel) != value: raise ValueError("Changed source after rebuild smoke: " + rel)
    files = sorted(set(files))
    manifest = {str(path.relative_to(REPO)).replace("\\", "/"): sha(path) for path in files}
    for path in files:
        if not path.exists(): raise FileNotFoundError(path)
    out = ROOT / "package"; out.mkdir(exist_ok=True)
    file = out / "FC-R2-desktop-prototype.zip"
    with zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files: archive.write(path, "Flip-Clock/" + str(path.relative_to(REPO)).replace("\\", "/"))
        archive.writestr("Flip-Clock/PACKAGE_MANIFEST.json", json.dumps(manifest, indent=2))
        archive.writestr("Flip-Clock/README.txt", "FC-R2 prototype: see cad/r2/README.md and RESULTS.md.\nRun cad/r2/build.ps1 from this extracted Flip-Clock directory.\nThis package includes original project helper source, not third-party archive geometry.\nPhysics videos and raw solver evidence are published separately in cad/r2/review on the GitHub branch.\n")
    with zipfile.ZipFile(file) as archive:
        if archive.testzip() is not None: raise RuntimeError("ZIP CRC failure")
        for relative, value in manifest.items():
            if hashlib.sha256(archive.read("Flip-Clock/" + relative)).hexdigest() != value: raise RuntimeError("ZIP hash mismatch " + relative)
    (out / "manifest.json").write_text(json.dumps({"file": file.name, "sha256": sha(file), "bytes": file.stat().st_size, "payload_files": len(files), "parts": len(mesh_rows), "prototype_only": True, "model_sources_match_rebuild_test": rebuild.is_file(), "physics_and_hardware_acceptance": "See RESULTS.md; packaging success is not motion acceptance"}, indent=2), encoding="utf-8")
    print(json.dumps({"file": str(file), "MiB": file.stat().st_size / 2**20, "files": len(files), "meshes_checked": len(mesh_rows)}, indent=2), flush=True)


if __name__ == "__main__": main()
