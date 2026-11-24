"""VI v2 日光赛车画廊主题：温润瓷白基底、纯粹中性炭黑排版与赛道朱红/海岸青点缀。"""

from panda3d.core import DynamicTextFont, Filename, SamplerState

from paths import resource_root

BRAND_NAME = "COASTAL DRIVE"
FONT_FILE = "fonts/SourceHanSansSC-Heavy.otf"
FONT_LICENSE = "fonts/OFL-SourceHanSans.txt"
DISPLAY_FONT_FILE = "fonts/ChakraPetch-BoldItalic.ttf"
# 覆盖 1080p 大标题的实际像素高度，避免放大低分辨率字形。
FONT_PIXELS_PER_UNIT = 160

# 日光赛车画廊主色（参考 GT7 / Forza Horizon / Porsche Configurator，零暗蓝黑脏灰）。
INK = (0.10, 0.105, 0.115, 1)
CHARCOAL = (0.105, 0.11, 0.12, 1)
CHARCOAL_SOFT = (0.18, 0.19, 0.21, 1)
CANVAS = (0.952, 0.952, 0.944, 1)
PAPER = (0.945, 0.948, 0.952, 1)
PAPER_LIGHT = (1.0, 1.0, 1.0, 1)
GLASS_LIGHT = (0.992, 0.992, 0.988, 0.91)
MIST = (0.935, 0.938, 0.944, 1)
HAIRLINE = (0.835, 0.845, 0.862, 1)
SHADOW = (0.06, 0.065, 0.075, 0.13)

# 经典赛车强调色：保时捷卫红/朱红、地中海海岸青、香槟金。
ORANGE = (0.90, 0.25, 0.15, 1)
ORANGE_BRIGHT = (0.97, 0.32, 0.20, 1)
ORANGE_TINT = (0.995, 0.935, 0.92, 1)
SEA = (0.05, 0.52, 0.65, 1)
MUTED = (0.41, 0.43, 0.47, 1)
LOCKED = (0.62, 0.64, 0.68, 1)
SUCCESS = (0.10, 0.58, 0.36, 1)
FAILURE = (0.82, 0.20, 0.16, 1)
GOLD = (0.78, 0.54, 0.11, 1)
SILVER = (0.46, 0.50, 0.56, 1)
BRONZE = (0.68, 0.41, 0.20, 1)

# 兼容别名（映射到新日光画廊令牌，彻底清除暗蓝石板旧色）。
SLATE_BG = CANVAS
SLATE_BAR = (1.0, 1.0, 1.0, 0.96)
SLATE_GLASS = GLASS_LIGHT
SLATE_CARD = PAPER_LIGHT
SLATE_CARD_HI = MIST
SLATE_BORDER = HAIRLINE
TEXT_LIGHT = INK
TEXT_SUB = MUTED
TEXT_LOCKED = LOCKED

PANEL_TINT = (1, 1, 1, 0.98)
HUD_TINT = (1, 1, 1, 0.94)
BUTTON_TINT = (1, 1, 1, 1)
SECONDARY_BUTTON_TINT = (0.95, 0.96, 0.96, 1)
TEXT_SHADOW = (0, 0, 0, 0)
DIAGNOSTIC_TEXT = (0.96, 0.97, 0.98, 1)
DIAGNOSTIC_SHADOW = (0, 0, 0, 0.65)


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
