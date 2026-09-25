"""生成海岸主题的像素界面素材：九宫格面板、按钮状态与功能图标。

素材在构建期用 PNMImage 直接画像素，运行期只读 PNG 并保持最近邻过滤。
颜色与 graphic_design 设计图一致：奶白纸面、深海蓝描边、橙色主操作。
"""

from pathlib import Path

from panda3d.core import Filename, PNMImage

DEST = Path(__file__).resolve().parents[1] / "assets/game/ui"

# 设计图取色
INK = (0.063, 0.169, 0.227)
INK_SOFT = (0.13, 0.27, 0.35)
PAPER = (0.953, 0.937, 0.890)
PAPER_LIGHT = (0.996, 0.988, 0.960)
PAPER_DARK = (0.855, 0.845, 0.800)
PAPER_SHADE = (0.784, 0.780, 0.741)
ORANGE = (0.957, 0.486, 0.141)
ORANGE_LIGHT = (1.0, 0.65, 0.29)
ORANGE_DARK = (0.788, 0.365, 0.078)
GOLD = (1.0, 0.761, 0.278)
RED = (0.804, 0.239, 0.176)
GREEN = (0.278, 0.616, 0.353)

# 九宫格切片尺寸：12 像素角块，运行期按目标尺寸拼接
CORNER = 12


def new_image(width, height):
    image = PNMImage(width, height, 4)
    image.fill(0, 0, 0)
    image.alphaFill(0)
    return image


def put(image, x, y, color, alpha=1):
    image.setXel(x, y, *color)
    image.setAlpha(x, y, alpha)


def rect(image, left, top, right, bottom, color, alpha=1):
    for y in range(top, bottom):
        for x in range(left, right):
            put(image, x, y, color, alpha)


def rounded(image, left, top, right, bottom, radius, color):
    """圆角矩形；半径内按像素中心判定，保持硬边像素风格。"""
    for y in range(top, bottom):
        for x in range(left, right):
            dx = 0.0
            dy = 0.0
            if x < left + radius:
                dx = left + radius - x - 0.5
            elif x >= right - radius:
                dx = x - (right - radius) + 0.5
            if y < top + radius:
                dy = top + radius - y - 0.5
            elif y >= bottom - radius:
                dy = y - (bottom - radius) + 0.5
            if dx * dx + dy * dy <= radius * radius + 0.25:
                put(image, x, y, color)


def slice_image(width, height, fill, outline, radius=4, shade=None):
    """九宫格底图：外描边 + 底部投影 + 内部填充 + 顶部受光 + 底部内阴影。"""
    image = new_image(width, height)
    rounded(image, 0, 0, width, height, radius, outline)
    rounded(image, 1, 1, width - 1, height - 1, max(1, radius - 1), fill)
    if shade is not None:
        rounded(image, 2, height - 4, width - 2, height - 1, 2, shade)
    rect(image, 3, 2, width - 3, 3, PAPER_LIGHT, 0.6)
    return image


def write(image, name):
    """写盘前确保带 alpha 通道。

    Panda 的 PNG 写出器在 alpha 全部不透明时会丢掉 alpha 通道，贴图变成 RGB；
    而开启透明混合的节点遇到没有 alpha 的贴图会把整片判为透明。角落留一点
    极低透明差异即可保住通道，视觉上不可见。
    """
    if not image.hasAlpha():
        rgba = new_image(image.getXSize(), image.getYSize())
        rgba.copySubImage(image, 0, 0, 0, 0, image.getXSize(), image.getYSize())
        image = rgba
        image.alphaFill(1)
    if image.getAlpha(0, image.getYSize() - 1) >= 1.0:
        image.setAlpha(0, image.getYSize() - 1, 0.996)
    DEST.mkdir(parents=True, exist_ok=True)
    image.write(Filename.fromOsSpecific(str(DEST / name)))


def nine_slice(name, width, height, fill, outline, radius=4, shade=None):
    """把一张完整贴图拆成中心与八条边，运行期按目标尺寸拼接。"""
    full = slice_image(width, height, fill, outline, radius, shade)
    pieces = {
        "center": (CORNER, CORNER, width - CORNER, height - CORNER),
        "top": (CORNER, 0, width - CORNER, CORNER),
        "bottom": (CORNER, height - CORNER, width - CORNER, height),
        "left": (0, CORNER, CORNER, height - CORNER),
        "right": (width - CORNER, CORNER, width, height - CORNER),
        "topleft": (0, 0, CORNER, CORNER),
        "topright": (width - CORNER, 0, width, CORNER),
        "bottomleft": (0, height - CORNER, CORNER, height),
        "bottomright": (width - CORNER, height - CORNER, width, height),
    }
    for piece, (left, top, right, bottom) in pieces.items():
        cut = new_image(right - left, bottom - top)
        cut.copySubImage(full, 0, 0, left, top, right - left, bottom - top)
        write(cut, f"{name}-{piece}.png")


