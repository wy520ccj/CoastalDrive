"""落日黑曜石与琥珀金（Sunset Obsidian & Amber Gold）统一视觉系统：克制、精密、汽车工坊级色彩与控件令牌。"""

from panda3d.core import DynamicTextFont, Filename, SamplerState

from paths import resource_root

BRAND_NAME = "COASTAL DRIVE"
FONT_FILE = "fonts/SourceHanSansSC-Heavy.otf"
FONT_LICENSE = "fonts/OFL-SourceHanSans.txt"
DISPLAY_FONT_FILE = "fonts/ChakraPetch-BoldItalic.ttf"
# 覆盖 1080p 大标题的实际像素高度，避免放大低分辨率字形。
FONT_PIXELS_PER_UNIT = 160

# ── 浅底对比度基准令牌（保留试验台浅色曲线/图表卡片高可读性，满足 WCAG >= 4.5）──
INK = (0.068, 0.084, 0.114, 1)            # 深黑曜石正文（用于浅底 & 琥珀金主按钮文字）
CANVAS = (0.945, 0.953, 0.965, 1)         # 冷静浅灰陶瓷画布
PAPER = (0.958, 0.964, 0.974, 1)          # 明净冷白基准
PAPER_LIGHT = (0.992, 0.994, 0.998, 1)    # 洁净白卡
GLASS_LIGHT = (0.975, 0.980, 0.988, 0.94)
MIST = (0.905, 0.918, 0.938, 1)
HAIRLINE = (0.810, 0.832, 0.868, 1)
MUTED = (0.310, 0.348, 0.415, 1)          # 冷石板灰辅助文字（在 PAPER 上 >= 6.4:1）
LOCKED = (0.520, 0.560, 0.625, 1)
SUCCESS = (0.060, 0.470, 0.310, 1)        # 达标翡翠绿（在 PAPER 上 >= 5.1:1）
FAILURE = (0.720, 0.160, 0.140, 1)        # 警示珊瑚红（在 PAPER 上 >= 5.1:1）

# ── 核心午夜黑曜石深色表面体系（复刻参考图右侧面板与底栏质感）──
CHARCOAL = (0.071, 0.086, 0.118, 1)       # #12161E 主哑光黑曜石底
CHARCOAL_SOFT = (0.115, 0.138, 0.184, 1)  # #1D232F 次级控件/悬停底
CARBON = (0.068, 0.084, 0.115, 0.94)      # 磨砂黑曜石面板
CARBON_SOLID = (0.075, 0.092, 0.125, 1)   # 实心黑曜石主面板
CARBON_CARD = (0.102, 0.124, 0.166, 0.96) # #1A202A 选项卡片静止底
CARBON_EDGE = (0.192, 0.228, 0.296, 0.92) # #313A4B 1px 精密细描边
CARBON_GLASS = (0.065, 0.080, 0.112, 0.82) # 展车上悬浮的通透黑玻璃
SHADOW = (0.015, 0.022, 0.038, 0.45)

# ── 核心落日琥珀金（#F2B041）与冷静钢蓝（#8BB8E8）强调体系 ──
AMBER = (0.949, 0.690, 0.255, 1)          # #F2B041 落日琥珀金（主 CTA / 选中边框 / 焦点）
AMBER_BRIGHT = (1.000, 0.765, 0.355, 1)   # #FFC35A 琥珀金高亮悬停
AMBER_WASH = (0.195, 0.160, 0.102, 0.95)  # 选中行内部的暖琥珀微光暗底
AMBER_TINT = (0.988, 0.945, 0.855, 1)     # 浅底琥珀柔光（试验台 B 槽）

STEEL_BG = (0.137, 0.200, 0.290, 0.95)    # #23334A 「已安装 / 已解锁」钢蓝徽章底
STEEL_TEXT = (0.545, 0.722, 0.910, 1)     # #8BB8E8 冷静冰钢蓝文字
STEEL_LINE = (0.285, 0.435, 0.605, 0.92)

# 兼容别名：全站统一归束到克制的落日琥珀金 + 冷静钢蓝，绝不刺眼杂乱。
ORANGE = AMBER
ORANGE_BRIGHT = AMBER_BRIGHT
ORANGE_TINT = AMBER_TINT
MAGENTA = AMBER
MAGENTA_BRIGHT = AMBER_BRIGHT
MAGENTA_TINT = AMBER_TINT
MAGENTA_DARK = AMBER_WASH

