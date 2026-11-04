"""Publish one completed run and its comparisons, without machine caches."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def copy_file(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,destination)


def main():
    p=argparse.ArgumentParser();p.add_argument("--main",required=True);p.add_argument("--zero",required=True);p.add_argument("--fine",required=True);a=p.parse_args()
    run=(ROOT/a.main).resolve();destination=ROOT/"review"/"physics"
    summary=json.loads((run/"summary.json").read_text(encoding="utf-8"))
    if summary["status"]!="COMPLETED" or summary["warning_counts"]:raise ValueError("Only a completed, warning-free run can be the review")
    if destination.exists() and (destination/"summary.json").exists():
        previous=json.loads((destination/"summary.json").read_text(encoding="utf-8"))
        if previous["run_id"]!=summary["run_id"]:raise ValueError("Existing review is from another run; preserve it explicitly first")
    files=("summary.json","states.npz","contact_points.json.gz","energy.csv","trajectory.csv","contacts.csv.gz","render.json","physics.mp4","front.mp4","rear.mp4","poster.png","initial.png")
    for name in files:copy_file(run/name,destination/name)
    for name in ("model.xml","manifest.json"):copy_file(run/"model"/name,destination/"model"/name)
    for path in (run/"model"/"assets").glob("*.stl"):copy_file(path,destination/"model"/"assets"/path.name)
    for path in (run/"source").glob("*.py"):copy_file(path,destination/"source"/path.name)
    copy_file(run/"run_config.json",destination/"provenance"/"source_run_config.json")
    render_info=json.loads((run/"render.json").read_text(encoding="utf-8"))
    candidates=[run/"render_source.py",destination/"provenance"/"render_source.py",ROOT/"simulation"/"render.py"]
    render_source=next((path for path in candidates if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==render_info["render_code_sha256"]),None)
    if render_source is None:raise ValueError("Matching historical render source is missing; render the run again before publishing")
    if render_source.resolve()!=(destination/"provenance"/"render_source.py").resolve():copy_file(render_source,destination/"provenance"/"render_source.py")
    config=json.loads((run/"run_config.json").read_text(encoding="utf-8"))
    config["omitted_derived_cache_sha256"]={k:v for k,v in config["assets_sha256"].items() if k in ("model.mjb","compiled.json")}
    config["assets_sha256"]={k:v for k,v in config["assets_sha256"].items() if k not in config["omitted_derived_cache_sha256"]}
    config["published_subset"]=True
    (destination/"run_config.json").write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8")
    for label,source in (("zero-gravity",a.zero),("timestep-half",a.fine)):
        source=(ROOT/source).resolve()
        for name in ("run_config.json","summary.json","states.npz"):copy_file(source/name,destination/"comparisons"/label/name)
    (destination/".gitignore").write_text("**/*.mjb\n**/compiled.json\n__pycache__/\n*.pyc\n",encoding="utf-8")
    (destination/"README.md").write_text(
        "# 已保存的 FC-R1 物理回放\n\n"
        "這是 2026-11-04 完成的 1.6 秒 MuJoCo 3.17.0 探索性運算。\n\n"
        "- [整機影片](physics.mp4) · [翻片近看](front.mp4) · [傳動背面](rear.mp4)\n"
        "- [操作及限制](../../PHYSICS_VIEW.md) · [數值結果](../../reports/physics_assessment.json)\n"
        "- states.npz 保存積分結果；紅點取自 contact_points.json.gz。\n"
        "- model/ 包含可重新編譯的物理模型與自有 CAD 視覺網格，不包含原作者模型。\n"
        "- source/ 保存運算當時的程式，provenance/ 保存來源設定與影片渲染程式。\n"
        "- comparisons/ 保存相同模型的無重力及較小時間步長對照；共用主模型。\n"
        "- 省略 .mjb 與 compiled.json 引擎快取，首次開啟時自動從 XML/STL 建立。\n\n"
        "互動視窗尚待使用者自行確認；尚未完成實測校準、定位保持與單片放行驗收。\n"
        "資料是 concept_only，physics_verified 與 manufacturing_ready 均為 false。\n",encoding="utf-8")
    payload={str(path.relative_to(destination)).replace("\\","/"):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(destination.rglob("*")) if path.is_file() and path.name!="PUBLISH_MANIFEST.json" and path.suffix!=".mjb" and path.name!="compiled.json" and "__pycache__" not in path.parts}
    audit_path=ROOT/"reports"/"original_manifest.json"
    excluded=[]
    if audit_path.exists():
        audit=json.loads(audit_path.read_text(encoding="utf-8"))
        excluded=sorted({r["sha256"] for r in audit["files"]}|{audit["archive_sha256"]})
    report={"schema_version":1,"run_id":summary["run_id"],"status":"EXPLORATORY_COMPLETED","original_author_geometry_included":False,"compiled_caches_included":False,"physics_verified":False,"files":payload,
        "excluded_author_payload_sha256":excluded,"exclusion_check_scope":"Exact byte hashes only; not a legal freedom-to-operate assessment."}
    (destination/"PUBLISH_MANIFEST.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"directory":str(destination),"files":len(payload),"bytes":sum((destination/name).stat().st_size for name in payload)}))


if __name__=="__main__":main()