def clear(image, left, top, right, bottom):
    """把区域擦成透明，用来在图形上开口（例如重启箭头的缺口）。"""
    for y in range(top, bottom):
        for x in range(left, right):
            image.setAlpha(x, y, 0)


def filled_circle(image, size, color, radius=None, cx=None, cy=None):
    if radius is None:
        radius = size // 2 - 2
    if cx is None:
        cx = (size - 1) / 2
    if cy is None:
        cy = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius + radius * 0.4:
                put(image, x, y, color)


def icon_clock(image, size, color):
    """秒表：外圈 + 顶部按钮 + 指针，对应设计图计时挑战的图标。"""
    filled_circle(image, size, color, radius=12)
    filled_circle(image, size, PAPER, radius=9)
    rect(image, 14, 27, 18, 30, color)
    rect(image, 15, 29, 17, 31, color)
    rect(image, 15, 14, 17, 22, color)
    rect(image, 16, 15, 22, 17, color)
    rect(image, 27, 8, 29, 11, color)


def icon_palm(image, size, color, accent):
    """棕榈：弯曲树干 + 上方散开的叶冠。"""
    rect(image, 14, 10, 18, 26, color)
    rect(image, 16, 14, 19, 27, color)
    for step in range(7):
        rect(image, 3 + step, 24 - step, 6 + step, 27 - step, accent)
        rect(image, 24 - step, 24 - step, 27 - step, 27 - step, accent)
    rect(image, 8, 18, 12, 21, accent)
    rect(image, 19, 18, 23, 21, accent)
    rect(image, 12, 14, 21, 17, accent)
    rect(image, 13, 10, 19, 13, accent)


def icon_road(image, size, color):
    """透视道路：收敛的两侧边线 + 中央虚线，对应无限高速。"""
    for step in range(22):
        y = 5 + step
        half = 3 + int(step * 5 / 21)
        rect(image, 16 - half, y, 16 - half + 2, y + 1, color)
        rect(image, 15 + half, y, 17 + half, y + 1, color)
    for y in (8, 16, 24):
        rect(image, 15, y, 17, y + 3, color)


def icon_home(image, size, color):
    """房屋：屋顶 + 墙体 + 门。"""
    for i in range(10):
        rect(image, 16 - i, 19 - i, 17 + i, 20 - i, color)
    rect(image, 5, 6, 9, 19, color)
    rect(image, 23, 6, 27, 19, color)
    rect(image, 5, 6, 27, 9, color)
    rect(image, 14, 6, 18, 14, color)


def icon_volume(image, size, color):
    """扬声器 + 两道声波。"""
    rect(image, 3, 13, 8, 19, color)
    for i in range(7):
        rect(image, 8 + i, 13 - i, 9 + i, 19 + i, color)
    for radius, half in ((18, 6), (22, 9)):
        for y in range(4, 28):
            for x in range(4, 30):
                distance = ((x - 10) ** 2 + (y - 15.5) ** 2) ** 0.5
                if radius - 1 <= distance <= radius + 1 and abs(y - 15.5) <= half:
                    put(image, x, y, color)


def icon_car(image, size, color):
    rect(image, 4, size - 14, size - 4, size - 10, color)
    rect(image, 6, size - 18, size - 6, size - 14, color)
    rect(image, 2, size - 10, size - 2, size - 7, color)
    rect(image, 1, size - 12, 4, size - 7, color)
    rect(image, size - 4, size - 12, size - 1, size - 7, color)


def icon_circle(image, size, color, thickness=2):
    cx = cy = size / 2 - 0.5
    radius = size / 2 - 3
    for y in range(size):
        for x in range(size):
            distance = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if radius - thickness + 0.5 <= distance <= radius:
                put(image, x, y, color)


def icon_checkpoint(image, size, color, accent):
    filled_circle(image, size, color, radius=10)
    filled_circle(image, size, (1, 1, 1), radius=6)
    filled_circle(image, size, accent, radius=3.5)


def icon_bridge(image, size, color):
    rect(image, 2, 15, size - 2, 19, color)
    rect(image, 6, 12, 9, 27, color)
    rect(image, size - 9, 12, size - 6, 27, color)
    for x in (10, 13, 19, 22):
        rect(image, x, 15, x + 1, 20, color)
    rect(image, 2, 3, size - 2, 6, color)


