"""落日工坊（Sunset Atelier）风格加载页：完整保留海岸手绘画卷 + 顶栏标识带 + 底部黑曜石进度坞。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

from ui import atelier, theme
from ui.lab_widgets import gradient_panel, rounded_panel

# 在深黑曜石底上保持清晰对比度（>= 7:1）的冷静银灰辅助字色。
_STAGE_FG = (0.76, 0.81, 0.88, 1)
_META_FG = (0.64, 0.70, 0.78, 1)


class WorkspaceLoading:
    def __init__(self, base):
        self.base = base
        self.font = theme.load_font("fonts/SourceHanSansSC-Bold.otf")
        self.regular = theme.load_font("fonts/SourceHanSansSC-Regular.otf")
        self.display_font = theme.load_font(theme.DISPLAY_FONT_FILE)
        self.root = DirectFrame(parent=base.aspect2d, frameColor=theme.SLATE_BG,
                                frameSize=(-8, 8, -2, 2), state=DGG.NORMAL, sortOrder=1000)
        self.art = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=base.loader.loadTexture(theme.asset_filename("backgrounds/workspace-handdrawn-v2.png")),
            frameSize=(-16/9, 16/9, -1, 1))
        self.content = self.root.attachNewNode("loading-content")
        self.content.setTransparency(TransparencyAttrib.MAlpha)

        # 轻柔底缘压暗托住底部卡片，完全不遮挡中部海景、公路与橙色小车。
        gradient_panel(self.content, "load-scrim-bottom", (-1.82, 1.82, -1.02, -.46),
                       (0.040, 0.050, 0.072, 0.78), (0.040, 0.050, 0.072, 0.0))

        # 顶部通栏黑曜石标识带（与首页/车库/暂停页顶栏完全统一，不再半截切天）。
        atelier.picture(self.content, base.loader, "atelier/bar-top.png", (-1.80, 1.80, .835, 1.02))
        DirectFrame(parent=self.content, frameColor=theme.CARBON_EDGE, frameSize=(-1.80, 1.80, .834, .837))
        atelier.wordmark(self.content, base.loader, (-1.68, -1.16, .870, .968))
        DirectFrame(parent=self.content, frameColor=(0.34, 0.40, 0.50, 0.78), frameSize=(-1.105, -1.099, .880, .958))
        self.text("海岸驾驶  ·  车辆动力学与公路试驾", -1.06, .902, .031, self.regular, color=_STAGE_FG)
        rounded_panel(self.content, "load-badge-edge", (1.356, 1.684, .882, .954), theme.STEEL_LINE, .012)
        rounded_panel(self.content, "load-badge-bg", (1.360, 1.680, .886, .950), theme.STEEL_BG, .010)
        rounded_panel(self.content, "load-badge-dot", (1.392, 1.408, .910, .926), theme.AMBER, .008)
        self.text("正在加载", 1.430, .905, .028, self.font, color=theme.STEEL_TEXT)

        # 底部精炼黑曜石进度坞（避开海景与橙车，零泥灰脏边、高对比清晰可读）。
        rounded_panel(self.content, "dock-shadow", (-1.665, 1.665, -.950, -.540), (0.012, 0.018, 0.032, 0.52), .024)
        rounded_panel(self.content, "dock-edge", (-1.664, 1.664, -.944, -.546), theme.CARBON_EDGE, .022)
        rounded_panel(self.content, "dock-body", (-1.660, 1.660, -.940, -.550), (0.058, 0.072, 0.102, 0.94), .020)
        rounded_panel(self.content, "dock-accent", (-1.608, -1.594, -.670, -.592), theme.AMBER, .005)

        self.title = self.text("正在准备海岸驾驶", -1.568, -.650, .062, color=theme.WHITE)
        self.stage = self.text("准备窗口与车辆", -1.568, -.732, .032, self.regular, color=_STAGE_FG)
        self.counter = self.text("", 1.595, -.665, .042, self.display_font,
                                 color=theme.AMBER, align=TextNode.ARight)

        # 细精密琥珀金进度轨。
        rounded_panel(self.content, "bar-track-edge", (-1.602, 1.602, -.796, -.774), (0.24, 0.30, 0.40, 0.72), .007)
        rounded_panel(self.content, "bar-track", (-1.598, 1.598, -.792, -.778), (0.11, 0.14, 0.20, 0.96), .005)
        self.bar = DirectFrame(parent=self.content, frameColor=theme.AMBER,
                               frameSize=(0, 1, -.007, .007), pos=(-1.598, 0, -.785))

        self.vehicle = self.text("同一辆车，从试验场到海岸线", -1.598, -.878, .030, self.regular, color=theme.WHITE)
        self.tip = self.text("", 1.595, -.878, .029, self.regular, color=_META_FG, align=TextNode.ARight)
        self.exit_button = DirectButton(parent=self.content, text="退出", text_font=self.font,
            text_scale=.034, text_fg=theme.INK, text_pos=(0, -.011),
            frameTexture=atelier.tex(base.loader, "atelier/btn-primary.png"),
            frameColor=(1, 1, 1, 1), relief=DGG.FLAT,
            frameSize=(-.15, .15, -.040, .040), pos=(1.445, 0, -.868), command=base.userExit,
            pressEffect=False)
        self.exit_button.setTransparency(TransparencyAttrib.MAlpha)
        self.exit_button.hide()
        self.history = []
        self.root.hide()

    def text(self, value, x, z, scale, font=None, *, color=theme.WHITE, align=TextNode.ALeft):
        return OnscreenText(parent=self.content, text=value, pos=(x, z), scale=scale,
                            font=font or self.font, fg=color, align=align, mayChange=True)

    def show(self, title, vehicle="", tip=""):
        self.title.setText(title)
        self.vehicle.setText(vehicle or "同一辆车，从试验场到海岸线")
        self.tip.setText(tip)
        self.tip.show()
        self.exit_button.hide()
        self.history = []
        self.advance(0, "准备切换")
        self.resize()
        self.root.show()

    def advance(self, completed, stage, total=5):
        self.stage.setText(stage)
        self.counter.setText(f"{completed} / {total}")
        if completed <= 0:
            self.bar.hide()
        else:
            self.bar.show()
            self.bar.setSx(3.196*completed/total)
        self.history.append((completed, total, stage))

    def resize(self):
        aspect = self.base.getAspectRatio()
        self.art.setScale(max(1., aspect/(16/9)))
        self.content.setScale(min(1., aspect/(16/9)))

    def hide(self):
        self.root.hide()

    def fail(self):
        self.stage.setText("加载未完成，请查看 runtime.log 后重新打开")
        self.tip.hide()
        self.exit_button.show()

    def close(self):
        self.root.destroy()
