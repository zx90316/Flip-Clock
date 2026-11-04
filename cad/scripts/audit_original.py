"""Read user-supplied 3MF meshes as data; never execute archive contents."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NS = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_3mf(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        models = [n for n in archive.namelist() if n.lower().endswith(".model")]
        result = {"model_files": models, "objects": []}
        for name in models:
            tree = ET.fromstring(archive.read(name))
            result["unit"] = tree.get("unit", "millimeter")
            result["build_items"] = [dict(e.attrib) for e in tree.findall("c:build/c:item", NS)]
            for obj in tree.findall("c:resources/c:object", NS):
                vertices = [tuple(float(v.get(a)) for a in "xyz")
                            for v in obj.findall("c:mesh/c:vertices/c:vertex", NS)]
                triangles = [tuple(int(t.get(a)) for a in ("v1", "v2", "v3"))
                             for t in obj.findall("c:mesh/c:triangles/c:triangle", NS)]
                if not vertices:
                    continue
                low = [min(v[i] for v in vertices) for i in range(3)]
                high = [max(v[i] for v in vertices) for i in range(3)]
                signed_volume = 0.0
                for indices in triangles:
                    a, b, c = (vertices[i] for i in indices)
                    signed_volume += (a[0] * (b[1]*c[2]-b[2]*c[1])
                                      + a[1] * (b[2]*c[0]-b[0]*c[2])
                                      + a[2] * (b[0]*c[1]-b[1]*c[0])) / 6
                item = {"id": obj.get("id"), "name": obj.get("name"),
                        "vertices": len(vertices), "triangles": len(triangles),
                        "local_bounds_mm": [low, high],
                        "local_size_mm": [round(high[i]-low[i], 6) for i in range(3)],
                        "mesh_signed_volume_mm3": round(signed_volume, 6)}
                result["objects"].append(item)
        thumb = next((n for n in archive.namelist() if n.lower().endswith("thumbnail.png")), None)
        if thumb and path.parent.name == "Other Parts":
            dest = ROOT / "tmp" / "original_thumbnails" / (path.stem + ".png")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.read(thumb))
        return result


def audit(input_path: Path) -> dict:
    target = ROOT / "source" / "original"
    target.mkdir(parents=True, exist_ok=True)
    copied = target / "Flip+Clock+Mechanism.zip"
    if input_path.resolve() != copied.resolve():
        if copied.exists() and sha256(copied) != sha256(input_path):
            raise ValueError("The archived source differs; preserve it and use a versioned directory")
        if not copied.exists():
            shutil.copy2(input_path, copied)
    extraction = target / "extracted"
    extraction.mkdir(exist_ok=True)
    with zipfile.ZipFile(copied) as archive:
        for entry in archive.infolist():
            dest = (extraction / entry.filename).resolve()
            if not dest.is_relative_to(extraction.resolve()):
                raise ValueError(f"Unsafe archive path: {entry.filename}")
            if entry.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(entry)
            if dest.exists() and dest.read_bytes() != data:
                raise ValueError(f"Refusing to replace changed source: {entry.filename}")
            if not dest.exists():
                dest.write_bytes(data)
    files = []
    for path in sorted(extraction.rglob("*")):
        if not path.is_file():
            continue
        item = {"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size, "sha256": sha256(path)}
        if path.suffix.lower() == ".3mf":
            item["mesh"] = inspect_3mf(path)
        files.append(item)
    manifest = {"schema_version": 1, "received_on": "2026-11-04",
                "source": "user_supplied_local_archive", "author": "NotKuro",
                "source_url": "https://makerworld.com/zh/models/908946-flip-clock-mechanism",
                "archive_sha256": sha256(copied), "archive_bytes": copied.stat().st_size,
                "archive_origin": str(input_path), "license_text_in_archive": False,
                "original_native_cad_present": False,
                "assembly_manual_present": any(f["path"].lower().endswith(".pdf") for f in files),
                "measurements": "resource-local mesh bounds; not assembled positions or physical fits",
                "files": files}
    report = ROOT / "reports" / "original_manifest.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"archive_sha256": manifest["archive_sha256"], "files": len(files),
                      "manual_present": manifest["assembly_manual_present"]}))
    for item in files:
        if "/Other Parts/" in item["path"] or item["path"].endswith("24H Flap.3MF"):
            print(item["path"], [(o["local_size_mm"], o["triangles"]) for o in item["mesh"]["objects"]])
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    audit(args.input)
