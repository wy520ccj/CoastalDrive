"""以正式主题色生成既有尺寸的底板与按钮，不改变页面布局。"""

import sys
from pathlib import Path

from panda3d.core import Filename, PNMImage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ui import theme

DEST = ROOT / "assets/game/ui"


def gradient(name, width, height, top, bottom):
    image = PNMImage(width, height, 4)
    for y in range(height):
        t = y / (height - 1)
        for x in range(width):
            grain = (((x * 17 + y * 29) % 13) - 6) / 1500
            line = 0.006 if (x + y * 2) % 37 < 2 else 0
            color = tuple(
                max(0, min(1, top[channel] * (1 - t) + bottom[channel] * t + grain + line))
                for channel in range(3)
            )
            image.setXel(x, y, *color)
            image.setAlpha(x, y, 1)
    image.write(Filename.fromOsSpecific(str(DEST / name)))


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    gradient("panel.png", 128, 256, theme.PAPER_LIGHT, theme.PAPER)
    gradient("button.png", 128, 64, theme.PAPER_LIGHT, theme.PAPER)


if __name__ == "__main__":
    main()
