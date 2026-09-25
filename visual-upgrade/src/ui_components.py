"""像素界面组件：按参考像素布局的九宫格面板、按钮、图标与页面根。

所有节点挂在 aspect2d 下，布局单位是 1080p 参考像素（原点在屏幕左上角，
y 向下增长）。Canvas 负责换算到 DirectGUI 坐标，因此同一套常量在
720p 与 1080p 下都落在稳定的整数像素宽度上。

九宫格用 OnscreenImage 拼接：角块保持像素尺寸，边与中心按目标框缩放；
图元不参与深度测试，避免被地形与天空遮挡。
"""

from typing import ClassVar

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import Filename, SamplerState, TextNode

import ui_theme as theme


def load_ui_font(loader):
    """优先用 Ark Pixel；未安装时回退到仓库原有的 Fusion Pixel。"""
    path = theme.FONT_FILE if theme.FONT_FILE.exists() else theme.FALLBACK_FONT_FILE
    font = loader.loadFont(Filename.fromOsSpecific(str(path)).getFullpath())
    font.setPixelsPerUnit(theme.FONT_UNITS_PER_EM)
    font.setMinfilter(SamplerState.FTNearest)
    font.setMagfilter(SamplerState.FTNearest)
    return font


def pixel_text(parent, canvas, value, x, y, size, *, color=theme.INK,
               align=TextNode.ALeft):
    """统一的像素文字：同色偏移描边加粗，贴近设计图的笔画厚度。

    (x, y) 用全局参考像素；align 决定该点落在左端还是中心。
    """
    node = OnscreenText(
        parent=parent, text=value, font=canvas.font, fg=color,
        scale=canvas.uy(size), pos=(canvas.x(x), canvas.y(y)), align=align,
    )
    offset = canvas.uy(theme.TEXT_BOLD_OFFSET)
    text = node.node()
    text.setShadow(offset, offset)
    text.setShadowColor(color[0], color[1], color[2], 1)
    return node


class Canvas:
    """把参考像素映射到当前窗口；窗口尺寸变化时重算比例并重新布局。"""

    def __init__(self, base):
        self.base = base
        self.scale = 1.0
        self.aspect_scale = 1.0
        self.font = load_ui_font(base.loader)
        self.update()

    def update(self):
        height = self.base.win.getYSize() or theme.REFERENCE_HEIGHT
        self.scale = theme.REFERENCE_HEIGHT / height
        self.aspect_scale = self.base.getAspectRatio() / (16 / 9)

    def x(self, px):
        """参考像素横坐标 -> aspect2d 横坐标。"""
        return (px - 960) / theme.HALF_HEIGHT

    def y(self, px):
        """参考像素纵坐标（向下）-> aspect2d 纵坐标。"""
        return (540 - px) / theme.HALF_HEIGHT

    def ux(self, px):
        return px / theme.HALF_HEIGHT

    def uy(self, px):
        return px / theme.HALF_HEIGHT

    def width(self):
        """当前窗口在参考像素下的宽度，用于左右锚定与安全区。"""
        return 1920 * self.aspect_scale


class OriginCanvas:
    """局部像素坐标 -> aspect2d：节点锚在屏幕原点，与全局坐标同一空间。"""

    def __init__(self, canvas):
        self.canvas = canvas

    def x(self, px):
        return self.canvas.x(px)

    def y(self, px):
        return self.canvas.y(px)

    def ux(self, px):
        return self.canvas.ux(px)

    def uy(self, px):
        return self.canvas.uy(px)


