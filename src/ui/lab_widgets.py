"""界面几何与控件原语：黑曜石圆角细描边卡片、单选圆环指示器、摄影渐隐遮罩与琥珀金按钮材质。"""

import math
from functools import lru_cache

from direct.gui.DirectOptionMenu import DirectOptionMenu
from direct.showbase import ShowBaseGlobal
from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    PNMImage,
    SamplerState,
    Texture,
    TransparencyAttrib,
)

from ui import theme

# 专家试验台明净浅瓷工程令牌（高对比浅底图表/数据可读性，与暗色工坊隔离不互相污染）。
MUTED = (0.345, 0.388, 0.458, 1)
BORDER = (0.815, 0.840, 0.878, 1)
LAB_BG = (0.942, 0.948, 0.958, 1)
LAB_HEADER = (0.988, 0.990, 0.995, 1)
LAB_CARD = (0.996, 0.997, 0.999, 1)
LAB_SURFACE = (0.948, 0.956, 0.968, 1)
LAB_FIELD = (0.938, 0.948, 0.964, 1)
LAB_FIELD_FOCUS = (0.855, 0.922, 0.975, 1)
LAB_FIELD_DISABLED = (0.920, 0.928, 0.940, 1)
LAB_TEXT = (0.082, 0.105, 0.145, 1)
LAB_DISABLED_TEXT = (0.580, 0.615, 0.670, 1)
LAB_GRID = (0.875, 0.895, 0.925, 1)
LAB_TRACK = (0.820, 0.850, 0.890, 1)
LAB_ACCENT_A = (0.090, 0.420, 0.640, 1)
LAB_TINT_A = (0.895, 0.945, 0.985, 1)
LAB_LINE_A = (0.640, 0.790, 0.905, 1)
LAB_ACCENT_B = (0.845, 0.335, 0.085, 1)
LAB_TINT_B = (0.992, 0.935, 0.895, 1)
LAB_LINE_B = (0.920, 0.735, 0.620, 1)
LAB_SUCCESS = (0.060, 0.490, 0.320, 1)
LAB_ERROR = (0.760, 0.160, 0.140, 1)


class LabOptionMenu(DirectOptionMenu):
    """定高平面列表；锁定控件外框尺寸不随箭头扩张，悬停不改变文字或鼠标命中区域。"""

    def __init__(self, parent=None, *, before_popup=None, **options):
        self.before_popup = before_popup
        self._fixed_frame_size = options.get("frameSize")
        super().__init__(parent, **options)
        self.initialiseoptions(LabOptionMenu)
        self._apply_fixed_frame()

    def _apply_fixed_frame(self):
        if self._fixed_frame_size is not None:
            self["frameSize"] = self._fixed_frame_size

    def set(self, index, fCommand=1):
        super().set(index, fCommand=fCommand)
        self._apply_fixed_frame()

    def _highlightItem(self, item, index):
        item["frameColor"] = self["highlightColor"]
        self.highlightedIndex = index

    def _unhighlightItem(self, item, frameColor):
        item["frameColor"] = frameColor
        self.highlightedIndex = None

    def showPopupMenu(self, event=None):
        if self.before_popup is not None:
            self.before_popup()
        bounds = self._fixed_frame_size or self["frameSize"]
        width = bounds[1] - bounds[0]
        height = self.maxHeight * len(self["items"])
        self.popupMenu["frameSize"] = (-.003, width + .003, -height - .003, .003)
        super().showPopupMenu(event)
        popup = self.popupMenu
        popup.setPos(self, bounds[0], 0, bounds[2] - .006)
        screen = ShowBaseGlobal.render2d
        pos, scale = popup.getPos(screen), popup.getScale(screen)
        # 底部控件向上展开，其余列表与控件左边缘对齐向下展开。
        if pos.z - height * scale.z < -.99:
            popup.setZ(self, bounds[3] + .006 + height)
        pos = popup.getPos(screen)
        popup.setX(screen, max(-.99, min(pos.x, .99 - width * scale.x)))
        popup.setZ(screen, max(-.99 + height * scale.z, min(pos.z, .99)))


def rounded_panel(parent, name, box, color, radius=.025):
    left, right, bottom, top = box
    radius = min(radius, (right-left)/2, (top-bottom)/2)
    points = [((left+right)/2, 0, (bottom+top)/2)]
    for cx, cz, angle in ((right-radius, top-radius, 0), (left+radius, top-radius, 90),
                          (left+radius, bottom+radius, 180), (right-radius, bottom+radius, 270)):
        for step in range(9):
            phase = math.radians(angle+step*90/8)
            points.append((cx+radius*math.cos(phase), 0, cz+radius*math.sin(phase)))
    data = GeomVertexData(name, GeomVertexFormat.getV3(), Geom.UHStatic)
    writer = GeomVertexWriter(data, "vertex")
    for point in points:
        writer.addData3f(*point)
    triangles = GeomTriangles(Geom.UHStatic)
    for index in range(1, len(points)):
        triangles.addVertices(0, index, 1 if index == len(points)-1 else index+1)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    result = parent.attachNewNode(node)
    result.setColor(*color)
    result.setDepthTest(False)
    result.setDepthWrite(False)
    return result


