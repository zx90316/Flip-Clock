import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from cadgen import read_scene

root = Path(__file__).resolve().parents[1]
archive_path = root / "package/FC-R2-desktop-prototype.zip"
destination = root / "tmp/package_source_smoke"
destination.mkdir(exist_ok=True)
with zipfile.ZipFile(archive_path) as archive:
    for name in archive.namelist():
        if name.endswith((".py", ".json", ".yaml")) and ("/src/" in name or "/config/" in name or name.endswith("/parameters.json")):
            target = (destination / name).resolve()
            if not target.is_relative_to(destination.resolve()): raise ValueError("Unsafe archive path")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
source = destination / "Flip-Clock/cad/r2/src/assembly_with_drag.py"
completed = subprocess.run([sys.executable, str(source)], cwd=destination / "Flip-Clock", capture_output=True, text=True, encoding="utf-8")
if completed.returncode: raise RuntimeError(completed.stdout + completed.stderr)
print(completed.stdout[-1200:], flush=True)
rebuilt = destination / "Flip-Clock/cad/r2/STEP/assembly_with_drag.step"
scenes = [read_scene(str(path)) for path in (root / "STEP/assembly_with_drag.step", rebuilt)]
rows = []
for scene in scenes:
    leaves = list(scene.leaves())
    rows.append({"leaves": len(leaves), "sum_volume_mm3": sum(n.shape().volume for n in leaves),
                 "label_order": [n.label for n in leaves]})
okay = rows[0]["leaves"] == rows[1]["leaves"] and rows[0]["label_order"] == rows[1]["label_order"] and abs(rows[0]["sum_volume_mm3"] - rows[1]["sum_volume_mm3"]) < 1e-4
result = {"status": "PASS" if okay else "FAIL", "scope": "Rebuilt complete candidate from extracted archive source and shared helpers in preserved folder layout, then read back both STEP files",
          "package_sha256_tested": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "native_leaf_count": rows[1]["leaves"],
          "volume_difference_mm3": rows[1]["sum_volume_mm3"] - rows[0]["sum_volume_mm3"],
          "final_archive_note": "Final archive will additionally contain later reports; all model/helper/config bytes must retain these hashes.",
          "sources_sha256": {str(p.relative_to(destination / "Flip-Clock")).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in (destination / "Flip-Clock").rglob("*") if p.is_file() and p.suffix in (".py", ".yaml", ".json") and "__pycache__" not in p.parts and "STEP" not in p.parts}}
(root / "reports/package_rebuild.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "sources_sha256"}, indent=2), flush=True)
if not okay: raise SystemExit(1)
