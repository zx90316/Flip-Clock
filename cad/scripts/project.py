"""Reproducible CAD tasks. 0=PASS, 1=FAIL, 2=BLOCKED, never fake a simulation."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def run_python(script,*args):
    return subprocess.call([sys.executable,str(ROOT/script),*args],cwd=ROOT)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("doctor")
    audit=sub.add_parser("audit-original"); audit.add_argument("--input",required=True)
    build=sub.add_parser("build-cad"); build.add_argument("--config",default="config/parameters.yaml")
    build.add_argument("--model",default="assembly",choices=["assembly","coupon_plate","clutch_test_rig","all"])
    sub.add_parser("check-geometry").add_argument("--all",action="store_true")
    sub.add_parser("render")
    sub.add_parser("drawings")
    sub.add_parser("export-parts")
    sub.add_parser("viewer")
    phys=sub.add_parser("export-physics");phys.add_argument("--units",choices=["SI"],default="SI");phys.add_argument("--scope",choices=["full","clutch"],default="full")
    sim=sub.add_parser("simulate");sim.add_argument("--case",choices=["gravity","drive","clutch_forward","clutch_reverse"],default="gravity");sim.add_argument("--seed",default=0);sim.add_argument("--headless",action="store_true")
    sim.add_argument("--duration",type=float,default=1.2);sim.add_argument("--dt",type=float,default=.00002);sim.add_argument("--gravity",type=float,default=9.81);sim.add_argument("--scope",choices=["full","clutch"],default="full")
    sub.add_parser("physics-view")
    package=sub.add_parser("package");package.add_argument("--prototype",action="store_true");package.add_argument("--require",default="geometry,physics,hardware")
    args=parser.parse_args()
    if args.command=="doctor":
        from cadgen import build123d as bd
        info={"status":"PASS" if bd.Box(1,1,1).is_valid else "FAIL",
              "cadgen":importlib.metadata.version("cadgen"),"build123d":importlib.metadata.version("build123d"),
              "python":sys.version,"platform":platform.platform(),"interpreter":sys.executable,
              "native_parameter_model":"Python/build123d using text-to-cad cadgen 0.7.17",
              "FreeCAD_available":bool(importlib.util.find_spec("FreeCAD")),
              "PyChrono_available":bool(importlib.util.find_spec("pychrono")),
              "physics_selftest":"NOT_RUN","kernel_unit_cube_mm3":bd.Box(1,1,1).volume}
        write(ROOT/"reports"/"environment.json",info)
        print(json.dumps(info,ensure_ascii=False,indent=2));return 0 if info["status"]=="PASS" else 1
    if args.command=="audit-original":return run_python("scripts/audit_original.py","--input",args.input)
    if args.command=="build-cad":
        cfg=(ROOT/args.config).resolve()
        if cfg != (ROOT/"config/parameters.yaml").resolve():
            print("BLOCKED: this design uses config/parameters.yaml; edit that authoritative file.");return 2
        models=["assembly","coupon_plate","clutch_test_rig"] if args.model=="all" else [args.model]
        for model in models:
            result=run_python(f"src/{model}.py")
            if result:return result
        return 0
    if args.command=="check-geometry":return run_python("checks/check_geometry.py")
    if args.command=="render":return run_python("scripts/render_review.py")
    if args.command=="drawings":return run_python("src/critical_parts_drawing.py")
    if args.command=="export-parts":return run_python("scripts/export_parts.py")
    if args.command=="viewer":
        return subprocess.call([str(Path(sys.executable).with_name("cadgen.exe")),"viewer","--host","127.0.0.1","--json","--detach"],cwd=ROOT)
    if args.command in ("simulate","export-physics"):
        command=["powershell.exe","-NoProfile","-File",str(ROOT/"physics.ps1")]
        if args.command=="export-physics":command += ["build","--scope",args.scope]
        else:command += ["run","--case",args.case,"--scope",args.scope,"--duration",str(args.duration),"--dt",str(args.dt),"--gravity",str(args.gravity),"--seed",str(args.seed)]
        return subprocess.call(command,cwd=ROOT)
    if args.command=="physics-view":return subprocess.call(["powershell.exe","-NoProfile","-File",str(ROOT/"physics.ps1"),"view"],cwd=ROOT)
    if args.command=="package":
        report_path=ROOT/"reports"/"geometry_check.json"
        geometry=json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
        if not args.prototype:
            print("BLOCKED: no physics/hardware/endurance evidence; manufacturing release is disabled.");return 2
        output=ROOT/"prototype_FC-R1.zip"
        paths=[ROOT/name for name in ("README.md","DESIGN.md","PHYSICS_VIEW.md","run.ps1","setup.ps1","physics.ps1","setup-physics.ps1","open-physics.ps1","VIEW_MODELS.md") if (ROOT/name).exists()]
        for directory in ("src","config","checks","scripts","STEP","STL","PDF","simulation","review"):
            paths.extend(p for p in (ROOT/directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts and "generated" not in p.parts and p.suffix not in (".mjb",".pyc") and p.name!="compiled.json")
        paths.extend(p for p in (ROOT/"reports").glob("*") if p.is_file() and not p.name.startswith("original") and p.name!="package_check.json")
        manifest={"design_id":"FC-R1","state":"concept_only","manufacturing_ready":False,
                  "original_geometry_included":False,"physics_verified":False,"hardware_verified":False,
                  "geometry_report_status":geometry.get("status","NOT_RUN"),
                  "files":{str(p.relative_to(ROOT)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
        with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("PROTOTYPE_ONLY.json",json.dumps(manifest,ensure_ascii=False,indent=2))
            for path in paths:archive.write(path,path.relative_to(ROOT))
            if (ROOT.parent/"LICENSE").exists():archive.write(ROOT.parent/"LICENSE","LICENSE")
        print(f"PASS: prototype only: {output}");return 0
    return 1


if __name__=="__main__":
    raise SystemExit(main())
