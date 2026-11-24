"""日光画廊加载过渡：全幅手绘海岸画卷 + 轻盈瓷白悬浮品牌卡与底部悬浮进度条卡。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

from ui import theme
from ui.lab_widgets import rounded_panel


class WorkspaceLoading:
    def __init__(self, base):
        self.base = base
        self.font = theme.load_font("fonts/SourceHanSansSC-Bold.otf")
        self.regular = theme.load_font("fonts/SourceHanSansSC-Regular.otf")
        self.display_font = theme.load_font(theme.DISPLAY_FONT_FILE)
        self.root = DirectFrame(parent=base.aspect2d, frameColor=theme.CANVAS,
                                frameSize=(-8, 8, -2, 2), state=DGG.NORMAL, sortOrder=1000)
        self.art = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=base.loader.loadTexture(theme.asset_filename("backgrounds/workspace-handdrawn-v2.png")),
            frameSize=(-16/9, 16/9, -1, 1))
        self.content = self.root.attachNewNode("loading-content")
        self.content.setTransparency(TransparencyAttrib.MAlpha)

        # 左上角轻盈瓷白悬浮品牌卡（彻底摒弃厚重深蓝底板）。
        rounded_panel(self.content, "brand-shadow", (-1.615, -.615, .678, .908), theme.SHADOW, .028)
        rounded_panel(self.content, "brand-edge", (-1.624, -.616, .686, .924), theme.HAIRLINE, .030)
        rounded_panel(self.content, "brand-badge", (-1.62, -.62, .69, .92), theme.GLASS_LIGHT, .028)
        rounded_panel(self.content, "brand-accent", (-1.592, -1.576, .725, .885), theme.ORANGE, .006)
        self.text("COASTAL DRIVE", -1.545, .805, .072, self.display_font, color=theme.INK)
        self.text("车辆工程  ·  动力学试验  ·  海岸试驾", -1.545, .725, .029, self.regular, color=theme.MUTED)

        # 底部居中瓷白悬浮进度卡片（通透轻盈，不再压暗整幅海岸画卷）。
        rounded_panel(self.content, "load-shadow", (-1.615, 1.625, -.948, -.462), theme.SHADOW, .032)
        rounded_panel(self.content, "load-edge", (-1.624, 1.624, -.944, -.456), theme.HAIRLINE, .034)
        rounded_panel(self.content, "load-card", (-1.62, 1.62, -.94, -.46), theme.GLASS_LIGHT, .032)
        rounded_panel(self.content, "load-accent", (-1.56, -1.546, -.618, -.516), theme.ORANGE, .005)
        self.title = self.text("正在准备海岸驾驶", -1.515, -.582, .062, color=theme.INK)
        self.stage = self.text("准备窗口与车辆", -1.515, -.682, .033, self.regular, color=theme.MUTED)
        self.counter = self.text("", 1.54, -.682, .036, color=theme.ORANGE, align=TextNode.ARight)
        rounded_panel(self.content, "bar-track", (-1.54, 1.54, -.766, -.744), theme.MIST, .011)
        self.bar = DirectFrame(parent=self.content, frameColor=theme.ORANGE,
                              frameSize=(0, 1, -.010, .010), pos=(-1.54, 0, -.755))
        self.vehicle = self.text("同一辆车，从试验场到海岸线", -1.54, -.865, .031, self.regular, color=theme.MUTED)
        self.tip = self.text("", 1.54, -.865, .030, self.regular, color=theme.MUTED, align=TextNode.ARight)
        self.exit_button = DirectButton(parent=self.content, text="退出", text_font=self.font,
            text_scale=.035, text_fg=(1, 1, 1, 1), frameColor=theme.CHARCOAL,
            frameSize=(-.15, .15, -.04, .05), pos=(1.39, 0, -.86), command=base.userExit)
        self.exit_button.hide()
        self.history = []
        self.root.hide()

    def text(self, value, x, z, scale, font=None, *, color=theme.INK, align=TextNode.ALeft):
        return OnscreenText(parent=self.content, text=value, pos=(x, z), scale=scale,
                            font=font or self.font, fg=color, align=align, mayChange=True)

    def show(self, title, vehicle="", tip=""):
        self.title.setText(title)
        self.vehicle.setText(vehicle or "同一辆车，从试验场到海岸线")
        self.tip.setText(tip)
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
            self.bar.setSx(3.08*completed/total)
        self.history.append((completed, total, stage))

    def resize(self):
        aspect = self.base.getAspectRatio()
        self.art.setScale(max(1., aspect/(16/9)))
        self.content.setScale(min(1., aspect/(16/9)))

    def hide(self):
        self.root.hide()

    def fail(self):
        self.stage.setText("加载未完成，请查看 runtime.log 后重新打开")
        self.exit_button.show()

    def close(self):
        self.root.destroy()
