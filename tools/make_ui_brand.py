"""生成项目自有的海岸道路图标；各尺寸直接绘制，不依赖外部插画。"""

import math
import struct
import sys
from pathlib import Path

from panda3d.core import Filename, PNMImage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ui import theme

DEST = ROOT / "assets/game/ui"
SIZES = (16, 32, 48, 64, 128, 256)


def draw_icon(size):
    image = PNMImage(size, size, 4)
    for y in range(size):
        for x in range(size):
            u, v = (x + 0.5) / size, (y + 0.5) / size
            color = theme.PAPER if v < 0.48 else theme.SEA
            if (u - 0.76) ** 2 + (v - 0.25) ** 2 < 0.105 ** 2:
                color = theme.ORANGE
            if v >= 0.40:
                center = 0.5 + 0.11 * math.sin((v - 0.4) * math.tau)
                half_width = 0.04 + (v - 0.4) * 0.25
                distance = abs(u - center)
                if distance < half_width + 0.025:
                    color = theme.PAPER_LIGHT
                if distance < half_width:
                    color = theme.INK
                if distance < 0.016 and int((v - 0.4) * 12) % 2 == 0:
                    color = theme.ORANGE
            image.setXel(x, y, *color[:3])
            # 角落透明同时保证 PNG 保留 alpha。
            image.setAlpha(x, y, 0 if min(x, y, size - 1 - x, size - 1 - y) == 0 else 1)
    return image


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    images = []
    for size in SIZES:
        path = DEST / f"coastal-drive-icon-{size}.png"
        if not draw_icon(size).write(Filename.fromOsSpecific(str(path))):
            raise OSError(f"无法生成图标：{path}")
        images.append((size, path.read_bytes()))
    # Windows ICO 内嵌原生 PNG，目录中保留每个尺寸供检查。
    offset = 6 + len(images) * 16
    header = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    for size, data in images:
        dimension = size if size < 256 else 0
        header.extend(struct.pack("<BBBBHHII", dimension, dimension, 0, 0,
                                  1, 32, len(data), offset))
        offset += len(data)
    (DEST / "coastal-drive.ico").write_bytes(header + b"".join(data for _, data in images))


if __name__ == "__main__":
    main()
