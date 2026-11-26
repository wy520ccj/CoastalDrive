"""落日工坊（Sunset Atelier）风格加载页：通顶海岸手绘画卷 + 紧凑底部黑曜石进度坞 + 微缩公路跑车进度条。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

from ui import atelier, theme
from ui.lab_widgets import gradient_panel, rounded_panel

# 在深黑曜石底上保持清晰对比度的冷静银灰辅助字色。
_STAGE_FG = (0.86, 0.90, 0.96, 1)
_ROAD_LEFT = -1.598
_ROAD_RIGHT = 1.598
_ROAD_Z = -0.836
_CAR_START_X = -1.465
_CAR_END_X = 1.435


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

        # 轻柔底缘压暗托住底部卡片，完全通顶保留蓝天流云、海岸线与插画橙车。
        gradient_panel(self.content, "load-scrim-bottom", (-1.82, 1.82, -1.02, -.48),
                       (0.040, 0.050, 0.072, 0.72), (0.040, 0.050, 0.072, 0.0))

        # 左上角轻置带柔和投影的透明手刷标识，不再用厚重黑框切割天空。
        atelier.picture(self.content, base.loader, atelier.WORDMARK_BRUSH,
                        (-1.662, -1.162, .852, .946), color=(0.04, 0.06, 0.10, 0.38))
        atelier.wordmark(self.content, base.loader, (-1.670, -1.170, .860, .954))

        # 底部紧凑黑曜石半透磨砂进度坞（z: -0.94 ~ -0.60，完全避开插画橙色小车）。
        rounded_panel(self.content, "dock-shadow", (-1.666, 1.666, -.946, -.594), (0.012, 0.018, 0.032, 0.48), .024)
        rounded_panel(self.content, "dock-edge", (-1.662, 1.662, -.942, -.598), theme.CARBON_EDGE, .022)
        rounded_panel(self.content, "dock-body", (-1.658, 1.658, -.938, -.602), (0.055, 0.068, 0.098, 0.90), .020)
        rounded_panel(self.content, "dock-accent", (-1.608, -1.594, -.716, -.642), theme.AMBER, .005)

        self.title = self.text("正在驶入海岸工坊", -1.568, -.696, .052, color=theme.WHITE)
        self.stage = self.text("正在点亮海岸车库灯光", 1.595, -.692, .037, self.regular,
                               color=_STAGE_FG, align=TextNode.ARight)

        # 下排微缩海岸公路进度轨：沥青路面、白线、中线虚线、终点棋盘旗与琥珀尾迹带。
        self.road_track = self.content.attachNewNode("loading-road-track")
        rounded_panel(self.road_track, "road-edge", (_ROAD_LEFT - .006, _ROAD_RIGHT + .006, -.885, -.787),
                      (0.22, 0.28, 0.38, 0.72), .012)
        rounded_panel(self.road_track, "road-bed", (_ROAD_LEFT, _ROAD_RIGHT, -.880, -.792),
                      (0.105, 0.130, 0.180, 0.96), .010)
        DirectFrame(parent=self.road_track, frameColor=(0.76, 0.82, 0.90, 0.42),
                    frameSize=(-1.588, 1.588, -.801, -.797))
        DirectFrame(parent=self.road_track, frameColor=(0.76, 0.82, 0.90, 0.42),
                    frameSize=(-1.588, 1.588, -.875, -.871))
        for i in range(26):
            dx = -1.545 + i * 0.120
            DirectFrame(parent=self.road_track, frameColor=(0.90, 0.92, 0.96, 0.46),
                        frameSize=(dx, min(1.535, dx + 0.066), -.838, -.834))

        # 终点琥珀标线与微缩格子旗。
        DirectFrame(parent=self.road_track, frameColor=theme.AMBER,
                    frameSize=(1.556, 1.564, -.876, -.796))
        DirectFrame(parent=self.road_track, frameColor=(0.86, 0.90, 0.96, 0.90),
                    frameSize=(1.558, 1.562, -.796, -.744))
        for row in range(2):
            for col in range(3):
                col_fg = theme.WHITE if (row + col) % 2 == 0 else (0.12, 0.15, 0.22, 0.96)
                fx = 1.562 + col * 0.011
                fz = -0.744 - row * 0.011
                DirectFrame(parent=self.road_track, frameColor=col_fg,
                            frameSize=(fx, fx + 0.011, fz - 0.011, fz))

        self.bar = DirectFrame(parent=self.road_track, frameColor=(0.949, 0.690, 0.255, 0.20),
                               frameSize=(0, 1, -.040, .040), pos=(_ROAD_LEFT, 0, _ROAD_Z))
        DirectFrame(parent=self.bar, frameColor=(0.949, 0.690, 0.255, 0.88),
                    frameSize=(0, 1, -.004, .004), pos=(0, 0, -.032))

        self.car = atelier.picture(self.road_track, base.loader, "atelier/icon-road-car.png",
                                   (-.13, .13, -.065, .065))
        self.car.setPos(_CAR_START_X, 0, -0.822)

        self.exit_button = DirectButton(parent=self.content, text="退出", text_font=self.font,
            text_scale=.034, text_fg=theme.INK, text_pos=(0, -.011),
            frameTexture=atelier.tex(base.loader, "atelier/btn-primary.png"),
            frameColor=(1, 1, 1, 1), relief=DGG.FLAT,
            frameSize=(-.15, .15, -.038, .038), pos=(1.445, 0, -.836), command=base.userExit,
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
        self.road_track.show()
        self.exit_button.hide()
        self.history = []
        self.advance(0, "正在检查车辆状态")
        self.resize()
        self.root.show()

    def advance(self, completed, stage, total=5):
        self.stage.setText(stage)
        frac = max(0.0, min(1.0, completed / max(1, total)))
        car_x = _CAR_START_X + (_CAR_END_X - _CAR_START_X) * frac
        self.car.setX(car_x)
        if frac <= 0.0:
            self.bar.hide()
        else:
            self.bar.show()
            self.bar.setSx(max(0.01, car_x - _ROAD_LEFT))
        self.history.append((completed, total, stage))

    def resize(self):
        aspect = self.base.getAspectRatio()
        self.art.setScale(max(1., aspect/(16/9)))
        self.content.setScale(min(1., aspect/(16/9)))

    def hide(self):
        self.root.hide()

    def fail(self):
        self.stage.setText("加载未完成，请查看 runtime.log 后重新打开")
        self.road_track.hide()
        self.exit_button.show()

    def close(self):
        self.root.destroy()