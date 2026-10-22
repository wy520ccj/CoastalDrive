"""车库首页：固定的驾驶入口、真实车辆展示和底部设置。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career_garage import garage_cars
from ui import theme
from ui.lab_widgets import rounded_panel

INK = (.04, .07, .12, 1)
GRAY = (.35, .39, .46, 1)
WHITE = (1, 1, 1, 1)
ORANGE = (1, .31, .12, 1)
DARK = (.04, .055, .075, .86)


class MainMenu:
    def __init__(self, parent, loader, body_font, display_font, actions, *, vehicle_view, confirm_action,
                 driving_mode_action=None, lab_action=None, journey_action=None):
        self.root = parent.attachNewNode('main-menu')
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        # 旧工具页仍使用原父节点；首页不随这些工具页整体缩小。
        self.content = self.root.attachNewNode('menu-content')
        self.home = self.root.attachNewNode('menu-home')
        self.loader, self.font, self.display_font = loader, body_font, display_font
        self.regular = theme.load_font('fonts/SourceHanSansSC-Regular.otf')
        self.icon_font = theme.load_font('fonts/Tabler-Menu.ttf')
        self.vehicle_view = vehicle_view
        self.confirm_action = confirm_action
        self.actions = (*actions, lab_action, driving_mode_action)
        self.order = (2, 3, 1, 0, 6, 7, 4, 5)
        if journey_action is not None:
            self.actions = (*self.actions, journey_action)
            self.order = (2, 3, 1, 0, 6, 8, 7, 4, 5)
        self.selected, self.aspect = 2, None
        self.widgets, self.subtitles, self.symbols = [], {}, {}
        self.buttons = []
        self.textures = tuple(loader.loadTexture(theme.asset_filename(f'components/button-{state}.png'))
                              for state in ('normal', 'pressed', 'hover', 'disabled'))
        self.background = DirectFrame(parent=self.root, frameColor=WHITE,
            frameTexture=loader.loadTexture(theme.asset_filename('backgrounds/garage-coastal-v2.png')),
            frameSize=(-16/9, 16/9, -1, 1), sortOrder=-10, state=DGG.DISABLED)
        self.notice = self.label('', 0, 0, 16, (1, .86, .70, 1))
        self.stars = self.label('', 0, 0, 23, (1, .75, .31, 1))
        self.credits = self.label('', 0, 0, 23, WHITE)
        self.car_name = self.label('', 0, 0, 28, WHITE, bold=True)
        self.vehicle_note = self.label('', 0, 0, 17, WHITE)
        self.time_goal = None
        self.resize(16/9)
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

    def fill(self, x, y, width, height, color, radius=4):
        return rounded_panel(self.layout, 'menu-fill', self.box(x, y, width, height), color, radius*2/941)

    def place_label(self, text, x, y, size, color=INK, *, bold=False):
        node = self.label(text, 0, 0, size, color, bold=bold, parent=self.layout)
        node.setPos(*self.point(x, y))
        return node

    def button(self, index, title, subtitle, x, y, width, height, *, icon=None, footer=False):
        unit = 2/941
        self.edges[index] = self.fill(x-2, y-2, width+4, height+4, ORANGE)
        geom = rounded_panel(self.layout, 'menu-control',
            (-width*unit/2, width*unit/2, -height*unit/2, height*unit/2), WHITE, 4*unit)
        geom.detachNode()
        tx = 0 if footer else (-width/2+110 if icon else -width/2+22)*unit
        px, pz = self.point(x+width/2, y+height/2)
        node = DirectButton(parent=self.layout, text=title, text_font=self.font,
            text_fg=INK, text_scale=(20 if footer else 27)*unit,
            text_align=TextNode.ACenter if footer else TextNode.ALeft,
            text_pos=(tx, -7*unit if footer else 7*unit), pos=(px, 0, pz),
            frameSize=(-width*unit/2, width*unit/2, -height*unit/2, height*unit/2),
            frameColor=(0, 0, 0, 0), geom=geom, relief=DGG.FLAT, pressEffect=False,
            command=lambda: self.activate(index))
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.bind(DGG.ENTER, lambda event, i=index: self.select(i))
        node.bind(DGG.B1PRESS, lambda event: self.confirm_action())
        self.buttons[index] = node
        if subtitle is not None:
            sub = self.label(subtitle, tx/unit, 27, 19, GRAY, parent=node)
            self.subtitles[index] = sub
            if index == 0:
                self.time_goal = sub
        if icon is not None:
            symbol = self.label(chr(icon), -width/2+29, 18, 50, INK, parent=node)
            symbol['font'] = self.icon_font
            arrow = self.label('›', width/2-33, 9, 34, INK, parent=node)
            self.symbols[index] = (symbol, arrow)

    def resize(self, aspect):
        if self.aspect == aspect:
            return
        owns_car = self.vehicle_view.frame is not None and self.vehicle_view.frame.getParent() == self.home
        old_goal = '' if self.time_goal is None else self.time_goal.getText()
        self.aspect, self.width = aspect, 941*aspect
        self.content.setScale(min(1, aspect/(16/9)))
        self.background['frameSize'] = (-aspect, aspect, -1, 1)
        texture = self.background['frameTexture']
        crop = aspect/(texture.getXSize()/texture.getYSize())
        self.background.setTexScale(TextureStage.getDefault(), min(1, crop), min(1, 1/crop))
        self.background.setTexOffset(TextureStage.getDefault(), max(0, (1-crop)/2), max(0, (1-1/crop)/2))
        # 保留外部可更新的读数，其余构图只在画幅变化时重建。
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
        self.subtitles, self.symbols = {}, {}
        margin, panel_width = self.width*.031, min(462, self.width*.355)
        inset, inner = 24, panel_width-48
        self.fill(0, 0, self.width, 74, DARK, 0)
        self.fill(0, 860, self.width, 81, DARK, 0)
        brand = self.place_label('COASTAL DRIVE', margin+10, 50, 34, WHITE, bold=True)
        brand['font'] = self.display_font
        if aspect > 1.5:
            self.place_label('/  海岸驾驶', margin+267, 49, 21, WHITE)
        self.fill(margin, 122, panel_width, 706, (.98, .98, .99, .96))
        self.place_label('出发', margin+28, 194, 48, bold=True)
        self.place_label('选一场比赛，或开车去兜风', margin+28, 231, 20)
        for index, title, subtitle, y, height, icon in (
            (2, '海岸生涯', '赛事 · 赢取星级与积分', 254, 96, 0xeb45),
            (3, '我的车库', '选车 · 升级 · 车身颜色', 366, 96, 0xebbb),
            (1, '滨海自由驾驶', '无计时 · 自由探索', 478, 96, 0xef3d),
            (0, '计时挑战', old_goal, 590, 96, 0xff9b),
            (6, '专家试验台', '车辆实验与曲线', 728, 78, 0xee2f)):
            self.button(index, title, subtitle, margin+inset, y, inner, height, icon=icon)
        self.fill(margin+24, 707, inner, 1, (.75, .78, .82, 1), 0)
        self.button(7, '驾驶辅助  F2', None, self.width-520, 883, 183, 42, footer=True)
        self.button(4, '声音设置', None, self.width-313, 883, 143, 42, footer=True)
        self.button(5, '退出游戏', None, self.width-146, 883, 116, 42, footer=True)
        self.driving_mode_button = self.buttons[7]
        if len(self.actions) > 8:
            self.button(8, '生涯车库', None, margin+panel_width+25, 777, 150, 42, footer=True)
        for text, x, width in (('↑', margin, 46), ('↓', margin+60, 46), ('Enter', margin+196, 75)):
            self.fill(x, 881, width, 40, (.95, .96, 1, .15))
            self.place_label(text, x+11, 911, 21, WHITE)
        self.place_label('选择', margin+124, 911, 20, WHITE)
        self.place_label('确认', margin+287, 911, 20, WHITE)
        for node, x, y, right in ((self.stars, self.width-350, 49, False),
                (self.credits, self.width-55, 49, True), (self.car_name, self.width-margin, 191, True),
                (self.vehicle_note, self.width-margin, 228, True), (self.notice, margin+24, 849, False)):
            node.reparentTo(self.layout)
            node.setPos(*self.point(x, y))
            node.textNode.setAlign(TextNode.ARight if right else TextNode.ALeft)
        self.place_label('当前车辆', self.width-margin-180, 148, 20, WHITE)
        self.car_box = self.box(margin+panel_width+18, 220, self.width-margin*2-panel_width-18, 620)
        if owns_car:
            self.vehicle_view.show(self.home, self.car_box, self.vehicle_view.base.workspace_vehicle, studio=True)
            self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.select(self.selected)

    def show_home(self, progress, vehicle):
        self.stars.setText(f'★  {progress.stars} / 18 星')
        self.credits.setText(f'{progress.credits} 积分')
        car = next(car for car in garage_cars(vehicle) if car.design_id == vehicle.design_id)
        self.car_name.setText(car.name)
        self.vehicle_note.setText(car.category)
        self.vehicle_view.show(self.home, self.car_box, vehicle, studio=True)
        self.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        self.vehicle_view.highlight(None)

    def hide_home(self):
        if self.vehicle_view.frame is not None and self.vehicle_view.frame.getParent() == self.home:
            self.vehicle_view.hide()

    def set_driving_mode(self, mode):
        self.driving_mode_button['text'] = '驾驶辅助  F2'

    def select(self, index):
        self.selected = index % len(self.buttons)
        for i, button in enumerate(self.buttons):
            focused, primary, footer = i == self.selected, i == 2, i in (7, 4, 5, 8)
            self.edges[i].show() if focused else self.edges[i].hide()
            button['geom_color'] = ORANGE if primary else ((1, .90, .85, 1) if focused else (.98, .98, .99, 1))
            if footer:
                button['geom_color'] = (.25, .27, .30, 1) if focused else (.10, .12, .15, .80)
            color = WHITE if primary or footer else INK
            button['text_fg'] = color
            if i in self.subtitles:
                self.subtitles[i]['fg'] = WHITE if primary else GRAY
            for symbol in self.symbols.get(i, ()):
                symbol['fg'] = color

    def move(self, direction):
        if self.selected in (7, 4, 5):
            self.select(6 if direction < 0 else 2)
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
