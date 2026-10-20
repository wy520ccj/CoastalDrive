"""驾驶选择页的卡片和课题图解；复用应用已有动作与规则文字。"""

import math

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, OnscreenText
from panda3d.core import LineSegs, TextNode

from ui import theme
from ui.lab_widgets import button_textures, rounded_panel


class DrivingCards:
    def __init__(self, panel, font, buttons):
        self.panel, self.font, self.buttons = panel, font, buttons
        self.root = panel.attachNewNode('driving-cards')
        self.content = self.root.attachNewNode('content')
        self.active = False
        self.labels, self.primary = [], set()

    def hide(self):
        for label in self.labels:
            label.destroy()
        self.labels.clear()
        self.content.removeNode()
        self.content = self.root.attachNewNode('content')
        self.root.hide()
        self.active = False

    def begin(self, app, title, subtitle):
        self.active, self.primary = True, set()
        self.root.show()
        app.panel['frameSize'] = (-1.70, 1.70, -.89, .86)
        app.panel['frameTexture'] = None
        app.panel['frameColor'] = theme.PAPER_LIGHT
        app.panel_accent.hide()
        app.panel_title.setText(title)
        app.panel_title['align'] = TextNode.ALeft
        app.panel_title.setPos(-1.50, .68)
        app.panel_title.setScale(.075)
        app.panel_title.textNode.setSlant(0.)
        app.panel_note.hide()
        app.panel_detail.hide()
        self.text(subtitle, -1.50, .555, .037, theme.MUTED)
        self.text('COASTAL DRIVE', .84, .74, .036, theme.SEA)
        DirectFrame(parent=self.content, frameColor=theme.ORANGE, frameSize=(-1.50, -1.38, .785, .797), state=DGG.DISABLED)
        self.text('↑ ↓ 选择 · Enter确认 · Esc返回', -1.50, -.79, .031, theme.MUTED)
        self.resize(app.getAspectRatio())

    def resize(self, aspect):
        if self.active:
            self.panel.setScale(min(1., aspect/(16/9)))

    def text(self, value, x, z, scale=.035, color=theme.INK):
        label = OnscreenText(parent=self.content, text=value, font=self.font, fg=color,
            align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)
        self.labels.append(label)
        return label

    def line(self, points, color=theme.SEA, thickness=2.5):
        lines = LineSegs()
        lines.setColor(*color)
        lines.setThickness(thickness)
        lines.moveTo(points[0][0], 0, points[0][1])
        for x, z in points[1:]:
            lines.drawTo(x, 0, z)
        self.content.attachNewNode(lines.create())

    def route(self, x, z, width, kind):
        # 只表达弯道/坡度/节奏；实际道路仍由原场景负责。
        points = []
        for index in range(41):
            t = index/40
            bend = (math.sin(t*math.pi*3)*.035 if kind in ('bend', 'slalom') else
                    math.sin(t*math.pi*2)*.035 if kind in ('hill', 'valley') else 0.)
            points.append((x-width/2+t*width, z+bend))
        self.line([(px, pz-.018) for px, pz in points], theme.SEA, 2.)
        self.line([(px, pz+.018) for px, pz in points], theme.SEA, 2.)
        if kind == 'traffic':
            for offset in (-.20, .12):
                DirectFrame(parent=self.content, frameColor=theme.ORANGE,
                    frameSize=(-.034, .034, -.016, .016), pos=(x+offset, 0, z), state=DGG.DISABLED)
        if kind == 'valley':
            self.line([(x-.10, z-.06), (x+.10, z-.06)], theme.ORANGE, 4.)
        if kind == 'tour':
            for offset in (-.24, 0., .24):
                self.line([(x+offset, z-.035), (x+offset, z+.035)], theme.ORANGE, 3.)

    def button(self, index, x, z, width, height, *, primary=False, compact=False):
        button = self.buttons[index]
        button.setPos(x, 0, z)
        button['frameSize'] = (-width/2, width/2, -height/2, height/2)
        button['text_scale'] = .040 if compact else .043
        button['text_align'] = TextNode.ALeft if not compact else TextNode.ACenter
        button['text_pos'] = (-width/2+.07, height/2-.085) if not compact else (0, -.014)
        if primary:
            self.primary.add(index)
        return button

    def select(self, index):
        for i, button in enumerate(self.buttons):
            states = button_textures(i in self.primary)
            button['frameTexture'] = (states[2], states[1], states[2], states[3]) if i == index else states
            button['text_fg'] = theme.INK

    def routes(self, app, goals):
        self.begin(app, '挑一条路，出发', '封闭短途 / 安全超车 / 三站巡回 · 使用当前驾驶车辆')
        rows = (
            ('bend', '1.8公里 · 连贯通过四门', goals[0]),
            ('hill', '1.4公里 · 起伏路面冲刺', goals[1]),
            ('valley', '250m ≥60 km/h\n400–650m · 35–50 km/h', goals[2]),
            ('traffic', '2公里 · 安全超越2辆', '并行 ≥1m · 前后 ≥10m'),
            ('hill', '2.4公里 · 安全超越3辆', '金110 / 银140 / 铜180秒'),
            ('tour', '山谷 → 连弯 → 弯坡车流', '每站至少铜牌 · 断点续跑'))
        for index, (kind, description, target) in enumerate(rows):
            x, z = (-1.08, 0., 1.08)[index % 3], .22 if index < 3 else -.31
            self.button(index, x, z, 1.00, .46)
            self.route(x, z+.045, .80, kind)
            self.text(description, x-.43, z-.055, .031, theme.MUTED)
            self.text(target, x-.43, z-.155, .030, theme.SEA)
        self.text('路线示意 · 前三项无车流，上限180秒；碰撞 / 越界 / 复位结束挑战', -1.50, -.65, .031, theme.MUTED)
        self.button(6, 1.13, -.78, .86, .10, compact=True)
        self.select(app.panel_selection)

    def highway(self, app):
        self.begin(app, '高速与驾驶课题', '自在巡航，或用一个短目标检验你的驾驶与改装')
        for index, x in enumerate((-.79, .79)):
            self.button(index, x, .40, 1.48, .12, compact=True)
        for index, x, kind, description in (
                (2, -.79, 'bend', '没有计时压力 · 按选择的道路与车流出发'),
                (3, .79, 'traffic', '5公里无碰撞 · 可以倒车调整，复位结束')):
            self.button(index, x, .075, 1.48, .40)
            self.route(x, .09, 1.20, kind)
            self.text(description, x-.66, -.055, .030, theme.MUTED)
        for index, x, title, description in (
                (4, -1.08, '制动与停车', '定点精度 / 短距制动 / 分配配方'),
                (5, 0., '转向与过门', '连续六门 / 高速验车 / 前胎配方'),
                (6, 1.08, '路线与巡回', '山谷 / 连弯 / 弯坡车流 / 三站')):
            self.button(index, x, -.39, 1.00, .30)
            self.text(title, x-.43, -.41, .037, theme.SEA)
            self.text(description, x-.43, -.49, .026, theme.MUTED)
        self.text('选中上方道路 / 车流时，左右键调整；驾驶课题使用各自固定场地。', -1.50, -.65, .031, theme.MUTED)
        self.button(7, 1.13, -.78, .86, .10, compact=True)
        self.select(app.panel_selection)

    def lesson(self, app, *, braking, fast):
        title = ('短距制动验车' if fast else '定点刹停') if braking else ('高速验车' if fast else '连续过门')
        self.begin(app, title, '使用当前车辆 · 封闭场地无车流 · 改装后可以直接同题再试')
        rounded_panel(self.content, 'course-diagram', (-1.50, .48, -.30, .43), theme.PAPER)
        rounded_panel(self.content, 'course-targets', (.56, 1.50, -.30, .43), theme.PAPER)
        self.text('场地示意', -1.38, .32, .035, theme.MUTED)
        if braking:
            self.line([(-1.32, .02), (.28, .02)], theme.SEA, 5.)
            for x, label in ((-1.22, '起步'), (-.32, '100m测速门'), (.20, '142m' if fast else '170m')):
                self.line([(x, -.04), (x, .09)], theme.ORANGE, 3.)
                self.text(label, x-.12, -.14, .032)
            self.text('80–85 km/h' if fast else '≥80 km/h', -.49, .16, .046, theme.SEA)
            self.text('过门后尽快停稳' if fast else '瞄准170米线停车', -1.35, -.25, .037)
            target = '最大前进距离' if fast else '停车绝对误差'
            medals = ('金 ≤33m', '银 ≤36m', '铜 ≤42m') if fast else ('金 ≤2m', '银 ≤5m', '铜 ≤10m')
            rule = '松开刹车停稳1秒 · 30秒内完成\n'+('直行带±1m · 偏角≤5° · 不可倒车' if fast else
                                                        '允许倒车调整 · 碰撞/复位结束')
        else:
            self.route(-.51, .04, 1.60, 'slalom')
            for index in range(6):
                x = -1.23+index*.29
                z = .04+math.sin(index*math.pi/2)*.035
                self.line([(x, z-.055), (x, z+.055)], theme.ORANGE, 3.)
                self.text(str(index+1), x-.015, -.10, .034)
            self.text('全段 70–80 km/h' if fast else '入门 ≥40 km/h', -1.35, .17, .045, theme.SEA)
            self.text('80m入门 → 120–320m六门', -1.35, -.25, .037)
            target = '有效六门总用时'
            medals = ('金 ≤11.5s', '银 ≤12.5s', '铜 ≤14s') if fast else ('金 ≤15s', '银 ≤18s', '铜 ≤24s')
            rule = '整车依次过门 · 门宽4米\n漏门/碰撞/越界/复位结束 · 上限40秒'
        self.text(target, .65, .32, .038, theme.MUTED)
        for z, label, color in zip((.18, .02, -.14), medals, (theme.ORANGE, theme.SEA, theme.INK), strict=True):
            self.text(label, .66, z, .055, color)
        self.text(rule, -1.50, -.39, .035, theme.MUTED)
        self.button(0, -.96, -.69, 1.08, .14, primary=True, compact=True)
        self.button(2, .30, -.69, 1.28, .14, compact=True)
        self.button(1, -.77, -.12-.41, 1.46, .10, compact=True)
        self.button(3, 1.25, -.69, .50, .14, compact=True)
        self.select(app.panel_selection)

    def overtake(self, app, route):
        self.begin(app, route.title, f'{route.distance/1000:g}公里 · 原生12车 · 使用当前驾驶车辆')
        rounded_panel(self.content, 'gap-diagram', (-1.50, .48, -.30, .43), theme.PAPER)
        rounded_panel(self.content, 'pass-targets', (.56, 1.50, -.30, .43), theme.PAPER)
        self.text('换道与净距示意', -1.38, .32, .035, theme.MUTED)
        for z in (.05, .22):
            self.line([(-1.35, z), (.30, z)], theme.SEA, 1.)
        for x, z, color in ((-.84, .13, theme.SEA), (-.43, .34, theme.ORANGE)):
            rounded_panel(self.content, 'car-footprint', (x-.13, x+.13, z-.04, z+.04), color, .015)
        self.line([(-1.20, .13), (-.98, .13), (-.79, .34), (-.60, .34)], theme.ORANGE, 3.)
        self.text('并行侧距 ≥1m', -1.35, -.09, .043)
        self.text('跟车 / 切回前后净距 ≥10m', -1.35, -.24, .039, theme.SEA)
        self.text(f'安全超越 {route.passes} 辆', .65, .32, .043)
        for z, (medal, seconds), color in zip((.18, .02, -.14), route.targets,
                                             (theme.ORANGE, theme.SEA, theme.INK), strict=True):
            self.text(f'{medal} ≤{seconds:g}s', .66, z, .055, color)
        self.text(('超车达标后，仍须安全跑到终点。' if route.finish_at_end else '达标即完成；先观察，再留距换道。')+
                  '\n从后方接近并整车领先10米才计数；贴身/碰撞/越界/逆向/复位结束。',
                  -1.50, -.42, .035, theme.MUTED)
        self.button(0, -.94, -.69, 1.12, .14, primary=True, compact=True)
        self.button(1, 1.01, -.69, 1.00, .14, compact=True)
        self.select(app.panel_selection)
