"""VI v1 主题：字体、语义颜色与品牌资源；不持有页面或游戏状态。"""

from panda3d.core import DynamicTextFont, Filename, SamplerState

from paths import resource_root

BRAND_NAME = "COASTAL DRIVE"
FONT_FILE = "fonts/SourceHanSansSC-Heavy.otf"
FONT_LICENSE = "fonts/OFL-SourceHanSans.txt"
DISPLAY_FONT_FILE = "fonts/ChakraPetch-BoldItalic.ttf"
# 覆盖 1080p 大标题的实际像素高度，避免放大低分辨率字形。
FONT_PIXELS_PER_UNIT = 160

# 现代汽车工程画廊配色：精密冷瓷基底 × 深海岩灰浮层 × 赛道炽橙强调。
INK = (0.065, 0.095, 0.135, 1)
PAPER = (0.935, 0.947, 0.962, 1)
PAPER_LIGHT = (0.992, 0.995, 0.998, 1)
ORANGE = (0.95, 0.36, 0.14, 1)
ORANGE_BRIGHT = (1.0, 0.44, 0.22, 1)
SEA = (0.10, 0.56, 0.68, 1)
MUTED = (0.36, 0.43, 0.51, 1)
SUCCESS = (0.13, 0.56, 0.40, 1)
FAILURE = (0.76, 0.22, 0.18, 1)

# 深海暗色画廊令牌（供首页、生涯、加载、调校等主流程共享）。
SLATE_BG = (0.055, 0.078, 0.108, 1)
SLATE_BAR = (0.042, 0.060, 0.086, 0.94)
SLATE_GLASS = (0.068, 0.096, 0.134, 0.88)
SLATE_CARD = (0.098, 0.134, 0.182, 0.94)
SLATE_CARD_HI = (0.148, 0.198, 0.262, 0.98)
SLATE_BORDER = (0.21, 0.27, 0.35, 0.72)
TEXT_LIGHT = (0.965, 0.975, 0.985, 1)
TEXT_SUB = (0.67, 0.73, 0.80, 1)
TEXT_LOCKED = (0.48, 0.54, 0.62, 1)
GOLD = (0.95, 0.72, 0.24, 1)
SILVER = (0.78, 0.83, 0.89, 1)
BRONZE = (0.82, 0.53, 0.30, 1)

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
    # 同一字形用于大标题和小提示，多级缩小采样避免细笔画漏采。
    # 图集留边覆盖小字号的采样范围，几何留边防止抗锯齿边缘被截断。
    font.setTextureMargin(16)
    font.setPolyMargin(4)
    font.setMinfilter(SamplerState.FTLinearMipmapLinear)
    font.setMagfilter(SamplerState.FTLinear)
    return font


def text_style(font):
    return {"fg": INK, "shadow": TEXT_SHADOW, "font": font}