class UiSkin:
    """按需加载并缓存界面贴图，并按参考像素拼接九宫格。"""

    def __init__(self, loader):
        self.loader = loader
        self._textures = {}

    def texture(self, name):
        if name not in self._textures:
            file_name = name if name.endswith(".png") else f"{name}.png"
            path = Filename.fromOsSpecific(str(theme.UI_ASSETS / file_name)).getFullpath()
            texture = self.loader.loadTexture(path)
            texture.setMinfilter(SamplerState.FT_nearest)
            texture.setMagfilter(SamplerState.FT_nearest)
            self._textures[name] = texture
        return self._textures[name]

    def image(self, name, parent, canvas, center_x, center_y, width, height):
        """按参考像素的中心与尺寸放一张贴图（OnscreenImage 以中心为锚点）。"""
        node = OnscreenImage(
            image=self.texture(name),
            parent=parent,
            pos=(canvas.x(center_x), 0, canvas.y(center_y)),
            # OnscreenImage 的几何是 -1..1，setScale 给的是半宽半高，必须减半
            scale=(canvas.ux(width) / 2, 1, canvas.uy(height) / 2),
        )
        node.setTransparency(True)
        node.setDepthTest(False)
        node.setDepthWrite(False)
        return node

    def picture(self, name, parent, canvas, x, y, width, height):
        """按参考像素的左上角与尺寸放一张贴图。"""
        return self.image(name, parent, canvas, x + width / 2, y + height / 2, width, height)

    def nine(self, style, parent, canvas, x, y, width, height):
        """九宫格：角块固定，边与中心拉伸。"""
        corner = theme.CORNER
        columns = (corner, max(1, width - 2 * corner), corner)
        rows = (corner, max(1, height - 2 * corner), corner)
        lefts = (x, x + columns[0], x + columns[0] + columns[1])
        tops = (y, y + rows[0], y + rows[0] + rows[1])
        nodes = {}
        for row, piece_row in enumerate((("topleft", "top", "topright"),
                                         ("left", "center", "right"),
                                         ("bottomleft", "bottom", "bottomright"))):
            for column, piece in enumerate(piece_row):
                nodes[piece] = self.picture(f"{style}-{piece}", parent, canvas,
                                            lefts[column], tops[row],
                                            columns[column], rows[row])
        return nodes

    def set_nine(self, nodes, style):
        for piece, node in nodes.items():
            node.setTexture(self.texture(f"{style}-{piece}"))


class PixelButton:
    """整块像素贴图做三态底图的按钮（ready / pressed / rollover / disabled）。

    这里用**组合**而不是继承 DirectButton：这一版 Panda3D 里子类化 DirectGui 控件
    会丢掉 PGItem 的 frame（`has_frame()` 为假）。PGUI 的鼠标拾取依赖 frame，
    没有 frame 时点哪都不会触发，而且不报任何错。
    """

    STYLES: ClassVar[dict[str, tuple[str, str, str]]] = {
        "normal": ("", "-hover", "-pressed"),
        "primary": ("-primary", "-primary-hover", "-pressed"),
    }

    def __init__(self, parent, canvas, skin, rect, label, command, *, primary=False,
                 font_scale=None, align=TextNode.ALeft, size="wide", inset=None):
        x, y, width, height = rect
        self.canvas = canvas
        self.skin = skin
        self.rect = rect
        self.size = size
        text_size = font_scale or theme.FONT_BODY
        normal, hover, pressed = self.STYLES["primary" if primary else "normal"]
        art = [skin.texture(f"btn-{size}{style}") for style in (normal, hover, pressed)]
        left = inset if inset is not None else self._text_inset(align, width)
        self.button = DirectButton(
            parent=parent,
            text=label,
            text_font=canvas.font,
            text_fg=theme.WHITE if primary else theme.INK,
            text_align=align,
            text_scale=canvas.uy(text_size),
            text_pos=(canvas.ux(left), canvas.uy(height) - canvas.uy(text_size * 0.66)),
            frameSize=(0, canvas.ux(width), 0, canvas.uy(height)),
            frameColor=(1, 1, 1, 1),
            relief=DGG.FLAT,
            # 状态顺序固定为 ready, pressed, rollover, disabled
            frameTexture=(art[0], art[2], art[1], art[0]),
            command=command,
        )
        self.button.setPos(canvas.x(x), 0, canvas.y(y + height))

    @property
    def guiId(self):
        return self.button.guiId

    def node(self):
        return self.button.node()

    @staticmethod
    def _text_inset(align, width):
        if align == TextNode.ACenter:
            return width / 2
        if align == TextNode.ARight:
            return width - 18
        return 18

    def set_style(self, style):
        self.button["frameTexture"] = self.skin.texture(f"btn-{self.size}{style}")

    def set_text(self, value):
        self.button["text"] = value

    def get_text(self):
        return self.button["text"]

    def destroy(self):
        self.button.destroy()