def skewed_panel(parent, name, box, color, skew=.010):
    """克制圆角微倾标签条（保留函数名兼容全站，改为参考图同款克制圆角精密徽标）。"""
    left, right, bottom, top = box
    radius = min((right - left) * 0.25, (top - bottom) * 0.25, max(0.004, abs(skew) * 0.45))
    node = rounded_panel(parent, name, box, color, radius)
    node.setTransparency(TransparencyAttrib.MAlpha)
    return node


def radio_dot(parent, name, cx, cz, radius, *, selected=False, installed=False):
    """参考图同款右侧精密单选圆环：未选空心细环、已装白点、当前选中琥珀金发光圆环。"""
    group = parent.attachNewNode(name)
    group.setTransparency(TransparencyAttrib.MAlpha)
    ring_col = theme.AMBER if selected else theme.DARK_SUB if installed else (0.36, 0.41, 0.50, 0.85)
    rounded_panel(group, name + "-outer",
                  (cx - radius, cx + radius, cz - radius, cz + radius), ring_col, radius)
    inner_r = radius * 0.78
    rounded_panel(group, name + "-cut",
                  (cx - inner_r, cx + inner_r, cz - inner_r, cz + inner_r),
                  theme.AMBER_WASH if selected else theme.CARBON_CARD, inner_r)
    if selected or installed:
        core_r = radius * 0.44
        rounded_panel(group, name + "-core",
                      (cx - core_r, cx + core_r, cz - core_r, cz + core_r),
                      theme.AMBER if selected else theme.WHITE, core_r)
    return group


def gradient_panel(parent, name, box, color_a, color_b, *, horizontal=False):
    """顶点渐变遮罩：在摄影与车库布景边缘营造平滑黑曜石渐隐，突出主体与字迹层次。"""
    left, right, bottom, top = box
    data = GeomVertexData(name, GeomVertexFormat.getV3c4(), Geom.UHStatic)
    pos = GeomVertexWriter(data, "vertex")
    col = GeomVertexWriter(data, "color")
    if horizontal:
        corners = (
            (left, bottom, color_a),
            (right, bottom, color_b),
            (right, top, color_b),
            (left, top, color_a),
        )
    else:
        corners = (
            (left, bottom, color_a),
            (right, bottom, color_a),
            (right, top, color_b),
            (left, top, color_b),
        )
    for x, z, rgba in corners:
        pos.addData3f(x, 0, z)
        col.addData4f(*rgba)
    triangles = GeomTriangles(Geom.UHStatic)
    triangles.addVertices(0, 1, 2)
    triangles.addVertices(0, 2, 3)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    result = parent.attachNewNode(node)
    result.setTransparency(TransparencyAttrib.MAlpha)
    result.setDepthTest(False)
    result.setDepthWrite(False)
    return result


@lru_cache(maxsize=64)
def button_textures(variant, aspect=4):
    """按宽高比生成等比圆角按钮材质，确保任意宽度与分辨率下四边细描边连续清晰。"""
    if variant == "lab_primary":
        fills = ((.880, .365, .115), (.940, .430, .175), (.760, .295, .080), (.78, .80, .84))
        border_rgb = (.880, .365, .115)
    elif variant is True or variant == "primary":
        fills = ((.949, .690, .255), (1.000, .765, .355), (.835, .585, .175), (.78, .80, .84))
        border_rgb = (.949, .690, .255)
    elif variant == "dark":
        fills = ((.105, .128, .172), (.155, .188, .250), (.075, .092, .128), (.082, .096, .126))
        border_rgb = (.245, .292, .375)
    else:
        fills = ((.994, .996, .999), (.936, .950, .972), (.882, .902, .936), (.93, .94, .96))
        border_rgb = (.745, .782, .832)
    textures = []
    height = 64
    ratio = max(1, min(16, round(aspect)))
    width = min(640, max(64, height * ratio))
    radius = 12
    stroke = 2.6
    for index, fill in enumerate(fills):
        image = PNMImage(width, height, 4)
        border = fill if (variant in (True, "primary", "lab_primary")) else border_rgb
        for y in range(height):
            for x in range(width):
                dx = max(radius-x-.5, x+.5-(width-radius), 0.)
                dy = max(radius-y-.5, y+.5-(height-radius), 0.)
                distance = math.hypot(dx, dy)
                alpha = min(1., max(0., radius+.5-distance))
                edge = min(x+.5, width-x-.5, y+.5, height-y-.5, radius-distance)
                color = border if edge < stroke else fill
                image.setXelA(x, y, *color, alpha)
        texture = Texture(f"lab-button-{variant}-{ratio}-{index}")
        texture.load(image)
        texture.setWrapU(SamplerState.WMClamp)
        texture.setWrapV(SamplerState.WMClamp)
        texture.setMinfilter(SamplerState.FTLinearMipmapLinear)
        texture.setMagfilter(SamplerState.FTLinear)
        textures.append(texture)
    return tuple(textures)
