"""生涯驾驶的四角信息区；只显示权威快照，不持有比赛或车辆状态。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from audio.music import STATIONS
from career import CHAPTERS, EVENT_BY_ID
from driving_modes import DrivingMode
from ui import theme
from ui.lab_widgets import rounded_panel

WHITE = (1, 1, 1, 1)
SOFT = (.76, .81, .83, 1)
DARK = (.035, .075, .10, .88)
ORANGE = (1, .31, .12, 1)
GOLD = (1, .77, .24, 1)
UNIT = 2/941


class CareerDrivingHUD:
    def __init__(self, parent, body_font, number_font, action):
        self.root = parent.attachNewNode('career-driving-hud')
        self.root.setScale(UNIT)
        self.body_font, self.number_font = body_font, number_font
        self.regular = theme.load_font('fonts/SourceHanSansSC-Regular.otf')
        self.widgets = []
        self.status = self.card('race-status', 482, 272)
        self.chapter = self.label(self.status, '', 46, 40, 21, SOFT)
        self.title = self.label(self.status, '', 44, 94, 40, bold=True)
        self.primary = self.label(self.status, '', 44, 183, 80, number=True)
        self.timer = self.label(self.status, '', 298, 150, 36, number=True)
        self.label(self.status, '用时', 300, 179, 20, SOFT)
        self.bar(self.status, 2, 9, 5, 78, ORANGE)
        self.bar(self.status, 38, 205, 412, 7, (.36, .43, .46, 1))
        self.progress = self.bar(self.status, 38, 205, 412, 7, ORANGE)
        self.detail = self.label(self.status, '', 38, 248, 22)
        self.goal = self.card('race-goal', 484, 65)
        self.label(self.goal, '★', 22, 47, 40, GOLD)
        self.goal_text = self.label(self.goal, '', 76, 43, 24)
        self.hints = self.card('driving-hints', 531, 174)
        self.bar(self.hints, 25, 20, 5, 34, ORANGE)
        self.tip = self.label(self.hints, '', 60, 48, 24)
        self.tip.textNode.setWordwrap(446/24)
        for x, y, text in ((42, 82, 'W'), (176, 82, 'S'), (350, 82, 'A'), (390, 82, 'D'),
                           (42, 124, 'C'), (176, 124, 'R')):
            key = self.card('key-'+text, 34, 34, parent=self.hints, color=SOFT)
            key.setPos(x, 0, -y)
            rounded_panel(key, 'key-center', (1, 33, -33, -1), (.04, .08, .10, 1), 4)
            self.label(key, text, 7, 25, 22)
        self.label(self.hints, '加速', 90, 107, 19, SOFT)
        self.brake_key = self.label(self.hints, '', 224, 107, 19, SOFT)
        self.label(self.hints, '转向', 436, 107, 19, SOFT)
        self.label(self.hints, '视角', 90, 149, 19, SOFT)
        self.label(self.hints, '复位', 224, 149, 19, SOFT)
        self.secondary_keys = self.label(self.hints, '', 333, 149, 18, SOFT)
        self.speed_card = self.card('driving-instruments', 496, 219)
        self.speed = self.label(self.speed_card, '000', 30, 94, 83, number=True)
        self.label(self.speed_card, 'km/h', 217, 91, 23)
        self.bar(self.speed_card, 388, 22, 86, 60, ORANGE)
        self.gear = self.label(self.speed_card, '', 405, 65, 32, (.04, .07, .10, 1), number=True)
        self.rpm = self.label(self.speed_card, '', 468, 113, 18, SOFT, right=True)
        self.segments = [self.bar(self.speed_card, 32+i*20, 125, 18, 14, SOFT) for i in range(22)]
        self.bar(self.speed_card, 22, 156, 452, 1, (.4, .46, .49, .65))
        self.assists = [self.label(self.speed_card, text, 35+i*87, 186, 19, SOFT)
                        for i, text in enumerate(('ABS', 'TCS', 'ESC'))]
        self.assist_lights = [self.bar(self.speed_card, 35+i*87, 196, 29, 4, SOFT) for i in range(3)]
        shape = rounded_panel(self.root, 'pause-fill', (0, 189, -61, 0), DARK, 8)
        shape.detachNode()
        self.pause = DirectButton(parent=self.root, text='Esc   暂停', text_font=self.regular,
            text_fg=WHITE, text_scale=25, text_pos=(94.5, -40), geom=shape,
            frameColor=(0, 0, 0, 0), frameSize=(0, 189, -61, 0), relief=DGG.FLAT,
            pressEffect=False, command=action, extraArgs=['pause'])
        self.widgets.append(self.pause)
        self._rpm_active = None
        self._assists = None
        self.root.hide()

    def card(self, name, width, height, *, parent=None, color=DARK):
        target = self.root if parent is None else parent
        shape = rounded_panel(target, name+'-fill', (0, width, -height, 0), color, 8)
        shape.detachNode()
        frame = DirectFrame(parent=target, geom=shape, frameColor=(0, 0, 0, 0),
            frameSize=(0, width, -height, 0), relief=DGG.FLAT)
        self.widgets.append(frame)
        return frame

    def label(self, parent, text, x, y, size, color=WHITE, *, number=False, right=False, bold=False):
        item = OnscreenText(parent=parent, text=text,
            font=self.number_font if number else self.body_font if bold else self.regular, fg=color, pos=(x, -y),
            scale=size, align=TextNode.ARight if right else TextNode.ALeft, mayChange=True)
        self.widgets.append(item)
        return item

    def bar(self, parent, x, y, width, height, color):
        item = DirectFrame(parent=parent, frameSize=(0, width, -height, 0),
            pos=(x, 0, -y), frameColor=color, relief=DGG.FLAT)
        self.widgets.append(item)
        return item

    def text(self, widget, value):
        if widget.getText() != value:
            widget.setText(value)

    def resize(self, aspect):
        left, right = -aspect/UNIT+36, aspect/UNIT-36
        self.status.setPos(left, 0, 941/2-40)
        self.goal.setPos(left, 0, 941/2-322)
        self.hints.setPos(left, 0, -941/2+36+174)
        self.speed_card.setPos(right-496, 0, -941/2+36+219)
        self.pause.setPos(right-189, 0, 941/2-40)

    def update(self, player, result, *, notice, driving_mode, station):
        event = EVENT_BY_ID[result.event_id]
        self.text(self.chapter, f'{event.chapter+1:02} / {CHAPTERS[event.chapter]}')
        self.text(self.title, event.name)
        fraction = max(0., min(1., result.position/event.distance))
        self.progress.setScale(fraction, 1, 1)
        if event.kind == 'slalom':
            self.text(self.primary, f'{sum(result.passed)}/{len(event.gates)}')
            remaining = event.gates[len(result.passed)][0]-result.position if len(result.passed) < len(event.gates) else 0
            self.text(self.detail, f'下一道门 {max(0, remaining):.0f} 米 · 漏门可继续')
            target = f'全过{len(event.gates)}门 · {event.gold:g}秒'
        elif event.kind == 'parking':
            error = abs(result.position-event.distance)
            self.text(self.primary, f'{error:.1f} m' if error < 10 else f'{error:.0f} m')
            self.text(self.detail, f'距停车区中心 · 停稳 {result.stopping_ticks/120:.1f} 秒')
            target = f'距中心不超过 {event.gold:g} 米'
        else:
            self.text(self.primary, f'{fraction*100:.0f}%')
            self.text(self.detail, f'距终点 {max(0, event.distance-result.position):.0f} 米')
            target = f'{event.gold:g} 秒'
        centiseconds = int(result.elapsed*100)
        minutes, seconds = divmod(centiseconds, 6000)
        self.text(self.timer, f'{minutes:02}:{seconds/100:05.2f}')
        self.text(self.goal_text, '三星目标 '+target)
        self.text(self.tip, notice or event.tip)
        brake = '刹车' if driving_mode == DrivingMode.SIMULATION else '刹车·倒车'
        self.text(self.brake_key, brake)
        controls = 'Q 倒挡  E 前进' if driving_mode == DrivingMode.SIMULATION else '辅助驾驶'
        station_name = STATIONS[station].split(' · ', 1)[0] if station is not None else ''
        self.text(self.secondary_keys, controls+(' · '+station_name if station_name else ''))
        self.text(self.speed, f'{abs(player.speed)*3.6:03.0f}')
        self.text(self.gear, 'R' if player.gear < 0 else 'N' if player.gear == 0 else f'D{player.gear}')
        self.text(self.rpm, f'{player.rpm:.0f} rpm')
        # 延续原HUD的7000rpm显示标尺，不由表现层改变发动机限制。
        active = round(max(0., min(1., player.rpm/7000))*len(self.segments))
        if active != self._rpm_active:
            for index, segment in enumerate(self.segments):
                segment['frameColor'] = ((.94, .13, .10, 1) if index >= 19 else ORANGE) if index < active else (.25, .31, .34, 1)
            self._rpm_active = active
        assists = ((player.abs_enabled, any(brake.abs_active for brake in player.brake_states)),
            (player.tcs_enabled, player.traction_state.active), (player.esc_enabled, player.stability_state.active))
        if assists != self._assists:
            for label, light, (enabled, intervening) in zip(self.assists, self.assist_lights, assists):
                color = (.37, .88, .64, 1) if intervening else SOFT if enabled else (.38, .44, .47, 1)
                label.setFg(color)
                light['frameColor'] = color
            self._assists = assists

    def destroy(self):
        for widget in reversed(self.widgets):
            widget.destroy()
        self.root.removeNode()
