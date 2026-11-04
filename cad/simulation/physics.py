"""Actual rigid-body gravity/contact simulation. No prescribed output angles."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("doctor")
    build=sub.add_parser("build");build.add_argument("--scope",choices=["full","clutch"],default="full")
    refresh=sub.add_parser("refresh");refresh.add_argument("--scope",choices=["full","clutch"],default="full")
    run=sub.add_parser("run");run.add_argument("--case",default="gravity");run.add_argument("--duration",type=float,default=1.2)
    run.add_argument("--dt",type=float,default=.00002);run.add_argument("--seed",type=int,default=0)
    run.add_argument("--contact-time",type=float,default=.0006)
    run.add_argument("--solver",choices=["Newton","CG","PGS"],default="Newton");run.add_argument("--iterations",type=int,default=100)
    run.add_argument("--gravity",type=float,default=9.81);run.add_argument("--scope",choices=["full","clutch"],default="full")
    run.add_argument("--no-pawl-contact",action="store_true");run.add_argument("--torque-scale",type=float,default=1)
    video=sub.add_parser("render");video.add_argument("--run",required=True)
    view=sub.add_parser("view");view.add_argument("--scope",choices=["full","clutch"],default="full")
    replay=sub.add_parser("replay");replay.add_argument("--run",required=True)
    args=parser.parse_args()
    if args.command=="doctor":
        from selftest import run_selftests
        return run_selftests()
    if args.command=="build":
        from export_model import build_model
        build_model(args.scope);return 0
    if args.command=="refresh":
        from scene_options import refresh_options
        refresh_options(ROOT/"simulation"/"generated"/args.scope);return 0
    if args.command=="run":
        from runner import run_case
        return run_case(args)
    if args.command=="render":
        from render import render_run
        return render_run(Path(args.run))
    if args.command in ("view","replay"):
        from live_view import launch
        return launch(args)
    return 1


if __name__=="__main__":raise SystemExit(main())
