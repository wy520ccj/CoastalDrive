"""暖阳海岸车库首页：经典左侧画报主导航（复古赛车三色条 + 多彩分类功能磁贴）+ 右侧全高日光展车舞台。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career_garage import garage_cars
from ui import theme
from ui.lab_widgets import rounded_panel

WHITE = (1, 1, 1, 1)
CREAM = theme.PAPER_LIGHT
INK = theme.INK
CHARCOAL = theme.CHARCOAL
MUTED = theme.MUTED
ORANGE = theme.ORANGE
GLASS = theme.GLASS_LIGHT
BORDER = theme.HAIRLINE
SHADOW = theme.SHADOW
# 保留旧导入名兼容 menu_layout / driving_summary。
DARK = CHARCOAL
GRAY = MUTED

# 每个入口拥有专属里维埃拉暖调色带与浅底色，层次丰富一眼辨识。
TILE_THEMES = {
    2: (theme.AMBER, theme.AMBER_TINT, 'CAREER'),
    3: (theme.ORANGE, theme.ORANGE_TINT, 'GARAGE'),
    1: (theme.SEA, theme.SEA_TINT, 'CRUISE'),
    8: (theme.GOLD, theme.AMBER_TINT, 'HIGHWAY'),
    0: (theme.PINE, theme.PINE_TINT, 'TIME TRIAL'),
    6: (theme.BURGUNDY, theme.BURGUNDY_TINT, 'LAB'),
}


class MainMenu:
    def __init__(self, parent, loader, body_font, display_font, actions, *, vehicle_view, confirm_action,
                 continue_action, driving_mode_action=None, lab_action=None, highway_action=None):
        self.root = parent.attachNewNode('main-menu')
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.content = self.root.attachNewNode('menu-content')
        self.home = self.root.attachNewNode('menu-home')
        self.loader, self.font, self.display_font = loader, body_font, display_font
        self.regular = theme.load_font('fonts/SourceHanSansSC-Regular.otf')
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
        self.widgets, self.subtitles, self.tags = [], {}, {}
        self.buttons = []
        self.textures = tuple(loader.loadTexture(theme.asset_filename(f'components/button-{state}.png'))
                              for state in ('normal', 'pressed', 'hover', 'disabled'))
        self.background = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=loader.loadTexture(theme.asset_filename('backgrounds/garage-coastal-v2.png')),
            frameSize=(-16/9, 16/9, -1, 1), sortOrder=-10, state=DGG.DISABLED)
        self.notice = self.label('', 0, 0, 16, ORANGE, bold=True)
        self.stars = self.label('', 0, 0, 21, theme.GOLD, bold=True)
        self.credits = self.label('', 0, 0, 16, MUTED)
        self.car_name = self.label('', 0, 0, 27, INK, bold=True)
        self.vehicle_note = self.label('', 0, 0, 16, MUTED)
        self.time_goal = None
        self.resize(vehicle_view.base.getAspectRatio())
        self.root.hide()

    def label(self, text, x, y, size, color=INK, *, bold=False, parent=None):
        node = OnscreenText(parent=self.home if parent is None else parent, text=text,
            font=self.font if bold else self.regular, fg=color, align=TextNode.ALeft,
            pos=(x*2/941, -y*2/941), scale=size*2/941, mayChange=True)
        self.widgets.append(node)
        return node

    def point(self, x, y):
        return (x-self.width/2)*2/941, 1-y*2/941

    def box(self, x, y, width, height):
        a, b = self.point(x, y+height), self.point(x+width, y)
        return a[0], b[0], a[1], b[1]

    def fill(self, x, y, width, height, color, radius=10):
        node = rounded_panel(self.layout, 'menu-fill', self.box(x, y, width, height), color, radius*2/941)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def place_label(self, text, x, y, size, color=INK, *, bold=False):
        node = self.label(text, 0, 0, size, color, bold=bold, parent=self.layout)
        node.setPos(*self.point(x, y))
        return node

    def button(self, index, title, subtitle, x, y, width, height, *, footer=False, hero=False):
        unit = 2/941
        accent, _tint, tag = TILE_THEMES.get(index, (ORANGE, CREAM, ''))
        radius = 10 if footer else 14 if hero else 12
        self.fill(x+1, y+3, width, height, SHADOW, radius)
        if not hero:
            self.fill(x-1, y-1, width+2, height+2, BORDER, radius+1)
        if hero:
            self.edges[index] = self.fill(x-2.5, y-2.5, width+5, height+5, theme.AMBER, radius+2)
        elif footer:
            self.edges[index] = self.fill(x-1.5, y-1.5, width+3, height+3, ORANGE, radius+1.5)
        else:
            self.edges[index] = self.fill(x-2, y-2, width+4, height+4, accent, radius+2)
        geom = rounded_panel(self.layout, 'menu-control',
            (-width*unit/2, width*unit/2, -height*unit/2, height*unit/2), WHITE, radius*unit)
        geom.detachNode()
        px, pz = self.point(x+width/2, y+height/2)
        if hero:
            tx, ty = (-width/2+24)*unit, 2*unit
            t_scale = 33*unit
        elif footer:
            tx, ty = 0, -6*unit
            t_scale = 16*unit
        else:
            tx, ty = (-width/2+18)*unit, (0 if subtitle else -8)*unit
            t_scale = 22*unit
        node = DirectButton(parent=self.layout, text=title, text_font=self.font if not footer else self.regular,
            text_fg=WHITE if hero else INK, text_scale=t_scale,
            text_align=TextNode.ACenter if footer else TextNode.ALeft, text_pos=(tx, ty), pos=(px, 0, pz),
            frameSize=(-width*unit/2, width*unit/2, -height*unit/2, height*unit/2),
            frameColor=(0, 0, 0, 0), geom=geom, relief=DGG.FLAT, pressEffect=False,
            command=lambda: self.activate(index))
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.bind(DGG.ENTER, lambda event, i=index: self.select(i))
        node.bind(DGG.B1PRESS, lambda event: self.confirm_action())
        self.buttons[index] = node

        if hero:
            # 落日赤陶主卡内的暖金角标与箭头。
            rounded_panel(node, 'hero-ribbon',
                          (-width*unit/2, width*unit/2, height*unit/2-5*unit, height*unit/2),
                          theme.AMBER, 0)
            self.label('SEASON 01  ·  CONTINUE', tx/unit, -40, 12, (1, .92, .80, .95), bold=True, parent=node)
            self.label('出发 →', width/2-82, 26, 18, (1, .96, .88, 1), bold=True, parent=node)
        elif not footer and tag:
            # 每张功能卡顶部配独立色带 + 小号英文赛车分类标，层次丰富饱满。
            rounded_panel(node, 'tile-stripe',
                          (-width*unit/2+14*unit, -width*unit/2+52*unit, height*unit/2-11*unit, height*unit/2-7*unit),
                          accent, 2*unit)
            t_node = self.label(tag, tx/unit, -28, 11, accent, bold=True, parent=node)
            self.tags[index] = t_node

        if subtitle is not None:
            sub = self.label(subtitle, tx/unit, 32 if hero else 28, 18 if hero else 14,
                             (1, .95, .88, .96) if hero else MUTED, parent=node)
            self.subtitles[index] = sub
            if index == 0:
                self.time_goal = sub

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
            keep = (self.notice, self.stars, self.credits, self.car_name, self.vehicle_note)
            for widget in keep:
                widget.reparentTo(self.home)
            for widget in self.widgets:
                if widget not in keep:
                    widget.destroy()
            self.widgets = list(keep)
            for button in self.buttons:
                button.destroy()
            self.layout.removeNode()
        self.layout = self.home.attachNewNode('menu-layout')
        self.buttons, self.edges = [None]*len(self.actions), [None]*len(self.actions)
        self.subtitles, self.tags = {}, {}

        margin = self.width*.030
        panel_w = min(506., max(400., self.width*.32))
        pad = 22
        inner = panel_w-2*pad

        # ── 左侧暖阳画报主控卡（保留最顺手的左控右展构图，彻底升级为暖色丰富杂志排版）──
        card_top, card_h = 34, 872
        self.fill(margin+3, card_top+5, panel_w, card_h, SHADOW, 18)
        self.fill(margin-1, card_top-1, panel_w+2, card_h+2, BORDER, 19)
        self.fill(margin, card_top, panel_w, card_h, GLASS, 18)

        # 顶部复古 GT 赛车三色涂装饰带（落日赤陶 · 金盏琥珀 · 地中海青）。
        stripe_y = card_top+18
        seg_w = inner/3
        self.fill(margin+pad, stripe_y, seg_w-3, 5, ORANGE, 2.5)
        self.fill(margin+pad+seg_w+1.5, stripe_y, seg_w-3, 5, theme.AMBER, 2.5)
        self.fill(margin+pad+seg_w*2+3, stripe_y, seg_w-3, 5, theme.SEA, 2.5)

        brand = self.place_label('COASTAL DRIVE', margin+pad, card_top+68, 34, INK, bold=True)
        brand['font'] = self.display_font
        self.place_label('第一季 · 暖阳海岸驾驶', margin+pad, card_top+98, 17, MUTED)

        # 星级暖金胶囊徽章放在左卡右上角，平衡呼吸感。
        star_w = 122
        star_x = margin+panel_w-pad-star_w
        self.fill(star_x, card_top+42, star_w, 36, theme.AMBER_TINT, 18)
        self.fill(star_x-1, card_top+41, star_w+2, 38, (0.87, 0.72, 0.45, .85), 19)
        self.fill(star_x, card_top+42, star_w, 36, theme.AMBER_TINT, 18)

        # 主英雄行动卡：继续赛季（落日赤陶 + 暖金顶边）。
        self.button(self.continue_index, '继续赛季', next_name or '海岸杯决赛',
                    margin+pad, card_top+122, inner, 126, hero=True)

        # 2×3 丰富多色标签功能磁贴（比单列长菜单更直观、更饱满、更有赛车杂志质感）。
        tile_gap = 12
        tile_w = (inner-tile_gap)/2
        tile_h = 132
        grid_top = card_top+268
        has_highway = 8 in self.order
        items = ((2, '生涯赛事', '章节奖牌与解锁'),
                 (3, '海岸车库', '选车 · 涂装 · 改装'),
                 (1, '滨海自由驾驶', '阳光环路巡游'),
                 (8, '无限高速', '自由 · 挑战 · 课题') if has_highway else (0, '计时挑战', old_goal or '预算 · 用时与油耗'),
                 (0, '计时挑战', old_goal or '预算 · 用时与油耗') if has_highway else (6, '专家试验台', '动力学仿真 · A/B'),
                 (6, '专家试验台', '动力学仿真 · A/B'))
        tile_count = 6 if has_highway else 5
        for pos_i, (idx, title, sub) in enumerate(items[:tile_count]):
            col, row = pos_i % 2, pos_i // 2
            w = inner if (not has_highway and pos_i == 4) else tile_w
            x = margin+pad+col*(tile_w+tile_gap)
            y = grid_top+row*(tile_h+tile_gap)
            self.button(idx, title, sub, x, y, w, tile_h)

        # 左卡底部整合三枚暖杏仁工具按钮（无需底部黑通栏）。
        foot_y = card_top+card_h-88
        self.fill(margin+pad, foot_y-14, inner, 1, BORDER, 0)
        fw = (inner-2*10)/3
        self.button(7, '驾驶辅助 F2', None, margin+pad, foot_y, fw, 42, footer=True)
        self.button(4, '声音设置', None, margin+pad+fw+10, foot_y, fw, 42, footer=True)
        self.button(5, '退出游戏', None, margin+pad+(fw+10)*2, foot_y, fw, 42, footer=True)
        self.driving_mode_button = self.buttons[7]
        self.place_label('↑ ↓ ← → 选择   ·   Enter 确认   ·   F2 辅助', margin+pad, card_top+card_h-18, 14, MUTED)

        # ── 右侧全高日光车库展台 + 右上暖沙象牙车型铭牌 ──
        badge_w = 310
        badge_x = self.width-margin-badge_w
        self.fill(badge_x+2, 39, badge_w, 86, SHADOW, 14)
        self.fill(badge_x-1, 33, badge_w+2, 88, BORDER, 15)
        self.fill(badge_x, 34, badge_w, 86, GLASS, 14)
        self.fill(badge_x+badge_w-6, 48, 6, 58, ORANGE, 3)

        for node, x, y, right in (
            (self.stars, star_x+star_w/2, card_top+67, False),
            (self.credits, self.width-margin, 140, True),
            (self.car_name, self.width-margin-24, 72, True),
            (self.vehicle_note, self.width-margin-24, 102, True),
            (self.notice, margin+panel_w+28, 886, False),
        ):
            node.reparentTo(self.layout)
            node.setPos(*self.point(x, y))
            node.textNode.setAlign(TextNode.ACenter if node is self.stars else
                                   TextNode.ARight if right else TextNode.ALeft)

        car_left = margin+panel_w+14
        self.car_box = self.box(car_left, 140, self.width-margin-car_left, 740)
        if owns_car:
            self.vehicle_view.show(self.home, self.car_box, self.vehicle_view.base.workspace_vehicle, studio=True)
            self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.select(self.selected)

    def show_home(self, progress, vehicle, continuation):
        self.home.show()
        self.stars.setText(f'★ {progress.stars}/18')
        self.subtitles[self.continue_index].setText(continuation)
        self.credits.setText('')
        car = next(car for car in garage_cars(vehicle) if car.design_id == vehicle.design_id)
        self.car_name.setText(car.name)
        self.vehicle_note.setText(car.category)
        self.vehicle_view.show(self.home, self.car_box, vehicle, studio=True)
        self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.vehicle_view.highlight(None)

    def hide_home(self):
        self.home.hide()
        if self.vehicle_view.frame is not None and self.vehicle_view.frame.getParent() == self.home:
            self.vehicle_view.hide()

    def set_driving_mode(self, mode):
        self.driving_mode_button['text'] = '驾驶辅助 F2'

    def select(self, index):
        self.selected = index % len(self.buttons)
        for i, button in enumerate(self.buttons):
            focused, primary, footer = i == self.selected, i == self.continue_index, i in (7, 4, 5)
            accent, tint, _ = TILE_THEMES.get(i, (ORANGE, CREAM, ''))
            self.edges[i].show() if focused else self.edges[i].hide()
            if primary:
                button['geom_color'] = theme.ORANGE_BRIGHT if focused else ORANGE
                button['text_fg'] = WHITE
            elif focused:
                button['geom_color'] = CHARCOAL
                button['text_fg'] = (1, .97, .93, 1)
            elif footer:
                button['geom_color'] = theme.MIST
                button['text_fg'] = INK
            else:
                # 静态展示各自柔和暖色底，丰富饱满不单调！
                button['geom_color'] = tint
                button['text_fg'] = INK
            if i in self.subtitles:
                self.subtitles[i].setFg((1, .95, .88, .96) if primary else
                                        (.88, .82, .76, 1) if focused else MUTED)
            if i in self.tags:
                self.tags[i].setFg(theme.AMBER if focused else accent)

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
        for button in self.buttons:
            button.destroy()
        self.background.destroy()
        self.root.removeNode()