class PageRoot:
    """页面根节点：锚在屏幕原点，子元素统一使用全局参考像素坐标。

    九宫格底图按 rect 直接拼在页面节点下（局部原点即屏幕原点），因此按钮、
    文字等子节点可以用 canvas.x/y 的全局像素定位，不会叠加页面偏移。
    """

    def __init__(self, parent, canvas, skin, rect, style="panel"):
        self.canvas = canvas
        self.skin = skin
        self.style = style
        self.rect = rect
        self.node = DirectFrame(parent=parent, frameColor=(0, 0, 0, 0), frameSize=(0, 0, 0, 0))
        self.pieces = skin.nine(style, self.node, OriginCanvas(canvas),
                                rect[0], rect[1], rect[2], rect[3])
        self.children = []

    def add(self, node):
        self.children.append(node)
        return node

    def show(self):
        self.node.show()

    def hide(self):
        self.node.hide()

    def destroy(self):
        for child in self.children:
            child.destroy()
        self.children.clear()
        for piece in self.pieces.values():
            piece.destroy()
        self.node.destroy()


class OptionButton(PixelButton):
    """整行可点选项：底图 + 图标 + 标签 + 右端箭头，对应设计图的列表项。

    图标与文字的左缩进按行高推导，同一套代码适配主入口与大按钮。
    """

    def __init__(self, parent, canvas, skin, rect, label, command, *, primary=False,
                 icon=None, size="menu", font_scale=None):
        icon_size = min(46.0, rect[3] - 22)
        super().__init__(parent, canvas, skin, rect, label, command, primary=primary,
                         font_scale=font_scale, size=size,
                         inset=22 + icon_size + 22 if icon else 26)
        x, y, width, height = rect
        center = y + height / 2
        self.icon = None
        if icon:
            self.icon = skin.picture(f"icon-{icon}", parent, canvas,
                                     x + 22, center - icon_size / 2, icon_size, icon_size)
        arrow = min(24.0, height - 30)
        self.arrow = skin.picture("icon-arrow", parent, canvas,
                                  x + width - 30 - arrow, center - arrow / 2, arrow, arrow)

    def destroy(self):
        for node in (self.icon, self.arrow):
            if node is not None:
                node.removeNode()
        super().destroy()


class ValueRow:
    """只读数值行：图标 + 名称 + 数值，对应设计图结算页的统计行。"""

    def __init__(self, parent, canvas, skin, rect, icon, name, value):
        x, y, width, height = rect
        self.pieces = skin.nine("well", parent, OriginCanvas(canvas), x, y, width, height)
        center = y + height / 2
        self.icon = None
        if icon:
            self.icon = skin.picture(f"icon-{icon}", parent, canvas,
                                     x + 18, center - 16, 32, 32)
        self.name = pixel_text(parent, canvas, name, x + 64, center + 8,
                               theme.FONT_BODY, align=TextNode.ALeft)
        self.value = pixel_text(parent, canvas, value, x + width - 22, center + 8,
                                theme.FONT_BODY, align=TextNode.ARight)

    def set_value(self, value):
        self.value.setText(value)

    def destroy(self):
        if self.icon is not None:
            self.icon.removeNode()
        self.name.destroy()
        self.value.destroy()
        for piece in self.pieces.values():
            piece.destroy()
