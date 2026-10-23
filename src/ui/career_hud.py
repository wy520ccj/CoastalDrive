"""生涯驾驶的四角信息区；只显示权威快照，不持有比赛或车辆状态。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import (
    CardMaker,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexReader,
    GeomVertexWriter,
    TextNode,
)

from audio.music import STATIONS
from career import CHAPTERS, EVENT_BY_ID
from driving_modes import DrivingMode
from ui import theme
from ui.lab_widgets import rounded_panel

WHITE = (1, 1, 1, 1)
SOFT = (.76, .81, .83, 1)
DARK = (.035, .075, .10, .38)
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
        self.status = self.card('race-status', 330, 162, fade=True)
        self.chapter = self.label(self.status, '', 16, 20, 15, SOFT)
        self.chapter.hide()
        self.title = self.label(self.status, '', 16, 40, 32, bold=True)
        self.primary = self.label(self.status, '', 16, 107, 62, number=True)
        self.timer = self.label(self.status, '', 166, 98, 30, number=True)
        self.bar(self.status, 0, 10, 4, 42, ORANGE)
        self.bar(self.status, 16, 123, 302, 2, (.75, .81, .83, .6))
        self.progress = self.bar(self.status, 16, 123, 302, 2, ORANGE)
        self.detail = self.label(self.status, '', 16, 152, 20)
        self.goal = self.card('race-goal', 330, 40, color=(0, 0, 0, 0))
        self.label(self.goal, '★', 14, 29, 30, GOLD)
        self.goal_text = self.label(self.goal, '', 52, 27, 21)
        self.hints = self.card('driving-hints', 510, 122, fade=True)
        self.bar(self.hints, 10, 12, 4, 24, ORANGE)
        self.tip = self.label(self.hints, '', 28, 31, 21)
        self.tip.textNode.setWordwrap(468/21)
        for x, text in ((16, 'W'), (148, 'S'), (310, 'A'), (346, 'D')):
            key = self.card('key-'+text, 28, 28, parent=self.hints, color=SOFT)
            key.setPos(x, 0, -61)
            rounded_panel(key, 'key-center', (1, 27, -27, -1), (.04, .08, .10, .7), 4)
            self.label(key, text, 6, 21, 19)
        self.label(self.hints, '加速', 54, 83, 18, SOFT)
        self.brake_key = self.label(self.hints, '', 186, 83, 18, SOFT)
        self.label(self.hints, '转向', 385, 83, 18, SOFT)
        self.secondary_keys = self.label(self.hints, '', 16, 114, 16, SOFT)
        self.speed_card = self.card('driving-instruments', 315, 160, color=(0, 0, 0, 0))
        self.speed = self.label(self.speed_card, '000', 10, 91, 78, number=True)
        self.label(self.speed_card, 'km/h', 183, 87, 21)
        self.bar(self.speed_card, 252, 38, 58, 43, ORANGE)
        self.gear = self.label(self.speed_card, '', 261, 70, 27, (.04, .07, .10, 1), number=True)
        self.rpm = self.label(self.speed_card, '', 309, 111, 16, SOFT, right=True)
        self.segments = [self.bar(self.speed_card, 12+i*13.5, 122, 11, 9, SOFT) for i in range(22)]
        self.assists = [self.label(self.speed_card, text, 14+i*72, 153, 17, SOFT)
                        for i, text in enumerate(('ABS', 'TCS', 'ESC'))]
        self.assist_lights = [self.bar(self.speed_card, 14+i*72, 158, 25, 2, SOFT) for i in range(3)]
        shape = rounded_panel(self.root, 'pause-fill', (0, 126, -43, 0), DARK, 5)
        shape.detachNode()
        self.pause = DirectButton(parent=self.root, text='Esc   暂停', text_font=self.regular,
            text_fg=WHITE, text_scale=21, text_pos=(63, -29), geom=shape,
            frameColor=(0, 0, 0, 0), frameSize=(0, 126, -43, 0), relief=DGG.FLAT,
            pressEffect=False, command=action, extraArgs=['pause'])
        self.widgets.append(self.pause)
        self._rpm_active = None
        self._assists = None
        self.root.hide()

    def card(self, name, width, height, *, parent=None, color=DARK, fade=False):
        target = self.root if parent is None else parent
        if fade:
            # 原生顶点渐隐只衬托文字，不再用整块深色面板遮挡环境。
            card = CardMaker(name+'-fill')
            card.setFrame(0, width, -height, 0)
            shape = target.attachNewNode(card.generate())
            geom = shape.node().modifyGeom(0)
            data = GeomVertexData(geom.getVertexData().convertTo(GeomVertexFormat.getV3c4()))
            positions = GeomVertexReader(data, 'vertex')
            colors = GeomVertexWriter(data, 'color')
            while not positions.isAtEnd():
                point = positions.getData3f()
                colors.addData4f(*color[:3], color[3]*(1-point.x/width))
            geom.setVertexData(data)
        else:
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
        item.textNode.setShadow(.025, .025)
        item.textNode.setShadowColor(0, 0, 0, .65)
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
        self.goal.setPos(left, 0, 941/2-206)
        self.hints.setPos(left, 0, -941/2+36+122)
        self.speed_card.setPos(right-315, 0, -941/2+36+160)
        self.pause.setPos(right-126, 0, 941/2-40)

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
        self.primary.setScale(min(62, 144/self.primary.textNode.getWidth()))
        centiseconds = int(result.elapsed*100)
        minutes, seconds = divmod(centiseconds, 6000)
        self.text(self.timer, f'{minutes:02}:{seconds/100:05.2f}')
        self.text(self.goal_text, '三星目标 '+target)
        self.text(self.tip, notice or event.tip)
        brake = '刹车' if driving_mode == DrivingMode.SIMULATION else '刹车·倒车'
        self.text(self.brake_key, brake)
        controls = 'Q 倒挡  E 前进' if driving_mode == DrivingMode.SIMULATION else '辅助驾驶'
        station_name = STATIONS[station].split(' · ', 1)[0] if station is not None else ''
        self.text(self.secondary_keys, 'C 视角   R 复位   '+controls+(' · '+station_name if station_name else ''))
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
