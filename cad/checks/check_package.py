"""Inspect the actual ZIP: complete manifests and no archived author payloads."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    original=json.loads((ROOT/"reports"/"original_manifest.json").read_text(encoding="utf-8"))
    forbidden={row["sha256"] for row in original["files"]}|{original["archive_sha256"]}
    failures=[]
    with zipfile.ZipFile(ROOT/"prototype_FC-R1.zip") as archive:
        damaged=archive.testzip()
        if damaged:failures.append("CRC failure: "+damaged)
        names=set(archive.namelist())
        manifest=json.loads(archive.read("PROTOTYPE_ONLY.json"))
        for name,expected in manifest["files"].items():
            if name not in names:failures.append("Missing: "+name);continue
            data=archive.read(name)
            digest=hashlib.sha256(data).hexdigest()
            if digest!=expected:failures.append("Manifest hash mismatch: "+name)
            if digest in forbidden:failures.append("Original payload: "+name)
            if "source/original" in name or name.lower().endswith(".3mf"):
                failures.append("Excluded original path/type: "+name)
        for needed in ("src/assembly.py","config/parameters.yaml","run.ps1","setup.ps1","VIEW_MODELS.md", "STEP/assembly.step","PDF/critical_parts_drawing.pdf","LICENSE"):
            if needed not in names:failures.append("Required delivery missing: "+needed)
        stls=[name for name in names if name.startswith("STL/prototype/") and name.endswith(".stl")]
        parts=json.loads(archive.read("reports/parts_catalog.json"))
        if len(stls)!=len(parts["parts"]):failures.append("STL catalog count differs from archive")
        if manifest["manufacturing_ready"] or manifest["state"]!="concept_only":failures.append("Incorrect release state")
        info={"status":"FAIL" if failures else "PASS","files":len(names),"prototype_stls":len(stls),
              "original_payload_matches":0 if not any("Original payload" in s for s in failures) else None,
              "original_hashes_checked":len(forbidden),"all_manifest_hashes_checked":True,"failures":failures,
              "archive_sha256":hashlib.sha256((ROOT/"prototype_FC-R1.zip").read_bytes()).hexdigest()}
    (ROOT/"reports"/"package_check.json").write_text(json.dumps(info,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(info,ensure_ascii=False,indent=2))
    return 1 if failures else 0


if __name__=="__main__":raise SystemExit(main())
