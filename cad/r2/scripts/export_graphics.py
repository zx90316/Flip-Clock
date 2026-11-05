"""Own seven-segment transfer artwork at 1:1 millimetre scale, both faces.

Artwork is a finishing template, not another FDM structural feature or a
registered duplex-print claim. No third-party font or original-author artwork.
"""
from pathlib import Path
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import r2_geometry as g


def main():
    out = ROOT / "graphics"; out.mkdir(exist_ok=True)
    entries = [(b, k) for b in ("H", "M") for k in range(g.count(b))]
    for upper, face in ((True, "front"), (False, "back")):
        for page, start in enumerate(range(0, len(entries), 70), 1):
            lines = ['<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
                     '<rect width="210" height="297" fill="white"/>',
                     f'<text x="10" y="5" font-size="2.8">FC-R2 | {face} {page} | 100% / 1:1 mm | self-authored vector glyphs</text>']
            for index, (b, k) in enumerate(entries[start:start + 70]):
                col, row = index % 5, index // 5; x0 = 10 + col * 38; y0 = 9 + row * 20
                lines.append(f'<g transform="translate({x0} {y0})"><rect width="34" height="18" fill="#182228" stroke="#999" stroke-width="0.08"/>')
                value = k if upper else (k + 1) % g.count(b)
                for solid in g.digit_boxes(value, upper, .05).solids():
                    box = solid.bounding_box()
                    # +Y front is -X screen-right; rear stencil intentionally
                    # appears mirrored before rotating the physical flap about X.
                    x = 17 - box.max.X if upper else 17 + box.min.X
                    y = 18 - box.max.Z
                    lines.append(f'<rect x="{x:.5f}" y="{y:.5f}" width="{box.size.X:.5f}" height="{box.size.Z:.5f}" fill="#F4F0DF"/>')
                label = f"{b}{k:02} {face} {'upper' if upper else 'lower'} {value:02}"
                lines.append(f'<text x="0" y="19.5" fill="#333" font-size="1.4">{escape(label)}</text></g>')
            lines.append('</svg>')
            (out / f"{face}_{page:02}.svg").write_text("\n".join(lines), encoding="utf-8")
    (out / "README.md").write_text("""# FC-R2 雙面字樣轉印稿

四張 A4 SVG、100% 尺寸；每格 34 × 18 mm。H00–H23、M00–M59。

正面是本片的上半字，背面是下一片號碼的下半字。背面圖樣配合繞 X 軸翻轉，刻意鏡像；請依檔案直接製作，不要再次鏡像。正反面分開轉印／遮罩上色；本稿未宣稱印表機雙面套準。先用 M08 與 M09 兩片確認翻轉後讀值，再處理整組。

字樣為本專案自繪七段向量，不使用原作者圖樣或外部字型。這是上色／轉印圖樣，STL 保持完整 1.2 mm 薄片，不含凸字或刻槽。不同塗層厚度與磨擦必須實際驗證。
""", encoding="utf-8")
    print("Exported 4 A4 SVG sheets for 84 two-sided flaps", flush=True)


if __name__ == "__main__": main()
