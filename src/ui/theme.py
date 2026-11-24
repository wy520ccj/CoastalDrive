"""VI v3 暖阳海岸赛车画廊主题：暖沙亚麻基底、浓焙浓缩棕排版、落日赤陶/金盏琥珀/海岸青复古赛车三色系。"""

from panda3d.core import DynamicTextFont, Filename, SamplerState

from paths import resource_root

BRAND_NAME = "COASTAL DRIVE"
FONT_FILE = "fonts/SourceHanSansSC-Heavy.otf"
FONT_LICENSE = "fonts/OFL-SourceHanSans.txt"
DISPLAY_FONT_FILE = "fonts/ChakraPetch-BoldItalic.ttf"
# 覆盖 1080p 大标题的实际像素高度，避免放大低分辨率字形。
FONT_PIXELS_PER_UNIT = 160

# 暖阳里维埃拉赛车配色：零惨白、零冷暗蓝，层次温暖丰富。
INK = (0.175, 0.125, 0.095, 1)
CHARCOAL = (0.20, 0.14, 0.105, 1)        # 浓焙浓缩棕（主选中胶囊 / 深暖对比）
CHARCOAL_SOFT = (0.28, 0.20, 0.155, 1)   # 暖胡桃悬停
CANVAS = (0.953, 0.924, 0.878, 1)        # 暖沙亚麻画布
PAPER = (0.935, 0.898, 0.845, 1)         # 暖石灰华/羊皮纸基底
PAPER_LIGHT = (0.992, 0.976, 0.946, 1)   # 象牙奶油浮卡（绝非惨白）
GLASS_LIGHT = (0.985, 0.958, 0.914, 0.93)  # 暖阳磨砂奶油玻璃
MIST = (0.930, 0.888, 0.828, 1)          # 暖杏仁柔雾表面
HAIRLINE = (0.835, 0.775, 0.695, 1)      # 暖砂岩细描边
SHADOW = (0.22, 0.135, 0.075, 0.16)      # 暖棕柔和阴影

# 经典南欧复古 GT 赛车多色强调体系（丰富而不杂乱）。
ORANGE = (0.88, 0.33, 0.16, 1)           # 落日赤陶橙红（主行动）
ORANGE_BRIGHT = (0.95, 0.40, 0.21, 1)
ORANGE_TINT = (0.985, 0.910, 0.855, 1)   # 暖杏桃高亮底
AMBER = (0.87, 0.56, 0.13, 1)            # 黄金时刻琥珀金
AMBER_TINT = (0.985, 0.938, 0.835, 1)    # 浅蜂蜜暖底
SEA = (0.10, 0.50, 0.55, 1)              # 地中海海岸青
SEA_TINT = (0.885, 0.942, 0.935, 1)      # 浅海沫暖青底
PINE = (0.24, 0.51, 0.35, 1)             # 海岸松绿
PINE_TINT = (0.895, 0.942, 0.902, 1)     # 浅松烟底
BURGUNDY = (0.58, 0.22, 0.25, 1)         # 经典复古酒红
BURGUNDY_TINT = (0.965, 0.905, 0.900, 1) # 浅玫瑰陶底

MUTED = (0.46, 0.38, 0.31, 1)            # 暖古铜褐辅助文字
LOCKED = (0.67, 0.59, 0.51, 1)
SUCCESS = (0.19, 0.53, 0.34, 1)
FAILURE = (0.78, 0.22, 0.17, 1)
GOLD = (0.78, 0.50, 0.10, 1)
SILVER = (0.52, 0.47, 0.42, 1)
BRONZE = (0.70, 0.38, 0.17, 1)

# 兼容令牌别名（全站统一暖沙奶油 + 浓焙棕，彻底告别惨白与冷暗蓝）。
SLATE_BG = CANVAS
SLATE_BAR = (0.985, 0.962, 0.922, 0.97)
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
SECONDARY_BUTTON_TINT = (0.95, 0.93, 0.89, 1)
TEXT_SHADOW = (0, 0, 0, 0)
DIAGNOSTIC_TEXT = (0.98, 0.96, 0.92, 1)
DIAGNOSTIC_SHADOW = (0.15, 0.10, 0.06, 0.65)


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
