"""按统一色板生成海岸主题界面的像素面板。"""

from pathlib import Path

from panda3d.core import Filename, PNMImage

DEST = Path(__file__).resolve().parents[1] / "assets/game/ui"
INK = (0.063, 0.169, 0.227)
SHADOW = (0.42, 0.49, 0.51)
PAPER = (0.953, 0.937, 0.89)
PAPER_LIGHT = (0.99, 0.982, 0.953)
PAPER_DARK = (0.81, 0.83, 0.81)
ORANGE = (0.957, 0.486, 0.141)
ORANGE_LIGHT = (1.0, 0.65, 0.29)


def put(image, x, y, color, alpha=1):
    image.setXel(x, y, *color)
    image.setAlpha(x, y, alpha)


def rect(image, left, top, right, bottom, color):
    for y in range(top, bottom):
        for x in range(left, right):
            put(image, x, y, color)


def panel(name, width, height):
    image = PNMImage(width, height, 4)
    rect(image, 0, 0, width, height, SHADOW)
    rect(image, 0, 0, width, height - 4, INK)
    rect(image, 4, 4, width - 4, height - 8, PAPER_DARK)
    rect(image, 7, 7, width - 7, height - 11, PAPER)
    rect(image, 11, 11, width - 11, height - 15, PAPER_LIGHT)
    rect(image, 11, 11, width - 11, 14, ORANGE)
    for x, y in ((0, 0), (width - 6, 0), (0, height - 6), (width - 6, height - 6)):
        rect(image, x, y, x + 6, y + 6, PAPER_LIGHT)
    image.write(Filename.fromOsSpecific(str(DEST / name)))


def button(name, fill, top):
    width, height = 240, 40
    image = PNMImage(width, height, 4)
    rect(image, 0, 0, width, height, SHADOW)
    rect(image, 0, 0, width, height - 4, INK)
    rect(image, 3, 3, width - 3, height - 7, fill)
    rect(image, 7, 5, width - 7, 8, top)
    for x, y in ((0, 0), (width - 4, 0), (0, height - 4), (width - 4, height - 4)):
        rect(image, x, y, x + 4, y + 4, PAPER_LIGHT)
    image.write(Filename.fromOsSpecific(str(DEST / name)))


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    panel("panel.png", 256, 320)
    panel("panel-wide.png", 384, 256)
    button("button.png", PAPER_LIGHT, PAPER_DARK)
    button("button-hover.png", (1.0, 0.91, 0.76), ORANGE)
    button("button-pressed.png", PAPER_DARK, INK)
    button("button-primary.png", ORANGE, ORANGE_LIGHT)


if __name__ == "__main__":
    main()
