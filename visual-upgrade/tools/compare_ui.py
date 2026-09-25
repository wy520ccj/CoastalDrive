"""把设计参考图与实际离屏渲染上下拼接，便于逐项对照差异。

上：graphic_design 设计参考；下：visual-upgrade 的真实离屏渲染。
"""

import sys
from pathlib import Path

from panda3d.core import Filename, PNMImage

ROOT = Path(__file__).resolve().parents[1]
PAIRS = {
    "menu": (
        ROOT / "graphic_design" / "exec-2876b849-d842-4b68-a14a-905bbfd7cc20.png",
        ROOT / "logs/ui-preview/menu-wired-1672x941.png",
        ROOT / "logs/ui-preview/compare-menu.png",
    ),
    "pause": (
        ROOT / "graphic_design" / "Codex 图像 2026年9月24日 11_15_00-3.png",
        ROOT / "logs/ui-preview/page-pause.png",
        ROOT / "logs/ui-preview/compare-pause.png",
    ),
    # 场景改造的前后对照：上=改造前基线，下=当前版本
    "scene": (
        ROOT / "logs/baseline-copy/h0-offscreen.png",
        ROOT / "logs/v04d/h0-offscreen.png",
        ROOT / "logs/ui-preview/compare-scene-v04.png",
    ),
}

OUTLINE = (0.557, 0.639, 0.704)
GAP = 10


def load(path):
    image = PNMImage()
    if not image.read(Filename.fromOsSpecific(str(path))):
        raise SystemExit(f"缺少图片：{path}")
    return image


def blit(dest, src, x, y):
    for sy in range(src.getYSize()):
        for sx in range(src.getXSize()):
            dest.setXel(x + sx, y + sy, src.getRed(sx, sy), src.getGreen(sx, sy),
                        src.getBlue(sx, sy))
            alpha = src.getAlpha(sx, sy) if src.hasAlpha() else 1.0
            dest.setAlpha(x + sx, y + sy, alpha)


def stripe(dest, x, y, width, height):
    for row in range(height):
        for column in range(width):
            dest.setXel(x + column, y + row, *OUTLINE)


def compose(name):
    design_path, render_path, out_path = PAIRS[name]
    design = load(design_path)
    render = load(render_path)
    width = max(design.getXSize(), render.getXSize())
    height = design.getYSize() + GAP + render.getYSize()
    sheet = PNMImage(width, height, 4)
    sheet.fill(0.10, 0.12, 0.15)
    sheet.alphaFill(1)
    # PNMImage 的 y=0 在图像上方：设计图放上、实际渲染放下
    blit(sheet, design, 0, 0)
    stripe(sheet, 0, design.getYSize(), width, GAP)
    blit(sheet, render, 0, design.getYSize() + GAP)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.write(Filename.fromOsSpecific(str(out_path)))
    print(f"对比图：{out_path} ({width}x{height})，上=设计图 下=实际渲染")


def main():
    for name, (_, render_path, _) in PAIRS.items():
        if render_path.exists():
            compose(name)


if __name__ == "__main__":
    sys.exit(main())