RUSH = (0.895, 0.525, 0.225, 1)           # 暖铜橙（柔和不刺眼）
RUSH_TINT = AMBER_TINT
SEA = (0.435, 0.690, 0.875, 1)            # 冷静海岸钢蓝（路线/A对照/状态）
SEA_TINT = (0.895, 0.945, 0.985, 1)
PINE = (0.265, 0.765, 0.565, 1)           # 柔和薄荷翡翠（领先/达标）
PINE_TINT = (0.895, 0.968, 0.938, 1)
VIOLET = (0.555, 0.605, 0.885, 1)         # 冷静暮光蓝紫（专家试验台）
VIOLET_TINT = (0.920, 0.932, 0.985, 1)
BURGUNDY = VIOLET
BURGUNDY_TINT = VIOLET_TINT

GOLD = AMBER
GOLD_DEEP = (0.765, 0.520, 0.125, 1)
SILVER = (0.680, 0.725, 0.790, 1)
BRONZE = (0.805, 0.525, 0.305, 1)

# 深色黑曜石界面文字令牌。
WHITE = (0.955, 0.965, 0.982, 1)          # 柔和象牙白，久看不刺眼
PURE_WHITE = (1.0, 1.0, 1.0, 1.0)
DARK_TEXT = WHITE
DARK_SUB = (0.560, 0.610, 0.690, 1)       # #8F9CB0 冷静银灰辅助字
DARK_LOCKED = (0.375, 0.415, 0.485, 1)

# 全站通用表面令牌（黑曜石哑光主母版）。
SLATE_BG = (0.062, 0.076, 0.104, 1)       # #10131A 极深黑曜石背景
SLATE_BAR = (0.065, 0.080, 0.110, 0.96)   # 顶底细线条黑曜石通栏
SLATE_GLASS = CARBON
SLATE_CARD = CARBON_CARD
SLATE_CARD_HI = AMBER_WASH
SLATE_BORDER = CARBON_EDGE
TEXT_LIGHT = DARK_TEXT
TEXT_SUB = DARK_SUB
TEXT_LOCKED = DARK_LOCKED

PANEL_TINT = (1, 1, 1, 0.98)
HUD_TINT = (1, 1, 1, 0.94)
BUTTON_TINT = (1, 1, 1, 1)
SECONDARY_BUTTON_TINT = (0.92, 0.94, 0.97, 1)
TEXT_SHADOW = (0, 0, 0, 0)
DIAGNOSTIC_TEXT = (0.96, 0.97, 0.99, 1)
DIAGNOSTIC_SHADOW = (0.04, 0.06, 0.10, 0.75)

# 克制高级的实车性能分级徽章色系（纯界面显示，绝不影响物理）。
PI_CLASSES = (
    ("S2", 901, (0.340, 0.560, 0.860, 1)),
    ("S1", 801, (0.545, 0.495, 0.845, 1)),
    ("A", 701, (0.885, 0.440, 0.310, 1)),
    ("B", 601, (0.925, 0.635, 0.245, 1)),
    ("C", 501, (0.875, 0.720, 0.285, 1)),
    ("D", 100, (0.365, 0.640, 0.805, 1)),
)


def vehicle_pi(config):
    """由实车物理参数换算性能分级与四维显示条，纯视觉呈现不改动物理。"""
    power_kw = max(rpm * torque / 9549.3 for rpm, torque in config.torque_curve)
    pw_ratio = power_kw / max(500.0, config.mass) * 1000.0
    grip = (config.lateral_stiffness + config.rear_lateral_stiffness) / 2000.0
    brake = config.brake_torque / max(500.0, config.mass)
    score = round(max(280.0, min(998.0, 320.0 + pw_ratio * 2.15 + grip * 0.85 + brake * 18.0)))
    letter, color = "D", PI_CLASSES[-1][2]
    for code, threshold, badge_color in PI_CLASSES:
        if score >= threshold:
            letter, color = code, badge_color
            break
    stats = (
        ("动力", min(1.0, max(0.18, power_kw / 280.0)), f"{power_kw:.0f} kW"),
        ("推重", min(1.0, max(0.18, pw_ratio / 220.0)), f"{pw_ratio:.0f}"),
        ("轻量", min(1.0, max(0.18, 1.0 - (config.mass - 750.0) / 1100.0)), f"{config.mass:.0f} kg"),
        ("制动", min(1.0, max(0.18, brake / 3.8)), f"{config.brake_torque:.0f}"),
    )
    return letter, score, color, power_kw, stats


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
