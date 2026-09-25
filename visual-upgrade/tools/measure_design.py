"""量取设计图里主菜单的真实像素布局，用于把界面常量对齐设计。

检测方式刻意选得抗干扰：
- 面板：按行找最长的奶白连续段（云和车身的渐变不会形成长段）；
- 按钮：按列找深蓝描边（按钮上下边框比填充色可靠得多）。
"""

import sys
from pathlib import Path

from panda3d.core import Filename, PNMImage

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "graphic_design" / "exec-2876b849-d842-4b68-a14a-905bbfd7cc20.png"
REFERENCE_WIDTH = 1920


def rgb(image, x, y):
    return (image.getRed(x, y), image.getGreen(x, y), image.getBlue(x, y))


def is_cream(color, tolerance=0.05):
    return (abs(color[0] - 0.953) <= tolerance and abs(color[1] - 0.937) <= tolerance
            and abs(color[2] - 0.890) <= tolerance)


def is_ink(color, limit=0.36):
    return color[0] < limit and color[1] < limit and color[2] < limit


def longest_run(image, y, matcher, minimum):
    best = None
    start = None
    for x in range(image.getXSize()):
        if matcher(rgb(image, x, y)):
            if start is None:
                start = x
        else:
            if start is not None and x - start >= minimum and (
                    best is None or x - start > best[1] - best[0]):
                best = (start, x - 1)
            start = None
    if start is not None and image.getXSize() - start >= minimum and (
            best is None or image.getXSize() - start > best[1] - best[0]):
        best = (start, image.getXSize() - 1)
    return best


def spans_along_column(image, x, matcher, minimum=2):
    spans = []
    start = None
    for y in range(image.getYSize()):
        if matcher(rgb(image, x, y)):
            if start is None:
                start = y
        elif start is not None:
            if y - start >= minimum:
                spans.append((start, y - 1))
            start = None
    return spans


def main():
    image = PNMImage()
    if not image.read(Filename.fromOsSpecific(str(DESIGN))):
        raise SystemExit(f"读不到设计图：{DESIGN}")
    scale = REFERENCE_WIDTH / image.getXSize()
    print(f"设计图 {image.getXSize()}x{image.getYSize()}  -> 1920 参考宽 ×{scale:.4f}")

    # 面板范围
    top = bottom = None
    left = image.getXSize()
    right = 0
    for y in range(image.getYSize()):
        run = longest_run(image, y, is_cream, 300)
        if run is None:
            continue
        top = y if top is None else top
        bottom = y
        left = min(left, run[0])
        right = max(right, run[1])
    print(f"面板: 设计px x {left}..{right}  y {top}..{bottom}"
          f"   参考px x {round(left * scale)}..{round(right * scale)}"
          f"  y {round(top * scale)}..{round(bottom * scale)}"
          f"  宽 {round((right - left) * scale)} 高 {round((bottom - top) * scale)}")

    # 按钮上下边框：在面板内中轴列上找深蓝描边
    axis = left + int((right - left) * 0.6)
    edges = [span[0] for span in spans_along_column(image, axis, is_ink, 1)]
    print(f"沿 x={axis}（参考 {round(axis * scale)}）的深蓝描边采样 y："
          f"{[round(v * scale) for v in edges][:24]}")


if __name__ == "__main__":
    sys.exit(main())
