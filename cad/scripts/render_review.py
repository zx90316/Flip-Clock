"""Use text-to-cad's saved-document snapshots, never source as image input."""
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
CLI=str(Path(sys.executable).with_name("cadgen.exe"))


def main():
    out=ROOT/"tmp"/"review"
    out.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for path in sorted((ROOT/"STEP").glob("*.step")):
        views=[{"path":str(out/(path.stem+".png")),"camera":{"direction":[1.4,2,1.1]}}]
        if path.stem=="assembly":
            views.extend([{"path":str(out/"assembly_rear.png"),"camera":{"direction":[-1.4,-2,1]}},
                          {"path":str(out/"assembly_side.png"),"camera":{"direction":[1,0,0]}}])
        if path.stem in ("clutch_minute","clutch_hour","coupon_plate"):
            views=[{"path":str(out/(path.stem+".png")),"camera":"top"}]
        jobs.append({"input":str(path),"mode":"view","outputs":views,
                     "output":{"sizeProfile":"simple","padding":.08},
                     "display":{"mode":"solid","edges":{"enabled":False}}})
    jobfile=out/"snapshot_jobs.json"
    jobfile.write_text(json.dumps(jobs,indent=2),encoding="utf-8")
    return subprocess.call([CLI,"step","snapshot","--job",str(jobfile)],cwd=ROOT)


if __name__=="__main__":raise SystemExit(main())
