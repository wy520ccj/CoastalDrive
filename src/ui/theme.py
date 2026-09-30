"""VI v1 主题：字体、语义颜色与品牌资源；不持有页面或游戏状态。"""

from panda3d.core import DynamicTextFont, Filename, SamplerState

from paths import resource_root

BRAND_NAME = "COASTAL DRIVE"
FONT_FILE = "fonts/SourceHanSansSC-Heavy.otf"
FONT_LICENSE = "fonts/OFL-SourceHanSans.txt"
DISPLAY_FONT_FILE = "fonts/ChakraPetch-BoldItalic.ttf"
# 覆盖 1080p 大标题的实际像素高度，避免放大低分辨率字形。
FONT_PIXELS_PER_UNIT = 160

# 奶白底与深海蓝字；橙色仅用于强调，不承担成功/失败语义。
INK = (16 / 255, 43 / 255, 58 / 255, 1)
PAPER = (243 / 255, 239 / 255, 227 / 255, 1)
PAPER_LIGHT = (254 / 255, 252 / 255, 245 / 255, 1)
ORANGE = (244 / 255, 124 / 255, 36 / 255, 1)
SEA = (36 / 255, 126 / 255, 150 / 255, 1)
MUTED = (0.27, 0.36, 0.39, 1)
SUCCESS = (0.13, 0.40, 0.29, 1)
FAILURE = (0.58, 0.17, 0.08, 1)
PANEL_TINT = (1, 1, 1, 0.98)
HUD_TINT = (1, 1, 1, 0.94)
BUTTON_TINT = (1, 1, 1, 1)
SECONDARY_BUTTON_TINT = (0.95, 0.96, 0.96, 1)
TEXT_SHADOW = (0, 0, 0, 0)
DIAGNOSTIC_TEXT = (0.94, 0.97, 1, 1)
DIAGNOSTIC_SHADOW = (0, 0, 0, 0.6)


def asset_filename(name):
    """文件缺失是部署错误，报告确切路径，不悄悄换主题。"""
    path = resource_root() / "assets/game/ui" / name
    if not path.is_file():
        raise FileNotFoundError(f"缺少界面资源：{path}")
    return Filename.fromOsSpecific(str(path))


def load_font(filename=FONT_FILE):
    # 独立字体实例避免重复启动时修改 FontPool 中已生成字形的字体。
    font = DynamicTextFont(asset_filename(filename))
    if not font.isValid():
        raise OSError(f"无法读取界面字体：{filename}")
    font.setPixelsPerUnit(FONT_PIXELS_PER_UNIT)
    font.setMinfilter(SamplerState.FTLinear)
    font.setMagfilter(SamplerState.FTLinear)
    return font


def text_style(font):
    return {"fg": INK, "shadow": TEXT_SHADOW, "font": font}
