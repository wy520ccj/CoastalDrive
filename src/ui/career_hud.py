"""生涯驾驶轻透四角遥测 HUD（原生顶点渐隐 + 悬浮无盒仪表）；只显示权威快照，不持有比赛或车辆状态。"""

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

WHITE = theme.WHITE
SOFT = (0.78, 0.83, 0.88, 1)
DARK = (0.045, 0.062, 0.088, 0.44)
ORANGE = theme.AMBER
GOLD = theme.AMBER
GREEN = theme.PINE
UNIT = 2/941


class CareerDrivingHUD:
    def __init__(self, parent, body_font, number_font, action):
        self.root = parent.attachNewNode('career-driving-hud')
        self.root.setScale(UNIT)
        self.body_font, self.number_font = body_font, number_font
        self.regular = theme.load_font('fonts/SourceHanSansSC-Regular.otf')
        self.widgets = []

        # ── 左上角轻透渐隐赛事进度（保留原版通透渐隐与悬浮三星目标）──
        self.status = self.card('race-status', 336, 164, fade=True)
        self.bar(self.status, 0, 10, 4, 42, ORANGE)
        self.chapter = self.label(self.status, '', 16, 20, 15, SOFT)
        self.chapter.hide()
        self.title = self.label(self.status, '', 16, 40, 31, bold=True)
        self.primary = self.label(self.status, '', 16, 107, 62, number=True)
        self.timer = self.label(self.status, '', 168, 98, 30, number=True)
        self.bar(self.status, 16, 123, 304, 3, (0.75, 0.81, 0.86, 0.45))
        self.progress = self.bar(self.status, 16, 123, 304, 3, ORANGE)
        self.detail = self.label(self.status, '', 16, 152, 20)

        self.goal = self.card('race-goal', 336, 40, color=(0, 0, 0, 0))
        self.label(self.goal, '★', 14, 29, 29, GOLD)
        self.goal_text = self.label(self.goal, '', 52, 27, 21)

        # ── 左下角轻透渐隐驾驶提示与键帽 ──
        self.hints = self.card('driving-hints', 510, 122, fade=True)
        self.bar(self.hints, 10, 12, 4, 24, ORANGE)
        self.tip = self.label(self.hints, '', 26, 31, 20)
        self.tip.textNode.setWordwrap(468/20)
        for x, text in ((16, 'W'), (148, 'S'), (310, 'A'), (346, 'D')):
            key = self.card('key-'+text, 28, 28, parent=self.hints, color=(0.56, 0.64, 0.74, 0.72))
            key.setPos(x, 0, -61)
            rounded_panel(key, 'key-center', (1, 27, -27, -1), (0.048, 0.064, 0.092, 0.76), 4)
            self.label(key, text, 6, 21, 18)
        self.label(self.hints, '加速', 54, 83, 18, SOFT)
        self.brake_key = self.label(self.hints, '', 186, 83, 18, SOFT)
        self.label(self.hints, '转向', 385, 83, 18, SOFT)
        self.secondary_keys = self.label(self.hints, '', 16, 114, 16, SOFT)

        # ── 右下角无底盒悬浮数字遥测（与滨海设计 40 完全一致，不挡路面）──
        self.speed_card = self.card('driving-instruments', 315, 160, color=(0, 0, 0, 0))
        self.speed = self.label(self.speed_card, '000', 10, 91, 78, number=True)
        self.label(self.speed_card, 'km/h', 183, 87, 21, SOFT)
        rounded_panel(self.speed_card, 'car-gear-pill', (252, 310, -81, -38), ORANGE, 5)
        self.gear = OnscreenText(parent=self.speed_card, text='', font=self.number_font,
                                 fg=theme.INK, pos=(281, -70), scale=27,
                                 align=TextNode.ACenter, mayChange=True)
        self.widgets.append(self.gear)
        self.rpm = self.label(self.speed_card, '', 309, 111, 16, SOFT, number=True, right=True)
        self.segments = [self.bar(self.speed_card, 12+i*13.5, 122, 11, 9, SOFT) for i in range(22)]
        self.assists = [self.label(self.speed_card, text, 14+i*72, 153, 17, SOFT, bold=True)
                        for i, text in enumerate(('ABS', 'TCS', 'ESC'))]
        self.assist_lights = [self.bar(self.speed_card, 14+i*72, 158, 28, 2.5, SOFT) for i in range(3)]

        # ── 右上角轻透黑曜石暂停按钮 ──
        edge = rounded_panel(self.root, 'pause-edge', (-1, 133, -45, 1), (0.34, 0.40, 0.50, 0.55), 7)
        rounded_panel(edge, 'pause-fill', (0, 132, -44, 0), (0.048, 0.064, 0.092, 0.64), 6)
        rounded_panel(edge, 'pause-accent', (6, 9, -34, -10), ORANGE, 1.5)
        edge.detachNode()
        self.pause = DirectButton(parent=self.root, text='Esc   暂停', text_font=self.regular,
            text_fg=WHITE, text_scale=20, text_pos=(69, -29), geom=edge,
            frameColor=(0, 0, 0, 0), frameSize=(0, 132, -44, 0), relief=DGG.FLAT,
            pressEffect=False, command=action, extraArgs=['pause'])
        self.widgets.append(self.pause)
        self._rpm_active = None
        self._assists = None
        self.root.hide()

    def card(self, name, width, height, *, parent=None, color=DARK, fade=False):
        target = self.root if parent is None else parent
        if fade:
            # 原生顶点渐隐只衬托文字，不用整块实心面板遮挡环境。
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
        item.textNode.setShadow(.03, .03)
        item.textNode.setShadowColor(0, 0, 0, .72)
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
        self.status.setPos(left, 0, 941/2-36)
        self.goal.setPos(left, 0, 941/2-208)
        self.hints.setPos(left, 0, -941/2+36+122)
        self.speed_card.setPos(right-315, 0, -941/2+36+160)
        self.pause.setPos(right-132, 0, 941/2-36)

    def update(self, player, result, *, notice, driving_mode, station, road_gold=None, automatic=False):
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
        if automatic:
            goal = '自动试车 · 不计成绩'
        elif road_gold is not None:
            goal = f'金牌 ≤{road_gold.seconds:g}s · ≤{road_gold.consumption:g} L/100km'
        else:
            goal = '三星目标 '+target
        if self.goal_text.getText() != goal:
            self.goal_text.setText(goal)
            self.goal_text.setScale(min(21., 280/self.goal_text.textNode.getWidth()))
        self.text(self.tip, notice or event.tip)
        brake = '刹车' if driving_mode == DrivingMode.SIMULATION else '刹车·倒车'
        self.text(self.brake_key, brake)
        controls = 'Q 倒挡  E 前进' if driving_mode == DrivingMode.SIMULATION else '辅助驾驶'
        station_name = STATIONS[station].split(' · ', 1)[0] if station is not None else ''
        self.text(self.secondary_keys, 'C 视角  R 复位  N 电台  M 静音  '+controls+(' · '+station_name if station_name else ''))
        self.text(self.speed, f'{abs(player.speed)*3.6:03.0f}')
        self.text(self.gear, 'R' if player.gear < 0 else 'N' if player.gear == 0 else f'D{player.gear}')
        self.text(self.rpm, f'{player.rpm:.0f} rpm')
        # 延续原HUD的7000rpm显示标尺，不由表现层改变发动机限制。
        active = round(max(0., min(1., player.rpm/7000))*len(self.segments))
        if active != self._rpm_active:
            for index, segment in enumerate(self.segments):
                if index < active:
                    seg_col = (0.94, 0.36, 0.28, 1) if index >= 19 else ORANGE if index >= 12 else WHITE
                else:
                    seg_col = (0.12, 0.16, 0.22, 0.50)
                segment['frameColor'] = seg_col
            self._rpm_active = active
        assists = ((player.abs_enabled, any(brake.abs_active for brake in player.brake_states)),
            (player.tcs_enabled, player.traction_state.active), (player.esc_enabled, player.stability_state.active))
        if assists != self._assists:
            for label, light, (enabled, intervening) in zip(self.assists, self.assist_lights, assists):
                color = GREEN if intervening else SOFT if enabled else (0.36, 0.42, 0.50, 0.72)
                label.setFg(color)
                light['frameColor'] = color
            self._assists = assists

    def destroy(self):
        for widget in reversed(self.widgets):
            widget.destroy()
        self.root.removeNode()
