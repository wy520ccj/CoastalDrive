"""落日黑曜石与琥珀金风格高速与路线课题卡片矩阵。"""

import math

from direct.gui.DirectGui import OnscreenText
from panda3d.core import LineSegs, TextNode, TransparencyAttrib

from ui import atelier, theme
from ui.lab_widgets import gradient_panel, rounded_panel


class DrivingCards:
    def __init__(self, panel, font, buttons):
        self.panel, self.font, self.buttons = panel, font, buttons
        self.root = panel.attachNewNode('driving-cards')
        self.content = self.root.attachNewNode('content')
        self.active = False
        self.dark = False
        self.labels, self.primary = [], set()
        self.frames, self.garage_knobs = [], []
        self.garage_page = self.garage_app = self.garage_aspect = None
        self.summary_order, self.summary_values = (), {}

    def hide(self):
        if self.garage_page is not None:
            view = self.garage_app.workshop_vehicle
            if view.frame is not None and view.frame.getParent() == self.content:
                view.hide()
            for button in self.buttons:
                button['geom'] = None
                button['text_font'] = self.font
        self.garage_page = None
        self.summary_order, self.summary_values = (), {}
        for knob in self.garage_knobs:
            knob.removeNode()
        self.garage_knobs.clear()
        for frame in self.frames:
            frame.destroy()
        self.frames.clear()
        for button in self.buttons:
            button.reparentTo(self.panel)
        for label in self.labels:
            label.destroy()
        self.labels.clear()
        self.content.removeNode()
        self.content = self.root.attachNewNode('content')
        self.root.hide()
        self.active = False

    def begin(self, app, title, subtitle, *, dark=True):
        self.dark = True
        self.active, self.primary = True, set()
        self.root.show()
        app.panel['frameSize'] = (-1.78, 1.78, -1.0, 1.0)
        app.panel['frameTexture'] = None
        app.panel['frameColor'] = theme.SLATE_BG
        app.panel_title['fg'] = theme.WHITE
        app.panel_accent.hide()
        app.panel_title.setText(title)
        app.panel_title['align'] = TextNode.ALeft
        app.panel_title.setPos(-1.50, .68)
        app.panel_title.setScale(.075)
        app.panel_title.textNode.setSlant(0.)
        app.panel_title.hide()
        app.panel_note.hide()
        app.panel_detail.hide()

        # 落日工坊柔暗氛围底 + 拉丝黑曜石顶底通栏（与生涯赛事板视觉完全统一）。
        self.app_loader = app.loader
        self.frames.append(atelier.picture(
            self.content, app.loader, atelier.SUNSET_GARAGE_BG,
            (-2.1, 2.1, -1.02, 1.02), color=(0.24, 0.22, 0.25, 1), crop=True))
        gradient_panel(self.content, 'cards-bg', (-2.6, 2.6, -2., 2.),
                       (0.045, 0.055, 0.078, 0.90), (0.045, 0.055, 0.078, 0.72))
        self.frames.append(atelier.picture(self.content, app.loader, 'atelier/bar-top.png', (-2.2, 2.2, .815, 1.02)))
        self.frames.append(atelier.picture(self.content, app.loader, 'atelier/footer-surface.png', (-2.2, 2.2, -1.02, -.70)))

        self.frames.append(atelier.wordmark(self.content, app.loader, (-1.52, -.98, .855, .958)))
        rounded_panel(self.content, 'cards-title-bar', (-1.50, -1.490, .665, .745), theme.AMBER, .004)
        self.text(title, -1.465, .675, .070, theme.WHITE)
        self.text(subtitle, -1.50, .576, .035, theme.DARK_SUB)
        self.text('↑ ↓ ← → 选择   ·   Enter 确认   ·   Esc 返回', -1.50, -.930, .028, theme.DARK_SUB)
        self.card_borders = {}
        self.resize(app.getAspectRatio())

    def resize(self, aspect):
        if self.garage_page is not None:
            if aspect != self.garage_aspect:
                selected = self.garage_app.panel_selection
                self.garage_app._shown_phase = None
                self.garage_app.refresh_panel()
                self.garage_app.select_panel_option(selected)
            return
        if self.active:
            self.panel.setScale(min(1., aspect/(16/9)))

    def text(self, value, x, z, scale=.035, color=theme.WHITE):
        mapped = color if self.garage_page is not None else {theme.INK: theme.WHITE, theme.MUTED: theme.DARK_SUB}.get(color, color)
        label = OnscreenText(parent=self.content, text=value, font=self.font, fg=mapped,
            align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)
        self.labels.append(label)
        return label

    def line(self, points, color=theme.STEEL_TEXT, thickness=2.6):
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
        self.line([(px, pz-.018) for px, pz in points], theme.STEEL_TEXT, 2.2)
        self.line([(px, pz+.018) for px, pz in points], theme.STEEL_TEXT, 2.2)
        if kind == 'traffic':
            for offset in (-.20, .12):
                rounded_panel(self.content, 'traffic-car',
                    (x+offset-.034, x+offset+.034, z-.016, z+.016), theme.AMBER, 0.)
        if kind == 'valley':
            self.line([(x-.10, z-.06), (x+.10, z-.06)], theme.AMBER, 3.8)
        if kind == 'tour':
            for offset in (-.24, 0., .24):
                self.line([(x+offset, z-.035), (x+offset, z+.035)], theme.AMBER, 3.)

    def button(self, index, x, z, width, height, *, primary=False, compact=False):
        button = self.buttons[index]
        button.reparentTo(self.content)
        button.setPos(x, 0, z)
        button['frameSize'] = (-width/2, width/2, -height/2, height/2)
        button['text_scale'] = .038 if compact else .042
        button['text_align'] = TextNode.ALeft if not compact else TextNode.ACenter
        button['text_pos'] = (-width/2+.06, height/2-.085) if not compact else (0, -.014)
        button.setTransparency(TransparencyAttrib.MAlpha)
        if primary:
            self.primary.add(index)
        return button

    def select(self, index):
        if self.garage_page is not None:
            from ui.menu_layout import style

            style(self, index)
            return
        loader = getattr(self, 'app_loader', None)
        for i, button in enumerate(self.buttons):
            if loader is not None:
                if i in self.primary:
                    tex_name = 'atelier/btn-primary-hover.png' if i == index else 'atelier/btn-primary.png'
                elif i == index:
                    tex_name = 'atelier/card-active.png'
                else:
                    tex_name = 'atelier/card-idle.png'
                button['frameTexture'] = atelier.tex(loader, tex_name)
                button['frameColor'] = (1, 1, 1, 1)
            else:
                button['frameTexture'] = None
                button['frameColor'] = theme.AMBER if i in self.primary else theme.AMBER_WASH if i == index else theme.CARBON_CARD
            if i in self.primary:
                button['text_fg'] = theme.INK
            elif i == index:
                button['text_fg'] = theme.AMBER
            else:
                button['text_fg'] = theme.WHITE

    def audio(self, app, station):
        from ui.menu_settings import audio

        audio(self, app, station)

    def assists(self, app):
        from ui.menu_settings import assists

        assists(self, app)

    def routes(self, app):
        self.begin(app, '路线选择', '固定原车 · 每关独立预算 · 用时与赛段油耗联合评价')
        rows = (
            ('bend', '1.8公里 · 连贯通过四门', '预算5000 · 联合目标（试行）'),
            ('hill', '1.4公里 · 起伏路面冲刺', '预算5000 · 联合目标标定中'),
            ('valley', '375m ≥80 km/h\n400–650m · 35–50 km/h', '预算5000 · 联合评价'),
            ('traffic', '2公里 · 安全超越2辆', '并行 ≥1m · 前后 ≥10m'),
            ('hill', '2.4公里 · 安全超越3辆', '预算5000 · 固定终点结算'),
            ('tour', '山谷 → 连弯 → 弯坡车流', '每站独立预算 · 联合评价'))
        for index, (kind, description, target) in enumerate(rows):
            x, z = (-1.06, 0., 1.06)[index % 3], .23 if index < 3 else -.29
            self.button(index, x, z, 1.00, .45)
            self.route(x, z+.048, .80, kind)
            self.text(description, x-.44, z-.050, .030, theme.DARK_SUB)
            self.text(target, x-.44, z-.155, .029, theme.STEEL_TEXT)
        self.text('路线示意 · 前三项无车流，上限180秒；碰撞 / 越界 / 复位结束挑战', -1.50, -.63, .030, theme.DARK_SUB)
        self.button(6, 1.13, -.77, .86, .10, compact=True)
        self.summary_order = (0, 1, 2, 3, 4, 5, 6)
        self.select(app.panel_selection)

    def highway(self, app):
        self.begin(app, '无限高速', '选择自由驾驶或驾驶课题', dark=app.workshop_garage_return)
        for index, x in enumerate((-.79, .79)):
            self.button(index, x, .40, 1.48, .11, compact=True)
        for index, x, kind, description in (
                (2, -.79, 'bend', '没有计时压力 · 按选择的道路与车流出发'),
                (3, .79, 'traffic', '车道内完成5公里 · 碰撞、越界或复位结束')):
            self.button(index, x, .085, 1.48, .39)
            self.route(x, .10, 1.20, kind)
            self.text(description, x-.66, -.050, .029, theme.DARK_SUB)
        for index, x, title, description in (
                (4, -1.06, '制动与停车', '定点精度 / 短距制动 / 预算设置'),
                (5, 0., '转向与过门', '连续六门 / 高速验车 / 预算设置'),
                (6, 1.06, '路线与巡回', '山谷 / 连弯 / 弯坡车流 / 三站')):
            self.button(index, x, -.37, 1.00, .29)
            self.text(title, x-.44, -.39, .035, theme.STEEL_TEXT)
            self.text(description, x-.44, -.47, .025, theme.DARK_SUB)
        self.text('选定道路或车流后可用 ← → 切换', -1.50, -.63, .030, theme.DARK_SUB)
        self.button(7, 1.13, -.77, .86, .10, compact=True)
        self.select(app.panel_selection)

    def lesson(self, app, *, braking, fast):
        from race import GameMode
        practice = not braking and app.slalom_mode == GameMode.SLALOM_PRACTICE
        title = ('短距制动验车' if fast else '定点刹停') if braking else ('高速验车' if fast else '连续过门')
        if practice:
            title = '过门练习'
        self.begin(app, title, '当前车辆 · 自由练习不授奖' if practice else
                   '固定原车 · 独立预算设置 · 封闭场地无车流', dark=app.workshop_garage_return)
        self.frames.append(atelier.picture(self.content, app.loader, 'atelier/panel-obsidian.png', (-1.54, .52, -.31, .47)))
        self.frames.append(atelier.picture(self.content, app.loader, 'atelier/panel-obsidian.png', (.52, 1.54, -.31, .47)))
        rounded_panel(self.content, 'lesson-left-bar', (-1.42, -1.410, .322, .372), theme.AMBER, .003)
        rounded_panel(self.content, 'lesson-right-bar', (.61, .620, .322, .372), theme.AMBER, .003)
        self.text('场地示意', -1.38, .33, .034, theme.DARK_SUB)
        if braking:
            self.line([(-1.32, .03), (.28, .03)], theme.STEEL_TEXT, 5.)
            for x, label in ((-1.22, '起步'), (-.32, '100m测速门'), (.20, '142m' if fast else '170m')):
                self.line([(x, -.03), (x, .10)], theme.AMBER, 3.2)
                self.text(label, x-.12, -.13, .031, theme.WHITE)
            self.text('80–85 km/h' if fast else '≥80 km/h', -.49, .17, .045, theme.STEEL_TEXT)
            self.text('过门后尽快停稳' if fast else '瞄准170米线停车', -1.35, -.23, .036, theme.WHITE)
            target = '最大前进距离' if fast else '停车绝对误差'
            medals = ('金 ≤33m', '银 ≤36m', '铜 ≤42m') if fast else ('金 ≤2m', '银 ≤5m', '铜 ≤10m')
            rule = '松开刹车停稳1秒 · 30秒内完成\n'+('直行带±1m · 偏角≤5° · 不可倒车' if fast else
                                                        '允许倒车调整 · 碰撞/复位结束')
        else:
            self.route(-.51, .05, 1.60, 'slalom')
            for index in range(6):
                x = -1.23+index*.29
                z = .05+math.sin(index*math.pi/2)*.035
                self.line([(x, z-.055), (x, z+.055)], theme.AMBER, 3.2)
                self.text(str(index+1), x-.015, -.09, .033, theme.WHITE)
            self.text('不限入口速度' if practice else '全段 70–80 km/h' if fast else '入门 ≥40 km/h', -1.35, .18, .044, theme.STEEL_TEXT)
            self.text('80m入门 → 120–320m六门', -1.35, -.23, .036, theme.WHITE)
            target = '有效六门总用时'
            medals = ('金 ≤11.5s', '银 ≤12.5s', '铜 ≤14s') if fast else ('金 ≤15s', '银 ≤18s', '铜 ≤24s')
            rule = '整车依次过门 · 门宽4米\n漏门/碰撞/越界/复位结束 · 上限40秒'
            if practice:
                target = '先找到过门节奏'
                medals = ('漏门可继续', '逐门看余量', '不记录奖牌')
                rule = 'W加速 · S刹车 · A/D转向 · 漏门可继续\n碰撞/越界/复位结束 · 上限40秒'
        self.text(target, .65, .33, .036, theme.DARK_SUB)
        for z, label, color in zip((.19, .03, -.13), medals, (theme.AMBER, theme.SILVER, theme.BRONZE), strict=True):
            self.text(label, .66, z, .054, color)
        self.text(rule, -1.50, -.37, .034, theme.DARK_SUB)
        self.button(0, -.96, -.77, 1.08, .12, primary=True, compact=True)
        self.button(2, .30, -.77, 1.28, .12, compact=True)
        self.button(1, -.77, -.55, 1.46, .10, compact=True)
        self.button(3, 1.25, -.77, .50, .12, compact=True)
        self.summary_order = (1, 0, 2, 3)
        self.select(app.panel_selection)

    def practice_result(self, app, result):
        self.begin(app, '练习完成' if result.succeeded else '练习结束',
                   f'通过 {result.gates}/6门 · 漏门可继续练习 · 不记录正式奖牌', dark=True)
        for index in range(6):
            x, z = (-1.04, 0., 1.04)[index % 3], .20 if index < 3 else -.20
            reached = index < len(result.clearances)
            passed = reached and result.clearances[index] >= 0
            color = theme.PINE if passed else theme.AMBER if reached else theme.DARK_SUB
            self.frames.append(atelier.picture(
                self.content, app.loader, 'atelier/card-active.png' if (reached and not passed) else 'atelier/card-idle.png',
                (x-.49, x+.49, z-.19, z+.19)))
            rounded_panel(self.content, 'practice-gate-bar', (x-.43, x-.420, z-.10, z+.10), color, .003)
            self.text(f'第 {index+1} 门', x-.37, z+.075, .048, theme.WHITE)
            self.text('通过' if passed else '漏门' if reached else '未到达', x+.12, z+.075, .044, color)
            self.text(f'车身余量 {result.clearances[index]:+.2f}m' if reached else '未到达该门',
                      x-.37, z-.07, .038, theme.DARK_SUB)
        if not result.succeeded:
            self.text(app.fit_lines(result.reason, 2.8, .032), -1.50, -.47, .032, theme.AMBER)
        for index, x, label in ((0, -1.13, '重新练习'), (3, -.37, '改装前轮'),
                                (1, .40, '返回工坊'), (2, 1.17, '主菜单')):
            self.buttons[index]['text'] = label
            self.button(index, x, -.77, .70, .12, primary=index == 0, compact=True)
            self.buttons[index]['text_scale'] = .046
        self.summary_order = (0, 3, 1, 2)
        self.select(app.panel_selection)

    def overtake(self, app, route):
        self.begin(app, route.title, f'{route.distance/1000:g}公里 · 固定原车 · 独立预算5000')
        self.frames.append(atelier.picture(self.content, app.loader, 'atelier/panel-obsidian.png', (-1.54, .52, -.31, .47)))
        self.frames.append(atelier.picture(self.content, app.loader, 'atelier/panel-obsidian.png', (.52, 1.54, -.31, .47)))
        rounded_panel(self.content, 'overtake-left-bar', (-1.42, -1.410, .322, .372), theme.AMBER, .003)
        rounded_panel(self.content, 'overtake-right-bar', (.61, .620, .322, .372), theme.AMBER, .003)
        self.text('换道与净距示意', -1.38, .33, .034, theme.DARK_SUB)
        for z in (.06, .23):
            self.line([(-1.35, z), (.30, z)], theme.STEEL_TEXT, 1.2)
        for x, z, color in ((-.84, .14, theme.STEEL_TEXT), (-.43, .35, theme.AMBER)):
            rounded_panel(self.content, 'car-footprint', (x-.13, x+.13, z-.04, z+.04), color, .012)
        self.line([(-1.20, .14), (-.98, .14), (-.79, .35), (-.60, .35)], theme.AMBER, 3.2)
        self.text('并行侧距 ≥1m', -1.35, -.08, .042, theme.WHITE)
        self.text('跟车 / 切回前后净距 ≥10m', -1.35, -.23, .038, theme.STEEL_TEXT)
        self.text(f'安全超越 {route.passes} 辆', .65, .33, .042, theme.WHITE)
        self.text('用时与赛段油耗', .66, .19, .044, theme.STEEL_TEXT)
        self.text('联合目标标定中', .66, .03, .044, theme.WHITE)
        self.text('当前可试跑', .66, -.13, .038, theme.DARK_SUB)
        self.text(f'超车达标后，仍须在{route.seconds:g}秒内安全到终点。'+
                  '\n从后方接近并整车领先10米才计数；贴身/碰撞/越界/逆向/复位结束。',
                  -1.50, -.40, .034, theme.DARK_SUB)
        self.button(0, -.94, -.77, 1.12, .12, primary=True, compact=True)
        self.button(1, 1.01, -.77, 1.00, .12, compact=True)
        self.summary_order = (0, 1)
        self.select(app.panel_selection)
