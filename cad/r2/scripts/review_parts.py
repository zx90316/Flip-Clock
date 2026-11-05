"""Headless native STEP contact sheets; never open/control a desktop window."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / "tmp" / "part_review"; out.mkdir(parents=True, exist_ok=True)
    parts = json.loads((ROOT / "reports" / "parts.json").read_text())["parts"]
    selected = [r for r in parts if (not r["id"].startswith(("FM_", "FH_")) or r["id"] == "FM_08_panel")
                and not r["id"].endswith(("_post_1", "_post_2", "_flange_1", "colon_1"))]
    cadgen = Path(sys.executable).parent / "cadgen.exe"
    def shot(row):
        file = out / (row["id"] + ".png")
        cmd = [str(cadgen), "step", "snapshot", str(ROOT / row["step"]), str(file), "--width", "500", "--height", "400"]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode or not file.exists(): raise RuntimeError(row["id"] + ": " + result.stderr + result.stdout)
        print("review", row["id"], flush=True)
        return row, file
    with ThreadPoolExecutor(max_workers=2) as pool:
        images = list(pool.map(shot, selected))
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)
    sheets = []
    for page, first in enumerate(range(0, len(images), 16), 1):
        subset = images[first:first + 16]; sheet = Image.new("RGB", (1600, 4 * 350), "white"); draw = ImageDraw.Draw(sheet)
        for i, (row, file) in enumerate(subset):
            tile = Image.open(file).convert("RGB"); tile.thumbnail((394, 310))
            x, y = (i % 4) * 400, (i // 4) * 350
            sheet.paste(tile, (x, y)); draw.text((x + 8, y + 315), row["id"], font=font, fill="#22333C")
        path = out / f"sheet_{page:02}.png"; sheet.save(path); sheets.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    (ROOT / "reports" / "snapshot_review.json").write_text(json.dumps({"parts_rendered": [r["id"] for r in selected], "sheets": sheets, "purpose": "Native saved STEP review in declared print poses; no UI control", "self_review_complete": False}, indent=2), encoding="utf-8")
    print("CONTACT_SHEETS", sheets, flush=True)


if __name__ == "__main__": main()
