"""车库首页：通透沉浸式车库画廊、左侧深海毛玻璃导航与实时 3D 展车。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career_garage import garage_cars
from ui import theme
from ui.lab_widgets import rounded_panel

WHITE = theme.TEXT_LIGHT
SUB = theme.TEXT_SUB
ORANGE = theme.ORANGE
DARK_BAR = theme.SLATE_BAR
GLASS = theme.SLATE_GLASS
CARD = theme.SLATE_CARD
CARD_HI = theme.SLATE_CARD_HI
BORDER = theme.SLATE_BORDER


class MainMenu:
    def __init__(self, parent, loader, body_font, display_font, actions, *, vehicle_view, confirm_action,
                 continue_action, driving_mode_action=None, lab_action=None, highway_action=None):
        self.root = parent.attachNewNode('main-menu')
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        # 旧工具页仍使用原父节点；首页不随这些工具页整体缩小。
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
        self.widgets, self.subtitles = [], {}
        self.buttons = []
        self.textures = tuple(loader.loadTexture(theme.asset_filename(f'components/button-{state}.png'))
                              for state in ('normal', 'pressed', 'hover', 'disabled'))
        self.background = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 1),
            frameTexture=loader.loadTexture(theme.asset_filename('backgrounds/garage-coastal-v2.png')),
            frameSize=(-16/9, 16/9, -1, 1), sortOrder=-10, state=DGG.DISABLED)
        self.notice = self.label('', 0, 0, 17, (1, .84, .64, 1))
        self.stars = self.label('', 0, 0, 24, theme.GOLD, bold=True)
        self.credits = self.label('', 0, 0, 20, SUB)
        self.car_name = self.label('', 0, 0, 28, WHITE, bold=True)
        self.vehicle_note = self.label('', 0, 0, 18, SUB)
        self.time_goal = None
        self.resize(vehicle_view.base.getAspectRatio())
        self.root.hide()

    def label(self, text, x, y, size, color=WHITE, *, bold=False, parent=None):
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

    def fill(self, x, y, width, height, color, radius=6):
        node = rounded_panel(self.layout, 'menu-fill', self.box(x, y, width, height), color, radius*2/941)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def place_label(self, text, x, y, size, color=WHITE, *, bold=False):
        node = self.label(text, 0, 0, size, color, bold=bold, parent=self.layout)
        node.setPos(*self.point(x, y))
        return node

    def button(self, index, title, subtitle, x, y, width, height, *, footer=False):
        unit = 2/941
        # 左侧聚焦指示光条或底栏高亮描边，清晰无遮挡。
        if footer:
            self.edges[index] = self.fill(x-1.5, y-1.5, width+3, height+3, ORANGE, 8)
        elif index == self.continue_index:
            self.edges[index] = self.fill(x-2, y-2, width+4, height+4, WHITE, 10)
        else:
            self.edges[index] = self.fill(x, y+10, 4.5, height-20, ORANGE, 2)
        geom = rounded_panel(self.layout, 'menu-control',
            (-width*unit/2, width*unit/2, -height*unit/2, height*unit/2), (1, 1, 1, 1),
            (8 if index == self.continue_index else 6)*unit)
        geom.detachNode()
        tx = 0 if footer else (-width/2+24)*unit
        px, pz = self.point(x+width/2, y+height/2)
        node = DirectButton(parent=self.layout, text=title, text_font=self.font if not footer else self.regular,
            text_fg=WHITE, text_scale=(19 if footer else 34 if index == self.continue_index else 24)*unit,
            text_align=TextNode.ACenter if footer else TextNode.ALeft,
            text_pos=(tx, (9 if subtitle is not None else -7)*unit), pos=(px, 0, pz),
            frameSize=(-width*unit/2, width*unit/2, -height*unit/2, height*unit/2),
            frameColor=(0, 0, 0, 0), geom=geom, relief=DGG.FLAT, pressEffect=False,
            command=lambda: self.activate(index))
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.bind(DGG.ENTER, lambda event, i=index: self.select(i))
        node.bind(DGG.B1PRESS, lambda event: self.confirm_action())
        self.buttons[index] = node
        if subtitle is not None:
            sub = self.label(subtitle, tx/unit, 26 if index == self.continue_index else 23,
                             19 if index == self.continue_index else 16,
                             WHITE if index == self.continue_index else SUB, parent=node)
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

        margin = self.width*.030
        panel_w = min(460., max(360., self.width*.295))
        pad = 24
        inner = panel_w-2*pad

        # 顶栏与底栏：深海毛玻璃通栏 + 精致底边细线。
        self.fill(0, 0, self.width, 64, DARK_BAR, 0)
        self.fill(0, 64, self.width, 1.5, BORDER, 0)
        self.fill(0, 868, self.width, 73, DARK_BAR, 0)
        self.fill(0, 867, self.width, 1.5, BORDER, 0)

        brand = self.place_label('COASTAL DRIVE', margin, 42, 26, WHITE, bold=True)
        brand['font'] = self.display_font
        self.fill(margin+248, 20, 2, 24, ORANGE, 1)
        self.place_label('第一季 · 海岸驾驶', margin+266, 40, 19, SUB)

        # 左侧悬浮深海毛玻璃导航卡（不再用惨白大色块切碎车库背景）。
        card_top, card_h = 94, 744
        self.fill(margin-1.5, card_top-1.5, panel_w+3, card_h+3, BORDER, 13)
        self.fill(margin, card_top, panel_w, card_h, GLASS, 12)
        self.place_label('驾驶中心', margin+pad, card_top+52, 34, WHITE, bold=True)
        self.place_label('选择赛事模式或进入专家试验台', margin+pad, card_top+82, 16, SUB)

        self.button(self.continue_index, '继续赛季', next_name, margin+pad, card_top+106, inner, 108)
        entries = {2: '生涯赛事', 3: '我的车库', 1: '滨海自由驾驶', 8: '无限高速',
                   0: '计时挑战', 6: '专家试验台'}
        for row, index in enumerate(i for i in self.order[1:] if i in entries):
            y = card_top+234+row*80
            self.button(index, entries[index], old_goal if index == 0 else None,
                        margin+pad, y, inner, 68)

        # 底部操作指引与快捷入口。
        self.place_label('↑↓ 选择   ·   Enter 确认   ·   F2 驾驶辅助', margin, 912, 16, SUB)
        self.button(7, '驾驶辅助 F2', None, self.width-margin-454, 884, 152, 42, footer=True)
        self.button(4, '声音设置', None, self.width-margin-288, 884, 136, 42, footer=True)
        self.button(5, '退出游戏', None, self.width-margin-138, 884, 138, 42, footer=True)
        self.driving_mode_button = self.buttons[7]

        # 右上角车辆铭牌悬浮卡。
        badge_w = 328
        badge_x = self.width-margin-badge_w
        self.fill(badge_x-1.5, 94-1.5, badge_w+3, 94+3, BORDER, 11)
        self.fill(badge_x, 94, badge_w, 94, GLASS, 10)
        self.fill(badge_x+badge_w-5, 110, 5, 62, ORANGE, 2)
        for node, x, y, right in (
            (self.stars, self.width-margin, 41, True),
            (self.credits, self.width-margin-160, 41, True),
            (self.car_name, self.width-margin-22, 134, True),
            (self.vehicle_note, self.width-margin-22, 168, True),
            (self.notice, margin+panel_w+26, 822, False),
        ):
            node.reparentTo(self.layout)
            node.setPos(*self.point(x, y))
            node.textNode.setAlign(TextNode.ARight if right else TextNode.ALeft)

        car_left = margin+panel_w+12
        self.car_box = self.box(car_left, 198, self.width-margin-car_left, 650)
        if owns_car:
            self.vehicle_view.show(self.home, self.car_box, self.vehicle_view.base.workspace_vehicle, studio=True)
            self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.select(self.selected)

    def show_home(self, progress, vehicle, continuation):
        self.home.show()
        self.stars.setText(f'★  {progress.stars} / 18 星')
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
            self.edges[i].show() if focused else self.edges[i].hide()
            if primary:
                button['geom_color'] = theme.ORANGE_BRIGHT if focused else ORANGE
            elif footer:
                button['geom_color'] = CARD_HI if focused else CARD
            else:
                button['geom_color'] = CARD_HI if focused else (.10, .14, .19, .58)
            button['text_fg'] = WHITE if (primary or focused) else (.86, .90, .94, 1)
            if i in self.subtitles:
                self.subtitles[i].setFg((1, .95, .90, .95) if primary else SUB)

    def move(self, direction):
        if self.selected in (7, 4, 5):
            self.select(6 if direction < 0 else self.continue_index)
        else:
            self.select(self.order[(self.order.index(self.selected)+direction) % len(self.order)])

    def horizontal(self, direction):
        footer = (7, 4, 5)
        if self.selected in footer:
            self.select(footer[(footer.index(self.selected)+direction) % len(footer)])

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
