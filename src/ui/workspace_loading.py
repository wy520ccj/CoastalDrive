"""同一窗口的工作方式过渡；进度只来自已完成的加载阶段。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from ui import theme


class WorkspaceLoading:
    def __init__(self, base):
        self.base = base
        self.font = theme.load_font("fonts/SourceHanSansSC-Bold.otf")
        self.display_font = theme.load_font(theme.DISPLAY_FONT_FILE)
        self.root = DirectFrame(parent=base.aspect2d, frameColor=theme.PAPER,
                                frameSize=(-8, 8, -2, 2), state=DGG.NORMAL, sortOrder=1000)
        self.art = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=base.loader.loadTexture(theme.asset_filename("backgrounds/workspace-handdrawn-v2.png")),
            frameSize=(-16/9, 16/9, -1, 1))
        self.content = self.root.attachNewNode("loading-content")
        DirectFrame(parent=self.content, frameColor=theme.PAPER_LIGHT,
                    frameSize=(-1.60, -.57, .65, .92))
        self.text("COASTAL DRIVE", -1.53, .79, .085, self.display_font)
        self.text("车辆设计  /  工程验证  /  海岸试驾", -1.52, .70, .031)
        self.title = self.text("正在准备海岸驾驶", -1.50, -.52, .067)
        self.stage = self.text("准备窗口与车辆", -1.50, -.66, .036, color=theme.MUTED)
        self.counter = self.text("", 1.50, -.66, .038, align=TextNode.ARight)
        DirectFrame(parent=self.content, frameColor=(.78, .83, .81, 1),
                    frameSize=(-1.50, 1.50, -.76, -.744))
        self.bar = DirectFrame(parent=self.content, frameColor=theme.ORANGE,
                              frameSize=(0, 1, -.008, .008), pos=(-1.50, 0, -.752))
        self.vehicle = self.text("同一辆车，从试验场到海岸线", -1.50, -.87, .032, color=theme.MUTED)
        self.tip = self.text("", 1.50, -.87, .031, color=theme.MUTED, align=TextNode.ARight)
        self.exit_button = DirectButton(parent=self.content, text="退出", text_font=self.font,
            text_scale=.035, text_fg=theme.INK, frameColor=theme.PAPER,
            frameSize=(-.15, .15, -.04, .05), pos=(1.35, 0, -.96), command=base.userExit)
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
        self.bar.setSx(3*completed/total)
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
