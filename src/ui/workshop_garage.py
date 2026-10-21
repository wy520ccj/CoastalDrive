"""当前车辆的工坊入口；玩家改装与工程课题分开呈现。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from ui.tire_tuning import AMBER, BACKGROUND, MUTED, SURFACE, TEXT
from vehicle_designs import vehicle_design


class WorkshopGarage:
    def __init__(self, parent, font, vehicle_view, action):
        self.vehicle_view, self.action, self.selected = vehicle_view, action, 0
        self.root = DirectFrame(parent=parent, frameColor=BACKGROUND,
            frameSize=(-1.78, 1.78, -1.5, 1.5), state=DGG.NORMAL, sortOrder=105)

        def text(value, x, z, scale=.038, color=TEXT):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color,
                align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)

        text('COASTAL DRIVE', -1.56, .87, .048, AMBER)
        text('海岸工坊', -.56, .87, .045)
        text('改装车辆', -1.56, .61, .075)
        self.vehicle = text('', -1.56, -.51, .045, MUTED)
        self.hardware = text('', -1.56, -.63, .034, MUTED)
        text('先试原车，再换一个零件，回到同一场地看差别。', -1.56, -.77, .035)
        self.buttons = []
        labels = ('前轮配方', '制动分配', '去试车场', '我的方案', '工程课题', '返回主菜单')
        positions = ((.99, .39), (.99, .12), (.99, -.23), (.99, -.47), (.60, -.80), (1.30, -.80))
        for index, (label, (x, z)) in enumerate(zip(labels, positions, strict=True)):
            compact = index >= 4
            button = DirectButton(parent=self.root, text=label+('  ›' if index < 4 else ''), text_font=font,
                text_fg=TEXT, text_scale=.054 if not compact else .039,
                text_pos=(0, -.016), frameColor=SURFACE,
                frameSize=(-.53, .53, -.09, .09) if not compact else (-.32, .32, -.055, .055),
                pos=(x, 0, z), relief=DGG.FLAT, pressEffect=False,
                command=self.activate, extraArgs=[index])
            button.bind(DGG.ENTER, lambda event, i=index: self.select(i))
            self.buttons.append(button)
        text('转向响应', .52, .25, .036, MUTED)
        text('前后轮刹车的分配', .52, -.02, .036, MUTED)
        text('自由试驾与驾驶挑战', .52, -.37, .036, MUTED)
        text('↑ ↓ 选择 · Enter进入 · Esc返回', -1.56, -.90, .031, MUTED)
        self.root.hide()

    def show(self, vehicle):
        self.vehicle.setText(vehicle_design(vehicle.design_id).name)
        config = vehicle.config
        self.hardware.setText(f'当前前轮 {config.lateral_stiffness/1000:g} kN/rad   /   前轴制动 {config.front_brake_share:.0%}')
        self.vehicle_view.show(self.root, (-1.62, .30, -.39, .50), vehicle)
        self.vehicle_view.highlight(None)
        self.select(0)
        self.root.show()

    def select(self, index):
        self.selected = index % len(self.buttons)
        for i, button in enumerate(self.buttons):
            button['frameColor'] = AMBER if i == self.selected else SURFACE
            button['text_fg'] = BACKGROUND if i == self.selected else TEXT

    def activate(self, index):
        self.hide()
        self.action(index)

    def key(self, key):
        if key in ('arrow_up', 'arrow_left', 'w', 'a'):
            self.select(self.selected-1)
        elif key in ('arrow_down', 'arrow_right', 's', 'd'):
            self.select(self.selected+1)
        elif key == 'enter':
            self.activate(self.selected)
        elif key == 'escape':
            self.activate(5)

    def hide(self):
        self.root.hide()
        self.vehicle_view.hide()
