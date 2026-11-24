"""驾驶 HUD 只将传入的快照和提示格式化，不维护车辆或比赛状态。"""

from direct.gui.DirectGui import DirectFrame, OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

from audio.music import STATIONS
from braking_lesson import BRAKING_MODES
from career import EVENT_BY_ID
from driving_modes import DrivingMode
from highway_map import HIGHWAY_LENGTH
from overtake_routes import OVERTAKE_ROUTES
from race import GameMode
from slalom_lesson import SLALOM_MODES
from sprint_routes import SPRINT_ROUTES
from ui import theme
from ui.braking_feedback import driving_feedback
from ui.career_hud import CareerDrivingHUD
from ui.coastal_hud import CoastalDrivingHUD
from ui.overtake_feedback import driving_feedback as overtake_driving_feedback
from ui.overtake_feedback import traffic_feedback
from ui.race_feedback import split_feedback
from ui.slalom_feedback import driving_feedback as slalom_driving_feedback
from ui.slalom_feedback import gate_feedback
from ui.sprint_feedback import driving_feedback as sprint_driving_feedback


def set_text(widget, value):
    if widget.getText() != value:
        widget.setText(value)


def driving_help(mode, abs_label=None, tcs_label=None, esc_label=None):
    """输入说明只表达已有模式行为。"""
    direction = " · Q 倒挡 / E 前进挡（选挡后W加油）" if mode == DrivingMode.SIMULATION else ""
    brake = "只刹车" if mode == DrivingMode.SIMULATION else "刹车·倒车"
    electronics = ""
    if abs_label is not None:
        electronics = f" · ABS{abs_label}"
    if tcs_label is not None:
        electronics += f" TCS{tcs_label}"
    if esc_label is not None:
        electronics += f" ESC{esc_label}"
    return (f"驾驶输入：{mode.label}{direction}{electronics}\n"
            f"W / ↑ 油门   S / ↓ {brake}   A D 转向   R 复位   C 视角   N 切台   M 音乐   G 幽灵   Esc 暂停")