def icon_flag(image, size, color, accent):
    rect(image, size // 2 - 1, 3, size // 2 + 1, size - 3, color)
    for i in range(9):
        rect(image, size // 2 + 1, 3 + i, size // 2 + 10 - i, 4 + i, accent)
    rect(image, size // 2 - 7, 3, size // 2 + 2, 5, color)


def icon_trophy(image, size, color, accent):
    rect(image, 6, 5, size - 6, 20, color)
    rect(image, 8, 3, size - 8, 5, accent)
    rect(image, 2, 7, 6, 16, color)
    rect(image, size - 6, 7, size - 2, 16, color)
    rect(image, size // 2 - 2, 20, size // 2 + 2, 26, color)
    rect(image, 7, 26, size - 7, 29, color)


def icon_wheel(image, size, color):
    icon_circle(image, size, color, thickness=4)
    for lx, ly in ((7, 21), (21, 21), (7, 7), (21, 7)):
        rect(image, lx, ly, lx + 4, ly + 4, color)
    rect(image, 14, 14, 18, 18, color)


def icon_restart(image, size, color):
    icon_circle(image, size, color, thickness=3)
    clear(image, size // 2 - 5, size // 2 + 2, size // 2 + 6, size)
    rect(image, size // 2 - 2, size // 2 - 2, size // 2 + 5, size // 2 + 4, color)
    rect(image, size // 2 + 2, size // 2 - 8, size // 2 + 6, size // 2 + 4, color)
    filled_circle(image, size, color, radius=3, cx=size // 2 + 1, cy=size // 2 - 1)


def icon_bar(image, size, color):
    rect(image, size // 2 - 8, size // 2 - 6, size // 2 - 5, size // 2 + 6, color)
    rect(image, size // 2 - 3, size // 2 - 6, size // 2, size // 2 + 6, color)
    rect(image, size // 2 + 2, size // 2 - 6, size // 2 + 5, size // 2 + 6, color)


def icon_exit(image, size, color):
    rect(image, 3, 4, 6, size - 4, color)
    rect(image, 6, 4, 16, 7, color)
    rect(image, 6, size - 7, 16, size - 4, color)
    rect(image, 11, size // 2 - 2, size - 9, size // 2 + 2, color)
    for i in range(8):
        rect(image, size - 10 + i, size // 2 - 2 - i, size - 9 + i, size // 2 + 2 - i, color)


def icon_note(image, size, color):
    """音符：效果音量。"""
    rect(image, 18, 5, 20, 27, color)
    rect(image, 20, 24, 26, 27, color)
    filled_circle(image, size, color, radius=4, cx=13, cy=7)
    filled_circle(image, size, color, radius=3.5, cx=22, cy=10)


def icon_arrow(image, size, color):
    """列表项右端的 `>` 指示。"""
    for y in range(8, 25):
        offset = abs(16 - y)
        inside = 16 - offset
        if 10 <= inside <= 20:
            for thickness in range(3):
                rect(image, inside + thickness - 2, y, inside + thickness, y + 1, color)


def icon_check(image, size, color):
    for i in range(size - 10):
        x = 5 + i
        if i < 6:
            put(image, x, size // 2 - 2 + i, color)
            put(image, x, size // 2 - 1 + i, color)
        else:
            put(image, x, size // 2 + 4 - (i - 6), color)
            put(image, x, size // 2 + 5 - (i - 6), color)


def icon_warning(image, size, color, accent):
    for i in range(11):
        rect(image, size // 2 - i, 4 + i, size // 2 + i + 1, 5 + i, color)
    rect(image, 3, 14, size - 3, 27, color)
    for i in range(11):
        rect(image, size // 2 - i + 2, 6 + i, size // 2 + i - 1, 7 + i, ORANGE)
    rect(image, 3, 22, size - 3, 25, (1, 1, 1))
    rect(image, size // 2 - 2, 9, size // 2 + 2, 20, ORANGE)
    rect(image, size // 2 - 2, 22, size // 2 + 2, 25, ORANGE)


def icon_collision(image, size, color, accent):
    icon_car(image, size, color)
    for i in range(6):
        rect(image, size - 9 + i, size - 18 + i, size - 7 + i, size - 16 + i, accent)
        rect(image, 1 + i, size - 18 + i, 3 + i, size - 16 + i, accent)


ICONS = {
    "clock": lambda image, size: icon_clock(image, size, INK),
    "car": lambda image, size: icon_car(image, size, INK),
    "road": lambda image, size: icon_road(image, size, INK),
    "bridge": lambda image, size: icon_bridge(image, size, INK),
    "wheel": lambda image, size: icon_wheel(image, size, INK),
    "restart": lambda image, size: icon_restart(image, size, INK),
    "home": lambda image, size: icon_home(image, size, INK),
    "volume": lambda image, size: icon_volume(image, size, INK),
    "exit": lambda image, size: icon_bar(image, size, INK),
    "check": lambda image, size: icon_check(image, size, GREEN),
    "menu": lambda image, size: icon_bar(image, size, INK),
    "warning": lambda image, size: icon_warning(image, size, INK, ORANGE),
    "collision": lambda image, size: icon_collision(image, size, INK, RED),
    "checkpoint": lambda image, size: icon_checkpoint(image, size, INK, ORANGE),
    "flag": lambda image, size: icon_flag(image, size, INK, ORANGE),
    "trophy": lambda image, size: icon_trophy(image, size, ORANGE, GOLD),
    "palm": lambda image, size: icon_palm(image, size, INK, GREEN),
    "arrow": lambda image, size: icon_arrow(image, size, INK),
    "note": lambda image, size: icon_note(image, size, INK),
}

ICON_SIZE = 32

# 按钮整块贴图的尺寸（宽 x 高，参考像素）；直接贴到 DirectFrame 上，
# 避免九宫格子节点在不同父节点下的定位差异。
BUTTON_SIZES = {
    "wide": (420, 62),
    "main": (632, 78),
    "sub": (560, 62),
    "menu": (328, 62),
    "mid": (280, 52),
    "small": (200, 52),
    "word": (588, 56),
}

BUTTON_STYLES = {
    "": (PAPER_LIGHT, INK, PAPER_SHADE),
    "-hover": ((1.0, 0.91, 0.76), INK, ORANGE),
    "-pressed": (PAPER_DARK, INK, PAPER_SHADE),
    "-primary": (ORANGE, ORANGE_DARK, ORANGE_DARK),
    "-primary-hover": (ORANGE_LIGHT, ORANGE_DARK, ORANGE_DARK),
    "-selected": ((1.0, 0.93, 0.80), ORANGE, ORANGE),
}


def put_button(image, width, height, style):
    """按样式画一块完整按钮贴图：描边 + 填充 + 顶部受光 + 底部投影。"""
    fill, outline, shade = BUTTON_STYLES[style]
    rounded(image, 0, 0, width, height, 4, outline)
    rounded(image, 1, 1, width - 1, height - 1, 3, fill)
    rounded(image, 2, height - 6, width - 2, height - 3, 2, shade)
    rect(image, 3, 2, width - 3, 3, (1.0, 0.99, 0.97))


def whole(name, width, height, fill=PAPER):
    """整张底板或按钮：给仍按整图铺贴的旧界面使用。"""
    image = new_image(width, height)
    rounded(image, 0, 0, width, height, 6, INK)
    rounded(image, 2, 2, width - 2, height - 2, 5, fill)
    rounded(image, 4, height - 10, width - 4, height - 5, 3, PAPER_SHADE)
    rect(image, 6, 4, width - 6, 6, PAPER_LIGHT)
    write(image, name)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    nine_slice("panel", 64, 64, PAPER, INK, radius=5, shade=PAPER_SHADE)
    nine_slice("panel-solid", 64, 64, PAPER_LIGHT, INK, radius=5, shade=PAPER_SHADE)
    nine_slice("well", 48, 48, PAPER_DARK, INK_SOFT, radius=4)
    nine_slice("pill", 40, 28, PAPER_LIGHT, INK, radius=10)
    nine_slice("chip", 40, 28, PAPER_DARK, INK_SOFT, radius=3)
    # 旧 setup_hud 仍按整张贴图读取这些底板与按钮；像素版本接管全部页面后再移除
    whole("panel.png", 256, 320)
    whole("panel-wide.png", 384, 256)
    whole("button.png", 240, 40, PAPER_LIGHT)
    whole("button-hover.png", 240, 40, (1.0, 0.91, 0.76))
    whole("button-pressed.png", 240, 40, PAPER_DARK)
    whole("button-primary.png", 240, 40, ORANGE)
    for name, painter in ICONS.items():
        image = new_image(ICON_SIZE, ICON_SIZE)
        painter(image, ICON_SIZE)
        write(image, f"icon-{name}.png")
    for size_name, (width, height) in BUTTON_SIZES.items():
        for style in BUTTON_STYLES:
            image = new_image(width, height)
            put_button(image, width, height, style)
            write(image, f"btn-{size_name}{style}.png")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
