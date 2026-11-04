"""The new design reads its own parameters only, never source/original/."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parameters():
    return json.loads((ROOT / "config" / "parameters.yaml").read_text(encoding="utf-8"))


def values():
    return {key: record["value"] for key, record in parameters()["parameters"].items()}
