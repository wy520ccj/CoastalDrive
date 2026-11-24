"""落日海岸工坊首页：70% 全高落日车库展车舞台 + 右侧通高黑曜石微光卡片面板 + 底部序号进度栏。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career_garage import garage_cars
from ui import atelier, theme
from ui.lab_widgets import gradient_panel, rounded_panel

WHITE = theme.WHITE
CREAM = theme.PAPER_LIGHT
INK = theme.INK
CHARCOAL = theme.CHARCOAL
MUTED = theme.DARK_SUB
ORANGE = theme.AMBER
GLASS = theme.CARBON
BORDER = theme.CARBON_EDGE
SHADOW = theme.SHADOW
DARK = theme.CARBON_SOLID
GRAY = theme.DARK_SUB


class MainMenu:
    def __init__(self, parent, loader, body_font, display_font, actions, *, vehicle_view, confirm_action,
                 continue_action, driving_mode_action=None, lab_action=None, highway_action=None):
        self.root = parent.attachNewNode('main-menu')
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.content = self.root.attachNewNode('menu-content')
        self.home = self.root.attachNewNode('menu-home')
        self.loader, self.font, self.display_font = loader, body_font, display_font
        self.bold = theme.load_font(atelier.BOLD_FONT_FILE)
        self.regular = theme.load_font(atelier.REGULAR_FONT_FILE)
        self.vehicle_view = vehicle_view
        self.confirm_action = confirm_action
        self.actions = (*actions, lab_action, driving_mode_action)
        self.order = (2, 3, 1, 0, 6, 7, 4, 5)
        if highway_action is not None:
            self.actions = (*self.actions, highway_action)
            self.order = (2, 3, 1, 8, 0, 6, 7, 4, 5)
        self.continue_index = len(self.actions)
        self.actions = (*self.actions, continue_action)
        self.order = (self.continue_index, *self.order)
        self.selected, self.aspect = self.continue_index, None
        self.widgets, self.subtitles, self.tile_frames = [], {}, []
        self.buttons = []
        self.textures = tuple(loader.loadTexture(theme.asset_filename(f'components/button-{state}.png'))
                              for state in ('normal', 'pressed', 'hover', 'disabled'))
        # 完整落日海岸工坊背景（无车空展台，供 3D 实车自然落位）。
        self.background = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=atelier.tex(loader, atelier.SUNSET_GARAGE_BG),
            frameSize=(-16/9, 16/9, -1, 1), sortOrder=-10, state=DGG.DISABLED)
        self.notice = self.label('', 0, 0, 15, theme.AMBER, bold=True)
        self.stars = self.label('', 0, 0, 16, theme.AMBER, bold=True)
        self.credits = self.label('', 0, 0, 14, theme.DARK_SUB)
        self.car_name = self.label('', 0, 0, 27, WHITE, bold=True)
        self.vehicle_note = self.label('', 0, 0, 15, theme.DARK_SUB)
        self.pi_text = self.label('C 595', 0, 0, 14, theme.STEEL_TEXT, bold=True)
        self.pi_text['font'] = self.display_font
        self.pi_specs = self.label('', 0, 0, 15, theme.DARK_SUB)
        self.mini_car_frame = None
        self.time_goal = None
        self.resize(vehicle_view.base.getAspectRatio())
        self.root.hide()

    def label(self, text, x, y, size, color=WHITE, *, bold=False, parent=None, display=False):
        node = OnscreenText(parent=self.home if parent is None else parent, text=text,
            font=self.display_font if display else self.bold if bold else self.regular,
            fg=color, align=TextNode.ALeft,
            pos=(x*2/941, -y*2/941), scale=size*2/941, mayChange=True)
        self.widgets.append(node)
        return node

    def point(self, x, y):
        return (x-self.width/2)*2/941, 1-y*2/941

    def box(self, x, y, width, height):
        a, b = self.point(x, y+height), self.point(x+width, y)
        return a[0], b[0], a[1], b[1]

    def fill(self, x, y, width, height, color, radius=6, parent=None):
        target = self.layout if parent is None else parent
        node = rounded_panel(target, 'menu-fill', self.box(x, y, width, height), color, radius*2/941)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def pic(self, name, x, y, w, h, *, color=(1, 1, 1, 1), parent=None, crop=False):
        target = self.layout if parent is None else parent
        frame = atelier.picture(target, self.loader, name, self.box(x, y, w, h), color=color, crop=crop)
        self.tile_frames.append(frame)
        return frame

    def place_label(self, text, x, y, size, color=WHITE, *, bold=False, display=False, right=False, center=False):
        node = self.label(text, 0, 0, size, color, bold=bold, parent=self.layout, display=display)
        node.setPos(*self.point(x, y))
        if right:
            node.textNode.setAlign(TextNode.ARight)
        elif center:
            node.textNode.setAlign(TextNode.ACenter)
        return node

    def _make_btn(self, index, title, x, y, w, h, *, tex_name=None, text_fg=WHITE, text_scale=17,
                  text_pos=(0, -6), align=TextNode.ACenter, bold=False, kind='card'):
        unit = 2/941
        px, pz = self.point(x+w/2, y+h/2)
        fsize = (-w*unit/2, w*unit/2, -h*unit/2, h*unit/2)
        tex = atelier.tex(self.loader, tex_name) if tex_name else None
        node = DirectButton(parent=self.layout, text=title,
            text_font=self.bold if bold else self.regular,
            text_fg=text_fg, text_scale=text_scale*unit,
            text_align=align, text_pos=(text_pos[0]*unit, text_pos[1]*unit),
            pos=(px, 0, pz), frameSize=fsize,
            frameTexture=tex, frameColor=(1, 1, 1, 1) if tex else (0, 0, 0, 0),
            relief=DGG.FLAT, pressEffect=False, command=lambda: self.activate(index))
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.bind(DGG.ENTER, lambda event, i=index: self.select(i))
        node.bind(DGG.B1PRESS, lambda event: self.confirm_action())
        self.buttons[index] = node
        self.btn_kinds[index] = kind
        return node

    def _option_card(self, index, title, subtitle, thumb_name, x, y, w, h, *, badge=None):
        unit = 2/941
        node = self._make_btn(index, title, x, y, w, h, tex_name='atelier/card-idle.png',
                              text_fg=(0, 0, 0, 0), kind='card')
        # 左侧内嵌暗调写实摄影缩略图（平滑羽化融入黑曜石卡片底面，复刻参考图轮胎实拍卡片质感）。
        th_w = min(132., w * 0.34)
        th_h = h - 10.
        th_box = ((-w/2+7)*unit, (-w/2+7+th_w)*unit, (-th_h/2)*unit, (th_h/2)*unit)
        thumb = atelier.picture(node, self.loader, f'atelier/thumb-{thumb_name}.png',
                                th_box, color=(0.86, 0.88, 0.92, 0.96))
        self.tile_frames.append(thumb)
        self.btn_icons[index] = thumb
        # 中间主副标题（缩略图右侧留出舒适呼吸间距）。
        tx = -w/2 + th_w + 14.
        t_node = self.label(title, tx, -6, 19.5, WHITE, bold=True, parent=node)
        self.card_titles[index] = t_node
        if subtitle is not None:
            sub = self.label(subtitle, tx, 20, 13.5, theme.DARK_SUB, parent=node)
            self.subtitles[index] = sub
            if index == 0:
                self.time_goal = sub
        if badge:
            bw = 54
            rounded_panel(node, 'card-badge', ((w/2-104)*unit, (w/2-104+bw)*unit, -2*unit, 20*unit),
                          theme.STEEL_BG, 4*unit)
            b_lbl = self.label(badge, w/2-104+bw/2, -5, 11.5, theme.STEEL_TEXT, bold=True, parent=node)
            b_lbl.textNode.setAlign(TextNode.ACenter)
        # 右侧高分抗锯齿单选圆环。
        r_s = 23
        r_box = ((w/2-38)*unit, (w/2-38+r_s)*unit, (-r_s/2)*unit, (r_s/2)*unit)
        default_radio = 'atelier/radio-installed.png' if index == 2 else 'atelier/radio-idle.png'
        radio = atelier.picture(node, self.loader, default_radio, r_box)
        self.tile_frames.append(radio)
        self.btn_radios[index] = radio

    def _left_tab(self, index, title, icon_name, y):
        unit = 2/941
        w, h = 166., 66.
        node = self._make_btn(index, title, 0, y, w, h, tex_name='atelier/left-tab-idle.png',
                              text_fg=(0, 0, 0, 0), kind='left-tab')
        ic_s = 28
        ic_box = ((-w/2+24)*unit, (-w/2+24+ic_s)*unit, (-ic_s/2)*unit, (ic_s/2)*unit)
        ic = atelier.picture(node, self.loader, f'atelier/icon-{icon_name}.png',
                             ic_box, color=(0.82, 0.86, 0.92, 0.96))
        self.tile_frames.append(ic)
        self.btn_icons[index] = ic
        t_node = self.label(title, -w/2+62, 7, 17, (0.82, 0.86, 0.92, 1), parent=node)
        self.card_titles[index] = t_node

    def resize(self, aspect):
        if self.aspect == aspect:
            return
        owns_car = self.vehicle_view.frame is not None and self.vehicle_view.frame.getParent() == self.home
        old_goal = '' if self.time_goal is None else self.time_goal.getText()
        next_event = self.subtitles.get(self.continue_index)
        next_name = '' if next_event is None else next_event.getText()
        self.aspect, self.width = aspect, 941*aspect
        self.content.setScale(min(1, aspect/(16/9)))
        self.background['frameSize'] = (-aspect, aspect, -1, 1)
        texture = self.background['frameTexture']
        crop = aspect/(texture.getXSize()/texture.getYSize())
        self.background.setTexScale(TextureStage.getDefault(), min(1, crop), min(1, 1/crop))
        self.background.setTexOffset(TextureStage.getDefault(), max(0, (1-crop)/2), max(0, (1-1/crop)/2))
        if self.buttons:
            keep = (self.notice, self.stars, self.credits, self.car_name, self.vehicle_note,
                    self.pi_text, self.pi_specs)
            for widget in keep:
                widget.reparentTo(self.home)
            for widget in self.widgets:
                if widget not in keep:
                    widget.destroy()
            self.widgets = list(keep)
            for frame in self.tile_frames:
                frame.destroy()
            self.tile_frames.clear()
            for button in self.buttons:
                button.destroy()
            self.layout.removeNode()
        self.layout = self.home.attachNewNode('menu-layout')
        self.buttons = [None]*len(self.actions)
        self.subtitles, self.btn_kinds, self.btn_icons, self.btn_radios, self.card_titles = {}, {}, {}, {}, {}

        unit = 2/941
        dock_w = min(492., max(390., self.width * 0.295))
        stage_w = self.width - dock_w
        foot_y = 858.

        # ── 左侧 70.5% 全高落日海岸工坊展台 ──
        # 顶部柔暗渐隐与底部电影暗角，完整保留车库横梁与落日海面层次。
        gradient_panel(self.layout, 'stage-top-scrim', self.box(0, 0, stage_w, 120),
                       (0.03, 0.04, 0.06, 0.0), (0.03, 0.04, 0.06, 0.78))
        gradient_panel(self.layout, 'stage-bottom-scrim', self.box(0, 680, stage_w, foot_y-680),
                       (0.03, 0.04, 0.06, 0.86), (0.03, 0.04, 0.06, 0.0))

        # 车底暖金落日地面反光与环境接地暗晕（位于实车下方，消除贴图悬浮感）。
        floor_glow = atelier.picture(self.layout, self.loader, 'atelier/floor-warm-bounce.png',
                                     self.box(125, 498, stage_w - 165, 230), sort_order=-2)
        self.tile_frames.append(floor_glow)

        # 左上角：真实手刷 COASTAL DRIVE 透明标识图 + 副标题（复刻参考图左上角）。
        wm = atelier.wordmark(self.layout, self.loader, self.box(34, 18, 246, 46))
        self.tile_frames.append(wm)
        self.place_label('海岸工坊', 38, 82, 16, (0.80, 0.84, 0.90, 0.92))

        # 顶栏中部磨砂深色玻璃导览条 + 平铺无框页签（复刻参考图「改装车辆 / 试车场 / 我的方案」）。
        tab_x = 344. if aspect > 1.5 else 296.
        self.pic('atelier/top-nav-glass.png', tab_x - 48, 0, 390 if aspect > 1.5 else 310, 74)
        self.place_label('主页', tab_x, 48, 19, WHITE, bold=True)
        self.fill(tab_x-12, 70, 64, 3, theme.AMBER, 1.5)
        self._make_btn(3, '海岸车库', tab_x+86, 18, 118, 46, text_fg=(0.74, 0.79, 0.86, 1), text_scale=19, kind='top-tab')
        self.top_tab_underlines = {3: self.fill(tab_x+102, 70, 86, 3, theme.AMBER, 1.5)}
        self.top_tab_underlines[3].hide()

        # 左缘悬浮磨砂玻璃垂直页签（复刻参考图「前轮 / 制动」）。
        self._left_tab(7, '驾驶辅助', 'shield', 148)
        self._left_tab(4, '声音设置', 'speaker', 226)
        self.driving_mode_button = self.buttons[7]

        # 展车左下方磨砂深色当前车辆信息卡 + 真实 Cycles 车模小图（1:1 复刻参考图左下角！）。
        strip_x, strip_w = 24., min(524., stage_w - 48)
        self.pic('atelier/car-strip-glass.png', strip_x, 738, strip_w, 110)
        self.place_label('当前车辆', strip_x + 18, 766, 13.5, theme.DARK_SUB)
        self.fill(strip_x + 90, 750, 64, 21, theme.STEEL_BG, 4)
        self.mini_car_frame = atelier.picture(
            self.layout, self.loader, 'garage-v2/car-game-tuned.png',
            self.box(strip_x + strip_w - 196, 744, 174, 96), color=(0.94, 0.89, 0.82, 0.96))
        self.tile_frames.append(self.mini_car_frame)

        # ── 右侧 29.5% 通高拉丝哑光黑曜石操作面板（自带向左环境投射阴影）──
        self.pic('atelier/dock-surface.png', stage_w - 34, 0, dock_w + 34, foot_y)
        self.fill(stage_w, 74, dock_w, 1.2, (0.20, 0.24, 0.31, 0.85), 0)

        # 右上角：极简单一拉丝金属「专家试验台 ›」按钮 + 烧瓶图标（1:1 复刻参考图右上角！）。
        lab_w = 178.
        lab_x = self.width - 30 - lab_w
        lab_btn = self._make_btn(6, '专家试验台  ›', lab_x, 15, lab_w, 44,
                                 tex_name='atelier/btn-ghost.png', text_fg=WHITE, text_scale=15,
                                 text_pos=(12, -5), kind='ghost')
        lab_ic = atelier.picture(lab_btn, self.loader, 'atelier/icon-flask.png',
                                 ((-lab_w/2+18)*unit, (-lab_w/2+40)*unit, -11*unit, 11*unit), color=WHITE)
        self.tile_frames.append(lab_ic)
        self.btn_icons[6] = lab_ic

        pad = 28.
        rx = stage_w + pad
        rw = dock_w - 2 * pad
        self.place_label('第一季  /  海岸驾驶', rx, 112, 13.5, theme.DARK_SUB)
        self.place_label('出发方式', rx, 152, 31, WHITE, bold=True)
        self.place_label('选择赛事模式或自由巡游。', rx, 182, 14.5, theme.DARK_SUB)

        # 右栏核心 4 枚内嵌写实缩略图的高质感微光选项卡片（1:1 复刻参考图 4 行轮胎实拍卡片质感！）。
        has_highway = 8 in self.order
        cards_spec = (
            (2, '生涯赛事', '章节奖牌 · 解锁车辆', 'career', '推荐'),
            (1, '滨海自由驾驶', '阳光海岸环路巡游', 'free', None),
            (0, '计时挑战', old_goal or '预算 5000 · 用时与油耗', 'timetrial', None),
            (8, '无限高速', '自由 · 5km · 课题', 'highway', None),
        ) if has_highway else (
            (2, '生涯赛事', '章节奖牌 · 解锁车辆', 'career', '推荐'),
            (1, '滨海自由驾驶', '阳光海岸环路巡游', 'free', None),
            (0, '计时挑战', old_goal or '预算 5000 · 用时与油耗', 'timetrial', None),
        )
        card_h = 88. if has_highway else 104.
        card_gap = 12.
        for ci, (idx, title, sub, thumb_name, badge) in enumerate(cards_spec):
            cy = 206. + ci * (card_h + card_gap)
            self._option_card(idx, title, sub, thumb_name, rx, cy, rw, card_h, badge=badge)

        # 卡片下方：双栏进度与推荐赛事对比条（复刻参考图「已安装 → 待安装」节奏）。
        sum_y = 618.
        self.fill(rx, sum_y, rw, 1, (0.20, 0.24, 0.31, 0.85), 0)
        self.place_label('赛季星级', rx, sum_y+28, 13.5, theme.DARK_SUB)
        self.place_label('→', rx+rw*0.42, sum_y+62, 22, theme.DARK_SUB, center=True)
        self.place_label('下一场推荐', rx+rw*0.52, sum_y+28, 13.5, theme.DARK_SUB)
        next_sub = self.place_label(next_name or '海岸初驶', rx+rw*0.52, sum_y+62, 23, theme.AMBER, bold=True)
        self.subtitles[self.continue_index] = next_sub
        self.place_label('进入后可原车发车或调整方案。', rx, sum_y+98, 14, theme.DARK_SUB)

        # 右栏底部行动行：缎面暖琥珀金主按钮「继续赛季」（配方向盘图标）+ 细描边暗钢「退出」。
        cta_y, cta_h = 746., 66.
        exit_w = 114.
        go_w = rw - exit_w - 12.
        go_btn = self._make_btn(self.continue_index, '继续赛季', rx, cta_y, go_w, cta_h,
                                tex_name='atelier/btn-primary.png', text_fg=INK, text_scale=20,
                                text_pos=(18, -7), bold=True, kind='primary')
        go_ic = atelier.picture(go_btn, self.loader, 'atelier/icon-steering.png',
                                (-68*unit, -40*unit, -14*unit, 14*unit), color=INK)
        self.tile_frames.append(go_ic)
        self._make_btn(5, '退出', rx+go_w+12, cta_y, exit_w, cta_h,
                       tex_name='atelier/btn-ghost.png', text_fg=(0.76, 0.81, 0.88, 1), text_scale=18, kind='ghost')

        # ── 底部通宽拉丝黑曜石序号进度底栏 + 右下角斜切角标（1:1 复刻参考图底栏！）──
        self.pic('atelier/footer-surface.png', 0, foot_y, self.width, 941-foot_y)
        self.pic('atelier/footer-corner-tag.png', self.width - 178, foot_y + 38, 178, 45)
        self.place_label('海岸工坊 · S1', self.width - 24, foot_y + 68, 13.5, theme.DARK_SUB, right=True)

        steps = (('1', '选择模式', True), ('2', '车辆调校', False), ('3', '海岸试驾', False))
        step_span = 260. if aspect > 1.5 else 210.
        start_sx = self.width/2 - step_span - 60
        sy = foot_y + 42
        for si, (num, s_label, is_on) in enumerate(steps):
            cx = start_sx + si * step_span
            self.pic('atelier/step-active.png' if is_on else 'atelier/step-idle.png', cx-16, sy-16, 32, 32)
            self.place_label(num, cx, sy+7, 15, INK if is_on else theme.DARK_SUB, bold=True, center=True)
            self.place_label(s_label, cx+26, sy+7, 16, theme.AMBER if is_on else theme.DARK_SUB, bold=is_on)
            if si < 2:
                self.fill(cx+112, sy-0.5, step_span-144, 1.2, (0.24, 0.28, 0.36, 0.9), 0)

        self.place_label('↑ ↓ 选择   Enter 确认   F2 辅助', 34, sy+7, 14, theme.DARK_SUB)

        for node, x, y, align in (
            (self.stars, rx, sum_y+62, TextNode.ALeft),
            (self.credits, strip_x+strip_w-16, 766, TextNode.ARight),
            (self.pi_text, strip_x+122, 765, TextNode.ACenter),
            (self.car_name, strip_x+18, 804, TextNode.ALeft),
            (self.pi_specs, strip_x+18, 833, TextNode.ALeft),
            (self.vehicle_note, strip_x+230, 833, TextNode.ALeft),
            (self.notice, strip_x+18, 722, TextNode.ALeft),
        ):
            node.reparentTo(self.layout)
            node.setPos(*self.point(x, y))
            node.textNode.setAlign(align)

        # 3D 实车贴合落日车库湿润水泥地面透视落位（低机位前左 3/4 视角，与左下车辆卡留足呼吸空间）。
        self.car_box = self.box(130, 165, stage_w-145, 555)
        if owns_car:
            self.vehicle_view.show(self.home, self.car_box, self.vehicle_view.base.workspace_vehicle, studio=True)
            self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.select(self.selected)

    def show_home(self, progress, vehicle, continuation):
        self.home.show()
        self.stars.setText(f'★ {progress.stars} / 18')
        self.stars.setFg(WHITE)
        self.stars.setScale(23 * 2 / 941)
        self.subtitles[self.continue_index].setText(continuation)
        self.credits.setText('')
        car = next(car for car in garage_cars(vehicle) if car.design_id == vehicle.design_id)
        letter, score, _, power_kw, _ = theme.vehicle_pi(vehicle.config)
        self.car_name.setText(car.name)
        self.pi_text.setText(f'{letter} {score}')
        self.pi_specs.setText(f'{power_kw:.0f} kW  |  {vehicle.config.mass:.0f} kg  |  {car.category}')
        self.vehicle_note.setText('')
        if self.mini_car_frame is not None:
            thumb_id = vehicle.design_id if vehicle.design_id in (
                'game-tuned', 'coastal-hatch', 'coastal-roadster', 'gr86-2022-premium-6mt',
                'coastal-gt', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else 'game-tuned'
            self.mini_car_frame['frameTexture'] = atelier.tex(self.loader, f'garage-v2/car-{thumb_id}.png')
        self.vehicle_view.show(self.home, self.car_box, vehicle, studio=True)
        self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.vehicle_view.highlight(None)

    def hide_home(self):
        self.home.hide()
        if self.vehicle_view.frame is not None and self.vehicle_view.frame.getParent() == self.home:
            self.vehicle_view.hide()

    def set_driving_mode(self, mode):
        self.driving_mode_button['text'] = '驾驶辅助'

    def select(self, index):
        self.selected = index % len(self.buttons)
        for i, button in enumerate(self.buttons):
            focused = i == self.selected
            kind = self.btn_kinds[i]
            if kind == 'primary':
                button['frameTexture'] = atelier.tex(self.loader,
                    'atelier/btn-primary-hover.png' if focused else 'atelier/btn-primary.png')
            elif kind == 'ghost':
                button['frameTexture'] = atelier.tex(self.loader,
                    'atelier/btn-ghost-hover.png' if focused else 'atelier/btn-ghost.png')
                button['text_fg'] = theme.AMBER if focused else (WHITE if i == 6 else theme.DARK_SUB)
                if i in self.btn_icons:
                    self.btn_icons[i]['frameColor'] = theme.AMBER if focused else WHITE
            elif kind == 'card':
                button['frameTexture'] = atelier.tex(self.loader,
                    'atelier/card-active.png' if focused else 'atelier/card-idle.png')
                if i in self.card_titles:
                    self.card_titles[i].setFg(theme.AMBER if focused else WHITE)
                if i in self.btn_icons:
                    self.btn_icons[i]['frameColor'] = (1.06, 1.02, 0.96, 1.0) if focused else (0.86, 0.88, 0.92, 0.95)
                if i in self.btn_radios:
                    idle_r = 'atelier/radio-installed.png' if i == 2 else 'atelier/radio-idle.png'
                    self.btn_radios[i]['frameTexture'] = atelier.tex(self.loader,
                        'atelier/radio-active.png' if focused else idle_r)
            elif kind == 'left-tab':
                button['frameTexture'] = atelier.tex(self.loader,
                    'atelier/left-tab-active.png' if focused else 'atelier/left-tab-idle.png')
                if i in self.card_titles:
                    self.card_titles[i].setFg(theme.AMBER if focused else (0.82, 0.86, 0.92, 1))
                if i in self.btn_icons:
                    self.btn_icons[i]['frameColor'] = theme.AMBER if focused else (0.82, 0.86, 0.92, 0.96)
            elif kind == 'top-tab':
                button['text_fg'] = WHITE if focused else theme.DARK_SUB
                if i in self.top_tab_underlines:
                    self.top_tab_underlines[i].show() if focused else self.top_tab_underlines[i].hide()

    def move(self, direction):
        if self.selected in (7, 4, 5):
            self.select(self.continue_index if direction > 0 else 6)
        else:
            self.select(self.order[(self.order.index(self.selected)+direction) % len(self.order)])

    def horizontal(self, direction):
        footer = (7, 4, 5)
        if self.selected in footer:
            self.select(footer[(footer.index(self.selected)+direction) % len(footer)])
        else:
            self.move(direction)

    def activate(self, index=None):
        if index is not None:
            self.select(index)
        self.hide_home()
        self.actions[self.selected]()

    def destroy(self):
        for widget in self.widgets:
            widget.destroy()
        for frame in self.tile_frames:
            frame.destroy()
        for button in self.buttons:
            button.destroy()
        self.background.destroy()
        self.root.removeNode()
