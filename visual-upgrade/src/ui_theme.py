"""像素界面主题：设计图配色、字号与间距的唯一来源。

所有尺寸以 1080p 参考像素为单位，由 ui_components.Canvas 换算到当前窗口，
因此 720p 与 1080p 使用同一套布局常量。
"""

from pathlib import Path

# 设计图取色（与 tools/make_ui_textures.py 保持一致）
INK = (0.063, 0.169, 0.227, 1)
INK_SOFT = (0.13, 0.27, 0.35, 1)
INK_MUTED = (0.40, 0.47, 0.51, 1)
PAPER = (0.953, 0.937, 0.890, 1)
PAPER_LIGHT = (0.996, 0.988, 0.960, 1)
PAPER_DARK = (0.855, 0.845, 0.800, 1)
ORANGE = (0.957, 0.486, 0.141, 1)
ORANGE_LIGHT = (1.0, 0.65, 0.29, 1)
GOLD = (1.0, 0.761, 0.278, 1)
RED = (0.804, 0.239, 0.176, 1)
GREEN = (0.278, 0.616, 0.353, 1)
WHITE = (1, 1, 1, 1)
SHADOW = (0.10, 0.15, 0.18, 0.35)

# 参考分辨率：所有布局像素都按 1080p 高度描述
REFERENCE_HEIGHT = 1080
HALF_HEIGHT = REFERENCE_HEIGHT / 2

# 字号（参考像素）。字体是 12px 像素字体，字号取 12 的整数倍才不会糊边。
FONT_TITLE = 72
FONT_HEADING = 36
FONT_SUBHEAD = 24
FONT_BODY = 24
FONT_LABEL = 24
FONT_CAPTION = 24
FONT_NUMERIC = 60
FONT_SPEED = 72
FONT_GEAR = 36

# 像素字体笔画偏细，用同色偏移约 1 像素描边加粗，接近设计图的厚度
TEXT_BOLD_OFFSET = 1.2

# 圆角与描边对应的九宫格角块像素
CORNER = 12

# 页面与元素间距（参考像素）
MARGIN = 44
PANEL_PADDING = 28
GAP = 14
BUTTON_HEIGHT = 52
BUTTON_GAP = 12
ROW_HEIGHT = 46

UI_ASSETS = Path(__file__).resolve().parent.parent / "assets/game/ui"

# 界面中文用 Ark Pixel 12px（SIL OFL 1.1，见 fonts/ark-pixel-LICENSE-OFL.txt）；
# 文件缺失时回退到仓库原有的 Fusion Pixel。字号取 12 的整数倍才不糊边。
FONT_FILE = UI_ASSETS / "fonts/ark-pixel-12px-proportional-zh_cn.ttf"
FALLBACK_FONT_FILE = UI_ASSETS / "fonts/fusion-pixel-12px-proportional-zh_hans.ttf"
FONT_UNITS_PER_EM = 32
