"""同一窗口的工作方式过渡；全屏手绘画幅搭配底部一体化深海信息带。"""

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
        self.root = DirectFrame(parent=base.aspect2d, frameColor=theme.SLATE_BG,
                                frameSize=(-8, 8, -2, 2), state=DGG.NORMAL, sortOrder=1000)
        self.art = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=base.loader.loadTexture(theme.asset_filename("backgrounds/workspace-handdrawn-v2.png")),
            frameSize=(-16/9, 16/9, -1, 1))
        self.content = self.root.attachNewNode("loading-content")
        self.content.setTransparency(TransparencyAttrib.MAlpha)

        # 左上角深海悬浮品牌角标，不再用死白方块遮挡天空。
        rounded_panel(self.content, "brand-badge", (-1.62, -.62, .69, .92), theme.SLATE_GLASS, .026)
        DirectFrame(parent=self.content, frameColor=theme.ORANGE, frameSize=(-1.62, -1.602, .725, .885))
        self.text("COASTAL DRIVE", -1.55, .805, .072, self.display_font, color=theme.TEXT_LIGHT)
        self.text("车辆工程  ·  动力学试验  ·  海岸试驾", -1.55, .725, .029, self.regular, color=theme.TEXT_SUB)

        # 底部一体化深海信息带，彻底隔开背景插画边缘与进度文字。
        DirectFrame(parent=self.content, frameColor=theme.SLATE_BAR, frameSize=(-1.78, 1.78, -1.0, -.44))
        DirectFrame(parent=self.content, frameColor=theme.SLATE_BORDER, frameSize=(-1.78, 1.78, -.443, -.44))
        self.title = self.text("正在准备海岸驾驶", -1.54, -.56, .062, color=theme.TEXT_LIGHT)
        self.stage = self.text("准备窗口与车辆", -1.54, -.67, .034, self.regular, color=theme.TEXT_SUB)
        self.counter = self.text("", 1.54, -.67, .036, color=theme.GOLD, align=TextNode.ARight)
        DirectFrame(parent=self.content, frameColor=(.18, .24, .31, 1),
                    frameSize=(-1.54, 1.54, -.758, -.742))
        self.bar = DirectFrame(parent=self.content, frameColor=theme.ORANGE,
                              frameSize=(0, 1, -.008, .008), pos=(-1.54, 0, -.750))
        self.vehicle = self.text("同一辆车，从试验场到海岸线", -1.54, -.86, .031, self.regular, color=theme.TEXT_SUB)
        self.tip = self.text("", 1.54, -.86, .030, self.regular, color=theme.TEXT_SUB, align=TextNode.ARight)
        self.exit_button = DirectButton(parent=self.content, text="退出", text_font=self.font,
            text_scale=.035, text_fg=theme.TEXT_LIGHT, frameColor=theme.SLATE_CARD_HI,
            frameSize=(-.15, .15, -.04, .05), pos=(1.39, 0, -.95), command=base.userExit)
        self.exit_button.hide()
        self.history = []
        self.root.hide()

    def text(self, value, x, z, scale, font=None, *, color=theme.TEXT_LIGHT, align=TextNode.ALeft):
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