class DrivingHUD:
    def __init__(self, parent, loader, body_font, number_font, career_action):
        self._active_rpm = None
        self._notice_source = None
        self._notice_height = None
        self._notice_lines = 1
        self._radio_station = None
        self._aspect = None
        self._timed = None
        self._split_invalidated = None
        self._overtaking = False
        self.root = parent.attachNewNode("driving-hud")
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        dark_card = (0.045, 0.062, 0.088, 0.62)
        soft_fg = (0.78, 0.83, 0.88, 1)
        shadow_cfg = {"shadow": (0, 0, 0, .70), "shadowOffset": (.03, .03)}
        self.status_frame = DirectFrame(
            parent=self.root, frameColor=dark_card,
            frameSize=(0, 0.88, -0.40, 0), pos=(-1.70, 0, 0.91),
        )
        self.mode = OnscreenText(parent=self.status_frame, text="", font=body_font,
                                fg=theme.WHITE, pos=(0.08, -0.071), scale=0.050,
                                align=TextNode.ALeft, mayChange=True, **shadow_cfg)
        DirectFrame(parent=self.status_frame, frameColor=theme.AMBER,
                    frameSize=(0.025, 0.036, -0.092, -0.032))
        DirectFrame(parent=self.status_frame, frameColor=(0.35, 0.42, 0.52, 0.35),
                    frameSize=(0.03, 0.85, -0.122, -0.119))
        self.status = OnscreenText(parent=self.status_frame, text="", font=number_font,
                                  fg=theme.WHITE, pos=(0.055, -0.212), scale=0.071,
                                  align=TextNode.ALeft, mayChange=True, **shadow_cfg)
        self.detail = OnscreenText(parent=self.status_frame, text="", font=body_font,
                                  fg=soft_fg, pos=(0.055, -0.302), scale=0.040,
                                  align=TextNode.ALeft, mayChange=True, **shadow_cfg)
        self.split = OnscreenText(parent=self.status_frame, text="", font=body_font,
                                  fg=theme.STEEL_TEXT, pos=(0.055, -0.422), scale=0.034,
                                  align=TextNode.ALeft, mayChange=True, **shadow_cfg)
        self.split.hide()
        self.goal = OnscreenText(parent=self.status_frame, text="", font=body_font,
            fg=theme.AMBER, pos=(.055, -.535), scale=.031, align=TextNode.ALeft, mayChange=True, **shadow_cfg)
        self.goal.hide()
        self.notice_frame = DirectFrame(parent=self.root, frameColor=(0.045, 0.062, 0.088, 0.72),
                                        frameSize=(0, 0.88, -0.18, 0), pos=(-1.70, 0, 0.50))
        DirectFrame(parent=self.notice_frame, frameColor=theme.AMBER,
                    frameSize=(0.012, 0.020, -0.075, -0.018))
        self.status_notice = OnscreenText(
            parent=self.notice_frame, text="", font=body_font, fg=theme.WHITE,
            pos=(0.038, -0.050), scale=0.033, align=TextNode.ALeft, mayChange=True, **shadow_cfg
        )
        # 提示一次排版即可；逐字测量每个增长前缀会让切台后的驾驶帧卡顿。
        self.status_notice.textNode.setWordwrap(0.80 / 0.033)
        # 三个固定电台标签在加载HUD时生成几何；切台只切换可见性。
        self.radio_labels = tuple(OnscreenText(
            parent=self.notice_frame, text=f"电台：{name}", font=body_font,
            fg=theme.STEEL_TEXT, pos=(0.038, -0.050), scale=0.033,
            align=TextNode.ALeft, mayChange=False, **shadow_cfg
        ) for name in STATIONS)
        for label in self.radio_labels:
            label.hide()
        # 右下角速度仪表与设计 40 一致采用无盒悬浮排版，不再用旧绿框贴图。
        self.speed_frame = DirectFrame(
            parent=self.root, frameColor=(0, 0, 0, 0),
            frameSize=(-0.98, 0, 0, 0.33), pos=(1.70, 0, -0.90),
        )
        self.speed = OnscreenText(parent=self.speed_frame, text="000", font=number_font,
                                 fg=theme.WHITE, pos=(-0.89, 0.117), scale=0.165,
                                 align=TextNode.ALeft, mayChange=True, **shadow_cfg)
        self.course_speed_frame = DirectFrame(parent=self.speed_frame, frameColor=(0.045, 0.062, 0.088, 0.72),
            frameSize=(-.98, 0, .36, .54))
        self.course_speed_label = OnscreenText(parent=self.course_speed_frame, text='', font=body_font,
            fg=theme.WHITE, pos=(-.92, .475), scale=.031, align=TextNode.ALeft, mayChange=True, **shadow_cfg)
        DirectFrame(parent=self.course_speed_frame, frameColor=(.20, .26, .34, 1),
                    frameSize=(-.90, -.08, .405, .425))
        DirectFrame(parent=self.course_speed_frame, frameColor=theme.PINE,
                    frameSize=(-.90+.82*.70, -.90+.82*.80, .395, .435))
        self.course_speed_needle = DirectFrame(parent=self.course_speed_frame, frameColor=theme.AMBER,
                                              frameSize=(-.004, .004, .39, .44))
        self.course_speed_frame.hide()
        OnscreenText(parent=self.speed_frame, text="km/h", font=body_font,
                     fg=soft_fg, pos=(-0.36, 0.125), scale=0.042, **shadow_cfg)
        self.gear_box = DirectFrame(parent=self.speed_frame, frameColor=theme.AMBER,
                                   frameSize=(-0.23, -0.06, 0.140, 0.258))
        self.gear = OnscreenText(parent=self.gear_box, text="D1", font=number_font, fg=theme.INK,
                                pos=(-0.145, 0.175), scale=0.066, align=TextNode.ACenter, mayChange=True)
        self.gear_rpm = OnscreenText(parent=self.speed_frame, text="", font=number_font,
                                    fg=soft_fg, pos=(-0.065, 0.077), scale=0.030,
                                    align=TextNode.ARight, mayChange=True, **shadow_cfg)
        self.rpm_segments = [DirectFrame(parent=self.speed_frame, frameColor=(0.12, 0.16, 0.22, 0.50),
                                        frameSize=(-0.89 + i * 0.039, -0.86 + i * 0.039, 0.033, 0.064))
                             for i in range(21)]
        self.help_frame = DirectFrame(parent=self.root, frameColor=(0.045, 0.062, 0.088, 0.46),
                                      frameSize=(-0.75, 0.75, -0.045, 0.045), pos=(0, 0, -0.94))
        self.help = OnscreenText(parent=self.help_frame,
                                text="W / ↑ 油门    S / ↓ 刹车·倒车    A D 转向    R 复位    C 视角    N 切台    M 音乐    Esc 暂停",
                                font=body_font, fg=soft_fg, pos=(0, 0.009), scale=0.027, mayChange=True, **shadow_cfg)
        self.career = CareerDrivingHUD(self.root, body_font, number_font, career_action)
        self.coastal = CoastalDrivingHUD(self.root, body_font, number_font, self.career.regular)
        self._career_active = False
        self._coastal_active = False

    def update(self, state, race, highway, *, track, countdown, notice,
               driving_mode=DrivingMode.GAME, automatic=False, automatic_splits=(), career_gold=None):
        budget_active = highway.engineering is not None and highway.engineering.assessment == 'road'
        career_active = track == 'endless' and highway.career is not None and not budget_active
        coastal_active = track == 'coastal' or budget_active
        if (career_active, coastal_active) != (self._career_active, self._coastal_active):
            self._career_active, self._coastal_active = career_active, coastal_active
            for widget in (self.status_frame, self.notice_frame, self.speed_frame, self.help_frame):
                widget.hide() if career_active or coastal_active else widget.show()
            self.career.root.show() if career_active else self.career.root.hide()
            self.coastal.root.show() if coastal_active else self.coastal.root.hide()
        if career_active:
            self.career.update(state.player, highway.career, notice=notice,
                driving_mode=driving_mode, station=self._radio_station, road_gold=career_gold,
                automatic=automatic)
            return
        if coastal_active:
            if budget_active:
                feedback, warning = '', False
                circuit = track == 'coastal' and race.mode == GameMode.TIME_TRIAL
                invalid_reason = race.invalid_reason if circuit and race.invalidated else ''
                if highway.overtake is not None:
                    reading, warning = traffic_feedback(highway.overtake)
                    required = OVERTAKE_ROUTES[race.mode].passes
                    passes = highway.overtake.passes
                    goal = ' · 安全驶至终点' if passes >= required else ''
                    feedback = f'安全超车 {passes}/{required}{goal}\n{reading}'
                elif highway.sprint is not None and SPRINT_ROUTES[race.mode].speed_zone is not None:
                    _, feedback = sprint_driving_feedback(highway.sprint)
                    feedback = feedback.split('\n')[-1]
                elif highway.career is not None:
                    feedback = EVENT_BY_ID[highway.career.event_id].tip
                elif circuit and not race.invalidated and race.checkpoints == highway.engineering.gate_count-1:
                    feedback = '检查点已齐，驶过终点线'
                self.coastal.update_challenge(state.player, highway.engineering, countdown=countdown,
                    notice='\n'.join(value for value in (notice, feedback) if value),
                    driving_mode=driving_mode, station=self._radio_station, warning=warning,
                    split_label='分段' if circuit or race.mode == GameMode.DISTANCE_CHALLENGE or highway.overtake is not None
                    else '道路门',
                    invalid_reason=invalid_reason, automatic=automatic, automatic_splits=automatic_splits)
                return
            self.coastal.update(state.player, race, countdown=countdown, notice=notice,
                                driving_mode=driving_mode, station=self._radio_station)
            return
        player = state.player
        timed = ((track != "endless" and race.mode == GameMode.TIME_TRIAL)
                 or (track == "endless" and (race.mode in (*SLALOM_MODES, *OVERTAKE_ROUTES)
                                             or highway.sprint is not None)))
        overtaking = track == 'endless' and race.mode in OVERTAKE_ROUTES
        if timed != self._timed or overtaking != self._overtaking:
            self._timed = timed
            self._overtaking = overtaking
            self.split.show() if timed else self.split.hide()
            self.goal.show() if overtaking else self.goal.hide()
            self.status_frame["frameSize"] = (0, .88, -.68 if overtaking else -.54 if timed else -.40, 0)
            self.notice_frame.setZ(.22 if overtaking else .36 if timed else .50)
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
        if race.mode == GameMode.FAST_SLALOM:
            kph = state.player.velocity[1]*3.6
            action = '继续加速' if kph < 70 else '松油门 / 轻刹' if kph > 80 else '速度合适'
            set_text(self.course_speed_label, f'目标 70–80 km/h · {action}')
            self.course_speed_needle.setX(-.90+.82*max(0., min(1., kph/100)))
            self.course_speed_frame.show()
        else:
            self.course_speed_frame.hide()
        set_text(self.gear, "R" if state.player.gear < 0 else "N" if state.player.gear == 0 else f"D{state.player.gear}")
        set_text(self.gear_rpm, f"{state.player.rpm:4.0f} rpm")
        # 色条直接表示当前发动机转速，末端标尺 7000 rpm；不改变物理转速。
        active = round(min(1, max(0, state.player.rpm / 7000)) * len(self.rpm_segments))
        if active != self._active_rpm:
            for i, segment in enumerate(self.rpm_segments):
                if i < active:
                    color = (0.94, 0.36, 0.28, 1) if i >= 18 else theme.AMBER if i >= 11 else theme.WHITE
                else:
                    color = (0.12, 0.16, 0.22, 0.50)
                segment["frameColor"] = color
            self._active_rpm = active
        if track == "endless":
            braking = race.mode in BRAKING_MODES
            slalom = race.mode in SLALOM_MODES
            set_text(self.mode, '过门练习' if race.mode == GameMode.SLALOM_PRACTICE else "短距制动验车" if race.mode == GameMode.SHORT_BRAKING else "高速验车" if race.mode == GameMode.FAST_SLALOM else "连续过门" if slalom else "定点刹停" if braking else "5公里无碰撞挑战" if highway.challenge else "无限高速")
            set_text(self.status, f"{highway.elapsed:07.2f} s")
            distance = f"{highway.distance:.0f} / {highway.target:.0f} m" if highway.challenge else f"{highway.distance / 1000:.2f} km"
            set_text(self.detail, f"距离 {distance}\n碰撞 {highway.collisions} 次")
            message = "无碰撞行驶中" if highway.collisions == 0 else f"碰撞 {highway.collisions} 次"
            if highway.career is not None:
                result = highway.career
                event = EVENT_BY_ID[result.event_id]
                set_text(self.mode, event.name)
                detail = (f'停车区 {event.distance:g}米 · 距中心 {abs(result.position-event.distance):.0f}米'
                          if event.kind == 'parking' else
                          f'通过 {sum(result.passed)} / 5 门 · 漏门可以继续' if event.kind == 'slalom' else
                          f'距终点 {max(0, event.distance-result.position):.0f} 米')
                set_text(self.detail, detail)
                message = event.tip
            elif highway.overtake is not None:
                route = OVERTAKE_ROUTES[race.mode]
                set_text(self.mode, route.title)
                detail, feedback = overtake_driving_feedback(highway.overtake)
                set_text(self.detail, detail)
                set_text(self.split, feedback)
                self.split.setFg(theme.STEEL_TEXT)
                reading, warning = traffic_feedback(highway.overtake)
                set_text(self.goal, reading)
                self.goal.setFg((1, .48, .34, 1) if warning else theme.AMBER)
                message = ("弯前看清车流，留距择道；超车达标后仍需安全到终点" if route.finish_at_end else
                           "留出空间再择道；超出整车10米才计数 · 金85 / 银110 / 铜150秒")
            elif braking:
                detail, message = driving_feedback(highway.braking, short=race.mode == GameMode.SHORT_BRAKING)
                set_text(self.detail, detail)
            elif slalom:
                detail, message = slalom_driving_feedback(highway.slalom, fast=race.mode == GameMode.FAST_SLALOM)
                set_text(self.detail, detail)
                set_text(self.split, gate_feedback(highway.slalom))
                self.split.setFg(theme.STEEL_TEXT)
                self._split_invalidated = None
            elif highway.sprint is not None:
                set_text(self.mode, SPRINT_ROUTES[race.mode].name)
                detail, feedback = sprint_driving_feedback(highway.sprint)
                set_text(self.detail, detail)
                set_text(self.split, feedback)
                self.split.setFg(theme.STEEL_TEXT)
                message = ("提前刹车，限速带全段保持速度；出带再加速"
                           if SPRINT_ROUTES[race.mode].speed_zone is not None else "看远处弯势；坡顶确认方向，弯前松油或刹车")
        elif race.mode == GameMode.TIME_TRIAL:
            set_text(self.mode, "计时挑战")
            set_text(self.status, f"{race.elapsed:07.3f} s")
            target = "终点" if race.checkpoints == 4 else f"检查点 {race.next_checkpoint}"
            set_text(self.detail, f"检查点  {race.checkpoints} / 4\n下一目标  {target}")
            set_text(self.split, split_feedback(race))
            if race.invalidated != self._split_invalidated:
                self._split_invalidated = race.invalidated
                self.split.setFg((1, .48, .34, 1) if race.invalidated else theme.STEEL_TEXT)
            message = f"圈速无效：{race.invalid_reason}" if race.invalidated else "本圈有效"
            if race.score_notice:
                message += " · "+race.score_notice
            if race.ghost_notice:
                message += " · "+race.ghost_notice
        else:
            set_text(self.mode, "滨海自由驾驶")
            set_text(self.status, "COASTAL CRUISE")
            self.status.setScale(0.054)
            set_text(self.detail, f"距终点 {max(0, HIGHWAY_LENGTH - state.player.position[1]):.0f} m"
                     if track == "highway" else "自由巡航")
            message = "享受海岸之旅"
        if track == "endless" or race.mode == GameMode.TIME_TRIAL:
            self.status.setScale(0.071)
        value = " · ".join(item for item in (countdown, '自动试车' if automatic else '', notice, message) if item)
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
        self.career.resize(aspect)
        self.coastal.resize(aspect)

    def destroy(self):
        self.career.destroy()
        self.coastal.destroy()
        for widget in (self.status_frame, self.notice_frame, self.speed_frame, self.help_frame):
            widget.destroy()
        self.root.removeNode()
