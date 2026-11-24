"""日光展厅首页：全屏通透海岸车库 + 顶部轻盈悬浮胶囊 + 底部 Forza/GT 风格横向 Bento 卡片坞。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career_garage import garage_cars
from ui import theme
from ui.lab_widgets import rounded_panel

WHITE = (1, 1, 1, 1)
INK = theme.INK
CHARCOAL = theme.CHARCOAL
MUTED = theme.MUTED
ORANGE = theme.ORANGE
GLASS = theme.GLASS_LIGHT
BORDER = theme.HAIRLINE
SHADOW = theme.SHADOW
# 保留旧导入名兼容 menu_layout/driving_summary 等模块。
DARK = CHARCOAL
GRAY = MUTED


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
        self.order = (2, 3, 0, 1, 6, 7, 4, 5)
        if highway_action is not None:
            self.actions = (*self.actions, highway_action)
            self.order = (2, 3, 0, 1, 8, 6, 7, 4, 5)
        self.continue_index = len(self.actions)
        self.actions = (*self.actions, continue_action)
        self.order = (self.continue_index, *self.order)
        self.selected, self.aspect = self.continue_index, None
        self.widgets, self.subtitles = [], {}
        self.buttons = []
        self.textures = tuple(loader.loadTexture(theme.asset_filename(f'components/button-{state}.png'))
                              for state in ('normal', 'pressed', 'hover', 'disabled'))
        self.background = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=loader.loadTexture(theme.asset_filename('backgrounds/garage-coastal-v2.png')),
            frameSize=(-16/9, 16/9, -1, 1), sortOrder=-10, state=DGG.DISABLED)
        self.notice = self.label('', 0, 0, 16, ORANGE, bold=True)
        self.stars = self.label('', 0, 0, 20, theme.GOLD, bold=True)
        self.credits = self.label('', 0, 0, 16, MUTED)
        self.car_name = self.label('', 0, 0, 26, INK, bold=True)
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

    def button(self, index, title, subtitle, x, y, width, height, *, pill=False, hero=False):
        unit = 2/941
        radius = 20 if pill else 14 if hero else 12
        # 柔和悬浮投影 + 精致高光描边，复刻 Forza / GT 卡片立体感。
        self.fill(x+1, y+4, width, height, SHADOW, radius)
        if not hero:
            self.fill(x-1, y-1, width+2, height+2, BORDER, radius+1)
        if hero:
            self.edges[index] = self.fill(x-2.5, y-2.5, width+5, height+5, WHITE, radius+2)
        elif pill:
            self.edges[index] = self.fill(x-2, y-2, width+4, height+4, ORANGE, radius+2)
        else:
            self.edges[index] = self.fill(x+16, y, width-32, 4.5, ORANGE, 2)
        geom = rounded_panel(self.layout, 'menu-control',
            (-width*unit/2, width*unit/2, -height*unit/2, height*unit/2), WHITE, radius*unit)
        geom.detachNode()
        px, pz = self.point(x+width/2, y+height/2)
        if hero:
            tx, ty = (-width/2+26)*unit, (16 if subtitle else -8)*unit
            t_scale = 36*unit
        elif pill:
            tx, ty = 0, -6*unit
            t_scale = 17*unit
        else:
            tx, ty = (-width/2+22)*unit, (10 if subtitle else -7)*unit
            t_scale = 23*unit
        node = DirectButton(parent=self.layout, text=title, text_font=self.font if not pill else self.regular,
            text_fg=WHITE if hero else INK, text_scale=t_scale,
            text_align=TextNode.ACenter if pill else TextNode.ALeft, text_pos=(tx, ty), pos=(px, 0, pz),
            frameSize=(-width*unit/2, width*unit/2, -height*unit/2, height*unit/2),
            frameColor=(0, 0, 0, 0), geom=geom, relief=DGG.FLAT, pressEffect=False,
            command=lambda: self.activate(index))
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.bind(DGG.ENTER, lambda event, i=index: self.select(i))
        node.bind(DGG.B1PRESS, lambda event: self.confirm_action())
        self.buttons[index] = node
        if hero:
            self.label('SEASON 01  ·  CONTINUE', tx/unit, -52, 13, (1, .90, .86, .92), bold=True, parent=node)
            self.label('出发  →', (width/2-88), 64, 18, WHITE, bold=True, parent=node)
        if subtitle is not None:
            sub_y = 20 if hero else 24
            sub_size = 19 if hero else 15
            sub = self.label(subtitle, tx/unit, sub_y, sub_size,
                             (1, .95, .93, .95) if hero else MUTED, parent=node)
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
        self.subtitles = {}

        margin = self.width*.032
        usable = self.width-2*margin

        # ── 顶部轻盈悬浮元素（无厚重通栏，让阳光与天空完整呼吸）──
        brand_w = 340
        self.fill(margin+1, 31, brand_w, 56, SHADOW, 14)
        self.fill(margin-1, 27, brand_w+2, 58, BORDER, 15)
        self.fill(margin, 28, brand_w, 56, GLASS, 14)
        self.fill(margin+14, 41, 5, 30, ORANGE, 2.5)
        brand = self.place_label('COASTAL DRIVE', margin+30, 65, 27, INK, bold=True)
        brand['font'] = self.display_font
        self.place_label('S1', margin+294, 63, 16, ORANGE, bold=True)

        # 左上第二层：轻盈悬浮当前座驾名牌（不压车身）。
        car_badge_w = 248
        self.fill(margin+1, 102, car_badge_w, 66, SHADOW, 12)
        self.fill(margin-1, 98, car_badge_w+2, 68, BORDER, 13)
        self.fill(margin, 99, car_badge_w, 66, GLASS, 12)

        # 右上悬浮胶囊群：星级徽章 + 快捷工具（驾驶辅助 / 声音 / 退出）。
        star_w = 136
        star_x = self.width-margin-460-star_w-12
        self.fill(star_x+1, 35, star_w, 42, SHADOW, 21)
        self.fill(star_x-1, 31, star_w+2, 44, BORDER, 22)
        self.fill(star_x, 32, star_w, 42, GLASS, 21)
        self.button(7, '驾驶辅助 F2', None, self.width-margin-456, 32, 148, 42, pill=True)
        self.button(4, '声音设置', None, self.width-margin-294, 32, 136, 42, pill=True)
        self.button(5, '退出游戏', None, self.width-margin-144, 32, 144, 42, pill=True)
        self.driving_mode_button = self.buttons[7]

        # ── 底部 Forza / GT 风格横向 Bento 卡片坞（上方 70% 空间完整留给 3D 展车与阳光海岸）──
        dock_top, dock_h, gap = 668, 228, 16
        hero_w = min(420., usable*.275)
        grid_x = margin+hero_w+gap
        grid_w = usable-hero_w-gap
        cols = 3
        tile_w = (grid_w-(cols-1)*gap)/cols
        tile_h = (dock_h-gap)/2

        self.button(self.continue_index, '继续赛季', next_name or '海岸杯决赛',
                    margin, dock_top, hero_w, dock_h, hero=True)

        # 2×3 精致瓷白 Bento 磁贴：核心驾驶入口清晰分明，无遮挡。
        has_highway = 8 in self.order
        top_row = ((2, '生涯赛事', '第一季 · 章节与奖牌'),
                   (3, '海岸车库', '车辆 · 车漆 · 改装'),
                   (0, '计时挑战', old_goal or '独立预算 · 圈速与油耗'))
        bot_row = (((1, '滨海自由驾驶', '阳光海岸环路巡游'),
                    (8, '无限高速', '自由 · 五公里 · 课题'),
                    (6, '专家试验台', '动力学仿真 · A/B 对比')) if has_highway else
                   ((1, '滨海自由驾驶', '阳光海岸环路巡游'),
                    (6, '专家试验台', '动力学仿真 · A/B 对比')))

        for col, (idx, title, sub) in enumerate(top_row):
            self.button(idx, title, sub, grid_x+col*(tile_w+gap), dock_top, tile_w, tile_h)
        bot_w = tile_w if has_highway else (grid_w-gap)/2
        for col, (idx, title, sub) in enumerate(bot_row):
            self.button(idx, title, sub, grid_x+col*(bot_w+gap), dock_top+tile_h+gap, bot_w, tile_h)

        # 底部细微按键指引（无重底栏）。
        self.place_label('↑ ↓ ← → 浏览   ·   Enter 确认   ·   F2 驾驶辅助', margin+4, 926, 15, (1, 1, 1, .92), bold=True)

        for node, x, y, right in (
            (self.stars, star_x+star_w/2, 60, False),
            (self.credits, self.width-margin, 95, True),
            (self.car_name, margin+20, 132, False),
            (self.vehicle_note, margin+20, 154, False),
            (self.notice, margin+hero_w+gap, 650, False),
        ):
            node.reparentTo(self.layout)
            node.setPos(*self.point(x, y))
            node.textNode.setAlign(TextNode.ACenter if node is self.stars else
                                   TextNode.ARight if right else TextNode.ALeft)

        # 全幅居中 3D 展车视口：充分享受日光车库主舞台！
        self.car_box = self.box(self.width*.14, 118, self.width*.72, 540)
        if owns_car:
            self.vehicle_view.show(self.home, self.car_box, self.vehicle_view.base.workspace_vehicle, studio=True)
            self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.select(self.selected)

    def show_home(self, progress, vehicle, continuation):
        self.home.show()
        self.stars.setText(f'★  {progress.stars} / 18')
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
            focused, primary, pill = i == self.selected, i == self.continue_index, i in (7, 4, 5)
            self.edges[i].show() if focused else self.edges[i].hide()
            if primary:
                button['geom_color'] = theme.ORANGE_BRIGHT if focused else ORANGE
                button['text_fg'] = WHITE
            elif focused:
                button['geom_color'] = CHARCOAL
                button['text_fg'] = WHITE
            elif pill:
                button['geom_color'] = GLASS
                button['text_fg'] = INK
            else:
                button['geom_color'] = GLASS
                button['text_fg'] = INK
            if i in self.subtitles:
                self.subtitles[i].setFg((1, .95, .93, .95) if primary else
                                        (.80, .82, .85, 1) if focused else MUTED)

    def move(self, direction):
        if self.selected in (7, 4, 5):
            self.select(self.continue_index if direction > 0 else 6)
        else:
            self.select(self.order[(self.order.index(self.selected)+direction) % len(self.order)])

    def horizontal(self, direction):
        pills = (7, 4, 5)
        if self.selected in pills:
            self.select(pills[(pills.index(self.selected)+direction) % len(pills)])
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
