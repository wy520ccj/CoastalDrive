"""生成 6B-08 界面底板和按钮的蓝灰渐变纹理。"""

from pathlib import Path

from panda3d.core import Filename, PNMImage

ROOT = Path(__file__).resolve().parents[1]
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
    gradient("panel.png", 128, 256, (0.075, 0.105, 0.145), (0.018, 0.032, 0.052))
    gradient("button.png", 128, 64, (0.26, 0.39, 0.51), (0.12, 0.21, 0.30))


if __name__ == "__main__":
    main()
