"""把生成的九宫格切片与图标拼成一张放大预览板，供人工检查像素质量。"""

import sys
from pathlib import Path

from panda3d.core import Filename, PNMImage

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "assets/game/ui"
OUT = ROOT / "logs/ui-preview/ui-textures-preview.png"

SLICES = ("panel", "panel-solid", "well", "button", "button-hover", "button-pressed",
          "button-primary", "button-primary-hover", "button-selected", "pill", "chip")
ICONS = ("clock", "car", "road", "bridge", "wheel", "restart", "home", "volume", "exit",
         "check", "warning", "collision", "checkpoint", "flag", "trophy", "palm")

# 预览尺寸：面板 260x160，按钮 200x48，图标放大 3 倍
PANEL = (260, 160)
BUTTON = (200, 48)
ICON_ZOOM = 3
ICON_CELL = 32 * ICON_ZOOM


def load(path):
    image = PNMImage()
    if not image.read(Filename.fromOsSpecific(str(path))):
        raise SystemExit(f"缺少素材：{path}")
    return image


def alpha_at(image, x, y):
    """PNG 若为不透明格式则没有 alpha 通道，此时视为完全不透明。"""
    return image.getAlpha(x, y) if image.hasAlpha() else 1.0


def blit(dest, src, x, y, zoom=1):
    for sy in range(src.getYSize()):
        for sx in range(src.getXSize()):
            alpha = alpha_at(src, sx, sy)
            if alpha <= 0.02:
                continue
            color = (src.getRed(sx, sy), src.getGreen(sx, sy), src.getBlue(sx, sy))
            for dy in range(zoom):
                for dx in range(zoom):
                    px, py = x + sx * zoom + dx, y + sy * zoom + dy
                    if 0 <= px < dest.getXSize() and 0 <= py < dest.getYSize():
                        dest.setXel(px, py, *color)
                        dest.setAlpha(px, py, alpha)


def draw_nine(dest, name, x, y, width, height):
    """按九宫格拼接，验证边角不拉伸。"""
    corner = 12
    parts = {
        "topleft": (x, y, corner, corner),
        "top": (x + corner, y, width - 2 * corner, corner),
        "topright": (x + width - corner, y, corner, corner),
        "left": (x, y + corner, corner, height - 2 * corner),
        "center": (x + corner, y + corner, width - 2 * corner, height - 2 * corner),
        "right": (x + width - corner, y + corner, corner, height - 2 * corner),
        "bottomleft": (x, y + height - corner, corner, corner),
        "bottom": (x + corner, y + height - corner, width - 2 * corner, corner),
        "bottomright": (x + width - corner, y + height - corner, corner, corner),
    }
    for piece, (px, py, pw, ph) in parts.items():
        image = load(UI / f"{name}-{piece}.png")
        for dy in range(ph):
            for dx in range(pw):
                sx = min(image.getXSize() - 1, int(dx * image.getXSize() / pw))
                sy = min(image.getYSize() - 1, int(dy * image.getYSize() / ph))
                alpha = alpha_at(image, sx, sy)
                if alpha <= 0.02:
                    continue
                dest.setXel(px + dx, py + dy, image.getRed(sx, sy), image.getGreen(sx, sy),
                            image.getBlue(sx, sy))
                dest.setAlpha(px + dx, py + dy, alpha)


def main():
    columns = 4
    rows = 1 + (len(SLICES) + columns - 1) // columns
    icon_rows = (len(ICONS) + 7) // 8
    width = 96 + columns * (PANEL[0] + 24)
    height = 40 + 30 + rows * (PANEL[1] + 20) + 20 + icon_rows * (ICON_CELL + 30) + 50
    sheet = PNMImage(width, height, 4)
    # 浅灰蓝底，方便同时看清浅色面板与深蓝图标
    sheet.fill(0.42, 0.47, 0.52)
    sheet.alphaFill(1)

    # 参考色块：奶白纸面、深海蓝、橙、金
    for index, color in enumerate(((0.953, 0.937, 0.89), (0.063, 0.169, 0.227),
                                   (0.957, 0.486, 0.141), (1.0, 0.761, 0.278))):
        for y in range(height - 40, height - 12):
            for x in range(20 + index * 60, 20 + index * 60 + 52):
                sheet.setXel(x, y, *color)

    for index, name in enumerate(SLICES):
        row, column = divmod(index, columns)
        x = 40 + column * (PANEL[0] + 24)
        y = 40 + 30 + row * (PANEL[1] + 20)
        draw_nine(sheet, name, x, y, PANEL[0], PANEL[1])
        draw_nine(sheet, name, x + 20, y + 20, BUTTON[0], BUTTON[1])

    icon_top = 40 + 30 + rows * (PANEL[1] + 20) + 16
    for index, name in enumerate(ICONS):
        row, column = divmod(index, 8)
        x = 40 + column * (ICON_CELL + 16)
        y = icon_top + row * (ICON_CELL + 30)
        blit(sheet, load(UI / f"icon-{name}.png"), x, y, ICON_ZOOM)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.write(Filename.fromOsSpecific(str(OUT)))
    print(f"预览板：{OUT} ({width}x{height})")


if __name__ == "__main__":
    sys.exit(main())
