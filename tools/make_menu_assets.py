"""用 Panda3D 原生 PNMImage 绘制无文字的菜单组件与像素图标。"""

from itertools import pairwise
from pathlib import Path

from panda3d.core import Filename, PNMImage

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets/game/ui/components"

INK = (16 / 255, 43 / 255, 58 / 255)
PAPER = (243 / 255, 239 / 255, 227 / 255)
WHITE = (254 / 255, 252 / 255, 245 / 255)
ORANGE = (244 / 255, 124 / 255, 36 / 255)
GOLD = (1.0, 189 / 255, 63 / 255)
MUTED = (150 / 255, 160 / 255, 158 / 255)
SHADE = (30 / 255, 55 / 255, 65 / 255)


def image(width, height, color=None):
    result = PNMImage(width, height, 4)
    for y in range(height):
        for x in range(width):
            result.setXel(x, y, *(color or (0, 0, 0)))
            result.setAlpha(x, y, 0 if color is None else 1)
    return result


def rect(img, x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(img.getYSize(), y1)):
        for x in range(max(0, x0), min(img.getXSize(), x1)):
            img.setXel(x, y, *color)
            img.setAlpha(x, y, 1)


def stepped_rect(img, x0, y0, x1, y1, step, color):
    rect(img, x0 + step, y0, x1 - step, y1, color)
    rect(img, x0, y0 + step, x1, y1 - step, color)
    rect(img, x0 + step // 2, y0 + step // 2, x1 - step // 2, y1 - step // 2, color)


def pixel_line(img, points, color, width=4):
    """用粗像素段连接点，适合 64px 符号图标。"""
    for (x0, y0), (x1, y1) in pairwise(points):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        error = dx - dy
        while True:
            rect(img, x0 - width // 2, y0 - width // 2,
                 x0 + (width + 1) // 2, y0 + (width + 1) // 2, color)
            if x0 == x1 and y0 == y1:
                break
            twice = error * 2
            if twice > -dy:
                error -= dy
                x0 += sx
            if twice < dx:
                error += dx
                y0 += sy


def outline_box(img, x0, y0, x1, y1, color, thickness=3):
    rect(img, x0, y0, x1, y0 + thickness, color)
    rect(img, x0, y1 - thickness, x1, y1, color)
    rect(img, x0, y0, x0 + thickness, y1, color)
    rect(img, x1 - thickness, y0, x1, y1, color)


def fill_poly(img, points, color):
    """以水平像素行填充简单多边形。"""
    low = max(0, min(y for _, y in points))
    high = min(img.getYSize(), max(y for _, y in points) + 1)
    for y in range(low, high):
        scan_y = y + 0.5
        crossings = []
        for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
            if (y0 <= scan_y < y1) or (y1 <= scan_y < y0):
                crossings.append(x0 + (scan_y - y0) * (x1 - x0) / (y1 - y0))
        crossings.sort()
        for left, right in zip(crossings[::2], crossings[1::2]):
            rect(img, int(left + 0.5), y, int(right + 0.5), y + 1, color)


def circle_blocks(img, cx, cy, radius, color, block=4, inner=None):
    for y in range(cy - radius, cy + radius + 1, block):
        for x in range(cx - radius, cx + radius + 1, block):
            d2 = (x + block / 2 - cx) ** 2 + (y + block / 2 - cy) ** 2
            if (radius - block) ** 2 <= d2 <= radius ** 2:
                rect(img, x, y, x + block, y + block, color)
            elif inner is not None and d2 < (radius - block) ** 2:
                rect(img, x, y, x + block, y + block, inner)


def button(width, height, kind, state):
    canvas = image(width, height)
    scale = max(1, width // 512)
    # 512×112 源图上的边线分别为 2px、1px 与 2px。
    edge_width, highlight_width, shadow_width = 2 * scale, 1 * scale, 2 * scale
    step = 3 * scale
    if state == "disabled":
        fill, edge, highlight, shadow = (220 / 255, 221 / 255, 214 / 255), MUTED, WHITE, MUTED
    elif kind == "primary":
        fill = ORANGE if state != "pressed" else (210 / 255, 93 / 255, 28 / 255)
        edge = GOLD if state == "hover" else INK
        highlight, shadow = (1, 172 / 255, 79 / 255), (158 / 255, 70 / 255, 25 / 255)
    else:
        fill = WHITE if state == "hover" else PAPER
        edge = GOLD if state == "hover" else INK
        highlight, shadow = WHITE, SHADE

    pressed = state == "pressed"
    offset = 3 * scale if pressed else 0
    # 独立投影与细双边框让组件离开背景后仍有清楚边界。
    x0, y0, x1, y1 = 2 * scale, 2 * scale + offset, width - 2 * scale, height - 4 * scale + offset
    stepped_rect(canvas, x0, y0 + shadow_width, x1, y1 + shadow_width,
                 step, shadow)
    stepped_rect(canvas, x0, y0, x1, y1, step, edge)
    inset = edge_width
    stepped_rect(canvas, x0 + inset, y0 + inset, x1 - inset, y1 - inset,
                 max(2, step - 1), fill)
    # 顶部仅留一道像素高的亮线，避免边框压过按钮文字。
    rect(canvas, x0 + step, y0 + inset, x1 - step, y0 + inset + highlight_width, highlight)
    if state == "disabled":
        # 保持状态本身干净，不附加文字或不可辨识图案。
        pass
    return canvas


def framed_panel(width, height, dark=False):
    base = SHADE if dark else PAPER
    edge = PAPER if dark else INK
    canvas = image(width, height)
    step = max(8, min(width, height) // 64)
    margin = max(3, min(width, height) // 128)
    stepped_rect(canvas, 0, 0, width, height, step, edge)
    stepped_rect(canvas, margin, margin, width - margin, height - margin,
                 max(4, step - margin), base)
    inset = max(4, min(width, height) // 48)
    inner = WHITE
    stepped_rect(canvas, inset, inset, width - inset, height - inset,
                 max(4, step // 2), inner if dark else (0.94, 0.91, 0.84))
    # 内层大面板回到纯纸色/深海蓝，留下极细的装饰双线。
    content_margin = inset + max(2, step // 2)
    stepped_rect(canvas, content_margin, content_margin, width - content_margin,
                 height - content_margin, max(4, step // 2), base)
    return canvas


def draw_icon(name):
    img = image(64, 64)
    c = INK
    if name == "stopwatch":
        outline_box(img, 27, 4, 37, 12, c, 4)
        circle_blocks(img, 32, 37, 22, c, 4)
        circle_blocks(img, 32, 37, 17, c, 4, WHITE)
        pixel_line(img, [(32, 37), (32, 23), (42, 18)], c, 4)
        rect(img, 17, 13, 24, 18, c)
    elif name == "palm":
        fill_poly(img, [(29, 60), (32, 28), (37, 20), (40, 21), (37, 34), (35, 60)], c)
        fill_poly(img, [(32, 25), (19, 21), (7, 13), (21, 15), (33, 21)], c)
        fill_poly(img, [(32, 23), (26, 10), (30, 4), (37, 15), (36, 23)], c)
        fill_poly(img, [(34, 22), (43, 9), (51, 7), (45, 17), (37, 26)], c)
        fill_poly(img, [(35, 23), (48, 17), (59, 20), (51, 27), (37, 28)], c)
        fill_poly(img, [(31, 25), (21, 25), (6, 31), (20, 30), (33, 29)], c)
    elif name == "highway":
        # 道路是完整深色梯形，中心用纸白短虚线刻出车道线。
        fill_poly(img, [(4, 62), (21, 4), (43, 4), (60, 62)], c)
        fill_poly(img, [(29, 58), (30, 48), (34, 48), (35, 58)], WHITE)
        fill_poly(img, [(30, 40), (31, 32), (33, 32), (34, 40)], WHITE)
        fill_poly(img, [(31, 25), (31, 18), (33, 18), (33, 25)], WHITE)
        fill_poly(img, [(32, 12), (32, 7), (33, 7), (33, 12)], WHITE)
    elif name == "garage":
        fill_poly(img, [(6, 29), (29, 8), (35, 8), (58, 29), (52, 29), (32, 14), (12, 29)], c)
        fill_poly(img, [(13, 27), (51, 27), (51, 58), (13, 58)], c)
        rect(img, 21, 35, 43, 38, WHITE)
        rect(img, 21, 43, 43, 46, WHITE)
        rect(img, 21, 51, 43, 54, WHITE)
    elif name == "speaker":
        rect(img, 7, 25, 20, 39, c)
        fill_poly(img, [(17, 25), (36, 12), (36, 52), (17, 39)], c)
        fill_poly(img, [(42, 23), (47, 26), (50, 32), (47, 38), (42, 41), (44, 35), (46, 32), (44, 29)], c)
        fill_poly(img, [(51, 14), (57, 19), (61, 27), (62, 32), (61, 38), (57, 46), (51, 50), (53, 43), (57, 37), (58, 32), (57, 27), (53, 21)], c)
    elif name == "exit":
        outline_box(img, 31, 7, 56, 57, c, 4)
        rect(img, 24, 27, 36, 37, WHITE)
        pixel_line(img, [(7, 32), (33, 32)], c, 5)
        pixel_line(img, [(21, 20), (8, 32), (21, 44)], c, 5)
    elif name == "retry":
        pixel_line(img, [(48, 24), (44, 16), (36, 11), (26, 10), (17, 14), (11, 22), (9, 32)], c, 5)
        pixel_line(img, [(48, 12), (48, 25), (35, 25)], c, 5)
        pixel_line(img, [(16, 40), (20, 48), (28, 53), (38, 53), (47, 49), (53, 41), (55, 32)], c, 5)
        pixel_line(img, [(16, 52), (16, 39), (29, 39)], c, 5)
    elif name == "home":
        pixel_line(img, [(7, 30), (32, 9), (57, 30)], c, 5)
        outline_box(img, 14, 28, 50, 57, c, 4)
        rect(img, 27, 40, 37, 57, c)
    elif name == "trophy":
        rect(img, 21, 10, 43, 34, c)
        pixel_line(img, [(21, 15), (12, 15), (12, 24), (18, 29)], c, 4)
        pixel_line(img, [(43, 15), (52, 15), (52, 24), (46, 29)], c, 4)
        rect(img, 29, 34, 35, 46, c)
        rect(img, 21, 46, 43, 52, c)
        rect(img, 17, 53, 47, 58, c)
    elif name == "pin":
        circle_blocks(img, 32, 24, 19, c, 4)
        circle_blocks(img, 32, 24, 9, c, 4, WHITE)
        pixel_line(img, [(17, 36), (32, 59), (47, 36)], c, 5)
    elif name == "wheel":
        circle_blocks(img, 32, 32, 25, c, 4)
        circle_blocks(img, 32, 32, 9, c, 4, WHITE)
        pixel_line(img, [(32, 24), (32, 8)], c, 4)
        pixel_line(img, [(25, 35), (13, 46)], c, 4)
        pixel_line(img, [(39, 35), (51, 46)], c, 4)
    elif name == "car":
        pixel_line(img, [(7, 40), (12, 29), (20, 26), (26, 17), (41, 17), (49, 28), (55, 31), (58, 40)], c, 5)
        rect(img, 7, 37, 58, 49, c)
        rect(img, 24, 22, 41, 27, WHITE)
        rect(img, 10, 46, 22, 56, c)
        rect(img, 43, 46, 55, 56, c)
        rect(img, 13, 48, 20, 54, WHITE)
        rect(img, 46, 48, 53, 54, WHITE)
    else:
        raise ValueError(f"未知图标：{name}")
    return img


def save(img, name):
    path = DEST / name
    if not img.write(Filename.fromOsSpecific(str(path))):
        raise OSError(f"无法生成资源：{path}")


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for state in ("normal", "hover", "pressed", "disabled"):
        save(button(512, 112, "secondary", state), f"button-{state}.png")
    for state in ("normal", "hover", "pressed"):
        save(button(512, 112, "primary", state), f"primary-{state}.png")
    save(button(320, 80, "secondary", "normal"), "button-small-normal.png")
    save(framed_panel(768, 768), "panel.png")
    save(framed_panel(512, 176, dark=True), "speed-panel.png")
    for name in ("stopwatch", "palm", "highway", "garage", "speaker", "exit",
                 "retry", "home", "trophy", "pin", "wheel", "car"):
        save(draw_icon(name), f"icon-{name}.png")


if __name__ == "__main__":
    main()
