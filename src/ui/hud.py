"""驾驶 HUD 只将传入的快照和提示格式化，不维护车辆或比赛状态。"""

from direct.gui.DirectGui import DirectFrame, OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

from audio.music import STATIONS
from driving_modes import DrivingMode
from highway_map import HIGHWAY_LENGTH
from race import GameMode
from ui import theme


def set_text(widget, value):
    if widget.getText() != value:
        widget.setText(value)


def driving_help(mode, abs_label=None, tcs_label=None, esc_label=None):
    """输入说明只表达已有模式行为。"""
    direction = " · Q 倒挡 / E 前进挡" if mode == DrivingMode.SIMULATION else ""
    brake = "刹车" if mode == DrivingMode.SIMULATION else "刹车·倒车"
    electronics = ""
    if abs_label is not None:
        electronics = f" · ABS{abs_label}"
    if tcs_label is not None:
        electronics += f" TCS{tcs_label}"
    if esc_label is not None:
        electronics += f" ESC{esc_label}"
    return (f"驾驶模式：{mode.label}{direction}{electronics}\n"
            f"W / ↑ 油门   S / ↓ {brake}   A D 转向   R 复位   C 视角   N 切台   M 音乐   Esc 暂停")


class DrivingHUD:
    def __init__(self, parent, loader, body_font, number_font):
        self._active_rpm = None
        self._notice_source = None
        self._notice_height = None
        self._notice_lines = 1
        self._radio_station = None
        self._aspect = None
        self.root = parent.attachNewNode("driving-hud")
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        panel = loader.loadTexture(theme.asset_filename("components/panel.png"))
        self.status_frame = DirectFrame(
            parent=self.root, frameColor=(1, 1, 1, 1), frameTexture=panel,
            frameSize=(0, 0.88, -0.40, 0), pos=(-1.70, 0, 0.91),
        )
        self.mode = OnscreenText(parent=self.status_frame, text="", font=body_font,
                                fg=theme.INK, pos=(0.11, -0.071), scale=0.052,
                                align=TextNode.ALeft, mayChange=True)
        DirectFrame(parent=self.status_frame, frameColor=theme.ORANGE,
                    frameSize=(0.045, 0.055, -0.092, -0.035))
        DirectFrame(parent=self.status_frame, frameColor=(0.5, 0.55, 0.56, 0.4),
                    frameSize=(0.04, 0.84, -0.122, -0.119))
        self.status = OnscreenText(parent=self.status_frame, text="", font=number_font,
                                  fg=theme.INK, pos=(0.055, -0.212), scale=0.071,
                                  align=TextNode.ALeft, mayChange=True)
        self.detail = OnscreenText(parent=self.status_frame, text="", font=body_font,
                                  fg=theme.INK, pos=(0.055, -0.302), scale=0.041,
                                  align=TextNode.ALeft, mayChange=True)
        self.notice_frame = DirectFrame(parent=self.root, frameColor=(*theme.INK[:3], 1),
                                        frameSize=(0, 0.88, -0.18, 0), pos=(-1.70, 0, 0.50))
        # 底板固定实色，避免移动的树影/天空透进来形成明暗跳动。
        self.notice_frame.setTransparency(TransparencyAttrib.MNone)
        self.status_notice = OnscreenText(
            parent=self.notice_frame, text="", font=body_font, fg=theme.PAPER_LIGHT,
            pos=(0.035, -0.050), scale=0.034, align=TextNode.ALeft, mayChange=True,
        )
        # 提示一次排版即可；逐字测量每个增长前缀会让切台后的驾驶帧卡顿。
        self.status_notice.textNode.setWordwrap(0.80 / 0.034)
        # 三个固定电台标签在加载HUD时生成几何；切台只切换可见性。
        self.radio_labels = tuple(OnscreenText(
            parent=self.notice_frame, text=f"电台：{name}", font=body_font,
            fg=theme.PAPER_LIGHT, pos=(0.035, -0.050), scale=0.034,
            align=TextNode.ALeft, mayChange=False,
        ) for name in STATIONS)
        for label in self.radio_labels:
            label.hide()
        self.speed_frame = DirectFrame(
            parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=loader.loadTexture(theme.asset_filename("components/speed-panel.png")),
            frameSize=(-0.98, 0, 0, 0.33), pos=(1.70, 0, -0.90),
        )
        self.speed = OnscreenText(parent=self.speed_frame, text="000", font=number_font,
                                 fg=theme.PAPER_LIGHT, pos=(-0.89, 0.117), scale=0.165,
                                 align=TextNode.ALeft, mayChange=True)
        OnscreenText(parent=self.speed_frame, text="km/h", font=body_font,
                     fg=theme.PAPER_LIGHT, pos=(-0.36, 0.125), scale=0.042)
        self.gear_box = DirectFrame(parent=self.speed_frame, frameColor=(1, 0.73, 0.15, 1),
                                   frameSize=(-0.23, -0.06, 0.125, 0.265))
        self.gear = OnscreenText(parent=self.gear_box, text="D1", font=number_font, fg=theme.INK,
                                pos=(-0.15, 0.16), scale=0.068, mayChange=True)
        self.gear_rpm = OnscreenText(parent=self.speed_frame, text="", font=number_font,
                                    fg=theme.PAPER_LIGHT, pos=(-0.065, 0.077), scale=0.030,
                                    align=TextNode.ARight, mayChange=True)
        self.rpm_segments = [DirectFrame(parent=self.speed_frame, frameColor=theme.MUTED,
                                        frameSize=(-0.89 + i * 0.039, -0.86 + i * 0.039, 0.033, 0.064))
                             for i in range(21)]
        self.help_frame = DirectFrame(parent=self.root, frameColor=(*theme.INK[:3], 0.70),
                                      frameSize=(-0.75, 0.75, -0.045, 0.045), pos=(0, 0, -0.94))
        self.help = OnscreenText(parent=self.help_frame,
                                text="W / ↑ 油门    S / ↓ 刹车·倒车    A D 转向    R 复位    C 视角    N 切台    M 音乐    Esc 暂停",
                                font=body_font, fg=theme.PAPER_LIGHT, pos=(0, 0.009), scale=0.027, mayChange=True)

    def update(self, state, race, highway, *, track, countdown, notice,
               driving_mode=DrivingMode.GAME):
        player = state.player
        abs_label = "关闭" if not player.abs_enabled else (
            "介入" if any(brake.abs_active for brake in player.brake_states) else "待命"
        )
        tcs_label = "关闭" if not player.tcs_enabled else (
            "介入" if player.traction_state.active else "待命"
        )
        esc_label = "关闭" if not player.esc_enabled else (
            "介入" if player.stability_state.active else "待命"
        )
        set_text(self.help, driving_help(driving_mode, abs_label, tcs_label, esc_label))
        set_text(self.speed, f"{abs(state.player.speed) * 3.6:03.0f}")
        set_text(self.gear, "R" if state.player.gear < 0 else f"D{state.player.gear}")
        set_text(self.gear_rpm, f"{state.player.rpm:4.0f} rpm")
        # 色条直接表示当前发动机转速，末端标尺 7000 rpm；不改变物理转速。
        active = round(min(1, max(0, state.player.rpm / 7000)) * len(self.rpm_segments))
        if active != self._active_rpm:
            for i, segment in enumerate(self.rpm_segments):
                color = (1, 0.73, 0.15, 1) if i < 18 else (0.91, 0.16, 0.16, 1)
                segment["frameColor"] = color if i < active else (0.34, 0.41, 0.46, 1)
            self._active_rpm = active
        if track == "endless":
            set_text(self.mode, "5公里无碰撞挑战" if highway.challenge else "无限高速")
            set_text(self.status, f"{highway.elapsed:07.2f} s")
            distance = f"{highway.distance:.0f} / {highway.target:.0f} m" if highway.challenge else f"{highway.distance / 1000:.2f} km"
            set_text(self.detail, f"距离 {distance}\n碰撞 {highway.collisions} 次")
            message = "无碰撞行驶中" if highway.collisions == 0 else f"碰撞 {highway.collisions} 次"
        elif race.mode == GameMode.TIME_TRIAL:
            set_text(self.mode, "计时挑战")
            set_text(self.status, f"{race.elapsed:07.3f} s")
            target = "终点" if race.checkpoints == 4 else f"检查点 {race.next_checkpoint}"
            set_text(self.detail, f"检查点  {race.checkpoints} / 4\n下一目标  {target}")
            message = f"圈速无效：{race.invalid_reason}" if race.invalidated else "本圈有效"
        else:
            set_text(self.mode, "滨海自由驾驶")
            set_text(self.status, "COASTAL CRUISE")
            self.status.setScale(0.054)
            set_text(self.detail, f"距终点 {max(0, HIGHWAY_LENGTH - state.player.position[1]):.0f} m"
                     if track == "highway" else "自由巡航")
            message = "享受海岸之旅"
        if track == "endless" or race.mode == GameMode.TIME_TRIAL:
            self.status.setScale(0.071)
        value = " · ".join(item for item in (countdown, notice, message) if item)
        if value != self._notice_source:
            self._notice_source = value
            self.status_notice.setText(value)
            wrapped = self.status_notice.textNode.getWordwrappedText()
            self._notice_lines = wrapped.count("\n") + 1
        height = max(0.09, 0.046 * (self._notice_lines + (self._radio_station is not None)) + 0.025)
        if height != self._notice_height:
            self.notice_frame["frameSize"] = (0, 0.88, -height, 0)
            self._notice_height = height

    def select_radio(self, station):
        if station == self._radio_station:
            return
        self._radio_station = station
        for i, label in enumerate(self.radio_labels):
            label.show() if i == station else label.hide()
        self.status_notice.setPos(0.035, -0.096 if station is not None else -0.050)

    def resize(self, aspect):
        if aspect == self._aspect:
            return
        self._aspect = aspect
        self.status_frame.setX(-aspect + 0.075)
        self.notice_frame.setX(-aspect + 0.075)
        self.speed_frame.setX(aspect - 0.075)

    def destroy(self):
        for widget in (self.status_frame, self.notice_frame, self.speed_frame, self.help_frame):
            widget.destroy()
        self.root.removeNode()
