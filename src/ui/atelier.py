"""Sunset Atelier 共享美术贴图加载与轻量化绘制辅助（无状态缓存，不引入额外管理层）。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextureStage, TransparencyAttrib

from ui import theme

SUNSET_GARAGE_BG = "backgrounds/garage-sunset-workshop.png"
WORDMARK_BRUSH = "atelier/wordmark-brush.png"
BOLD_FONT_FILE = "fonts/SourceHanSansSC-Bold.otf"
REGULAR_FONT_FILE = "fonts/SourceHanSansSC-Regular.otf"

_CACHE = {}


def tex(loader, relative_name):
    key = (id(loader), relative_name)
    cached = _CACHE.get(key)
    if cached is None:
        cached = loader.loadTexture(theme.asset_filename(relative_name))
        _CACHE[key] = cached
    return cached


def picture(parent, loader, name, box, *, color=(1, 1, 1, 1), crop=False, sort_order=0):
    texture = tex(loader, name)
    frame = DirectFrame(
        parent=parent,
        frameSize=box,
        frameTexture=texture,
        frameColor=color,
        relief=DGG.FLAT,
        sortOrder=sort_order,
        state=DGG.DISABLED,
    )
    frame.setTransparency(TransparencyAttrib.MAlpha)
    if crop:
        w, h = box[1] - box[0], box[3] - box[2]
        if w > 0 and h > 0:
            ratio = (w / h) / (texture.getXSize() / texture.getYSize())
            stage = TextureStage.getDefault()
            if ratio < 1:
                frame.setTexScale(stage, ratio, 1)
                frame.setTexOffset(stage, (1 - ratio) / 2, 0)
            else:
                frame.setTexScale(stage, 1, 1 / ratio)
                frame.setTexOffset(stage, 0, (1 - 1 / ratio) / 2)
    return frame


def wordmark(parent, loader, box):
    """手刷质感 COASTAL DRIVE 透明标识图。"""
    return picture(parent, loader, WORDMARK_BRUSH, box, color=(0.96, 0.97, 0.99, 1))
