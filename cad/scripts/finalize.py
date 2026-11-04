"""Bind actual reports, dependency versions, viewer links, and CAD review evidence."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime,timezone,timedelta
import hashlib
import importlib.metadata
import json
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--viewer-url",required=True)
    parser.add_argument("--snapshots-reviewed",action="store_true")
    parser.add_argument("--pdf-reviewed",action="store_true")
    args=parser.parse_args()
    geometry=json.loads((ROOT/"reports"/"geometry_check.json").read_text(encoding="utf-8"))
    parts=json.loads((ROOT/"reports"/"parts_catalog.json").read_text(encoding="utf-8"))
    if geometry["document_hash"]!=parts["source_document_hash"]:
        raise ValueError("Geometry report and prototype parts refer to different assembly revisions")
    # Refresh only material metadata; the already checked geometry stays unchanged.
    for part in parts["parts"]:
        if part["id"].startswith("A04_"):part["material"]="TPU proposal"
    (ROOT/"reports"/"parts_catalog.json").write_text(json.dumps(parts,ensure_ascii=False,indent=2),encoding="utf-8")
    with (ROOT/"reports"/"bom.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.writer(stream);writer.writerow(["ID","quantity","material_proposal","print_orientation","STEP","STL","status"])
        for part in parts["parts"]:writer.writerow([part["id"],part["quantity"],part["material"],part["print_orientation"],part["step"],part["stl"],part["mesh_check"]["status"]])
    report={"design_id":"FC-R1","state":"concept_only",
        "updated_at":datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).isoformat(),
        "original_author_geometry_used":False,"original_files_packaged":False,
        "selected_L0_geometry":{"status":geometry["status"],"pass":geometry["pass"],"fail":geometry["fail"],"evidence":"geometry_check.json"},
        "prototype_part_meshes":{"status":parts["status"],"definitions":len(parts["parts"]),"evidence":"parts_catalog.json"},
        "snapshot_review":{"status":"PASS" if args.snapshots_reviewed else "NOT_RUN","evidence":"tmp/review/*.png","scope":"static visible geometry only"},
        "nominal_drawing_review":{"status":"PASS" if args.pdf_reviewed else "NOT_RUN","evidence":"PDF/critical_parts_drawing.pdf","tolerances_frozen":False},
        "continuous_full_assembly_collision":{"status":"NOT_RUN"},
        "physics":{"status":"NOT_RUN","reason":"No recorded exploratory run for this CAD revision; physical calibration remains incomplete"},
        "motor_calibration":{"status":"BLOCKED","reason":"Torque-speed curve, actual ratio and reversal backlash not measured"},
        "hardware":{"status":"NOT_RUN"},"endurance":{"status":"NOT_RUN"},
        "geometry_verified":False,"physics_verified":False,"hardware_verified":False,
        "manufacturing_ready":False,"release":{"status":"BLOCKED"},
        "assembly_sha256":hashlib.sha256((ROOT/"STEP"/"assembly.step").read_bytes()).hexdigest(),
        "native_main_file":"src/assembly.py","parameter_file":"config/parameters.yaml"}
    latest=ROOT/"reports"/"physics_latest.json"
    if latest.exists():
        pointer=json.loads(latest.read_text(encoding="utf-8"));run=(ROOT/Path(pointer.get("relative_directory",pointer["directory"]))).resolve()
        manifest=json.loads((run/"model"/"manifest.json").read_text(encoding="utf-8"))
        if manifest["cad_sha256"]==report["assembly_sha256"]:
            result=json.loads((run/"summary.json").read_text(encoding="utf-8"))
            report["physics"]={"status":"EXPLORATORY_RUN","run_status":result["status"],"engine":"MuJoCo "+manifest["version"],"evidence":str(run.relative_to(ROOT)).replace("\\","/")+"/summary.json","calibrated":False,"physics_verified":False}
    (ROOT/"reports"/"verification.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    inventory={d.metadata["Name"]:d.version for d in importlib.metadata.distributions() if d.metadata["Name"]}
    (ROOT/"config"/"dependencies.lock.json").write_text(json.dumps({"runtime":"CPython 3.13.15","packages":dict(sorted(inventory.items(),key=lambda x:x[0].lower()))},indent=2)+"\n",encoding="utf-8")
    lines=["# FC-R1 模型目錄","","本機 CAD Viewer；所有模型均為 concept_only 工程原型。", "",
           f"本次檢查：{geometry['pass']} 項指定幾何檢查通過；完整動態與實機驗證另列待完成。", "",
           "## 整機與子系統",""]
    def link(path):return args.viewer_url.rstrip("/")+"/?file="+quote(str(path.resolve()),safe="")
    for path in sorted((ROOT/"STEP").glob("*.step")):
        lines.append(f"- [{path.stem}]({link(path)})")
    lines.extend(["","## 原型分件","","以下 STEP 與 STL 是相同幾何的分件匯出，已沿用所屬組裝的視覺審閱。",""])
    for part in parts["parts"]:
        lines.append(f"- [{part['id']}]({link(ROOT/part['step'])})（數量 {part['quantity']}）")
    (ROOT/"VIEW_MODELS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    summary=(f"# FC-R1 交付狀態\n\n全新參數化 CAD 初版，concept_only。\n\n"
             f"- 指定幾何檢查：{geometry['pass']}/{geometry['requested_cases']} PASS。\n"
             f"- 工程原型分件：{len(parts['parts'])} 種，網格檢查 {parts['status']}。\n"
             f"- 時輪 24 片、分輪 60 片；兩支獨立輸出軸；單共同輸入。\n"
             "- 原作者網格、原尺寸及封存原檔不屬建模輸入或交付包。\n"
             "- 物理、馬達、硬體、耐久及完整連續碰撞均未通過驗收。\n\n"
             "見 verification.json 與 DESIGN.md；不得將 CAD 檢查當成完成實機證據。\n")
    (ROOT/"reports"/"delivery.md").write_text(summary,encoding="utf-8")
    print(json.dumps({"geometry":geometry["status"],"parts":len(parts["parts"]),"snapshot_review":report["snapshot_review"]["status"],"drawing_review":report["nominal_drawing_review"]["status"],"release":"BLOCKED"},ensure_ascii=False))


if __name__=="__main__":main()
