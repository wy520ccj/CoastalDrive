"""当前车辆的工坊入口；玩家改装与工程课题分开呈现。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from ui.lab_widgets import rounded_panel
from ui.tire_tuning import BACKGROUND, BLUE, MUTED, SELECTED, SURFACE, TEXT, part_icon
from vehicle_designs import vehicle_design


class WorkshopGarage:
    def __init__(self, parent, font, vehicle_view, action):
        self.vehicle_view, self.action, self.selected = vehicle_view, action, 0
        self.root = DirectFrame(parent=parent, frameColor=BACKGROUND,
            frameSize=(-1.78, 1.78, -1.5, 1.5), state=DGG.NORMAL, sortOrder=105)
        self.vehicle_layer = self.root.attachNewNode('vehicle-display')
        rounded_panel(self.root, 'vehicle-note', (-1.58, -.68, .25, .68), (.98, .98, .96, .95), .035)

        def text(value, x, z, scale=.038, color=TEXT):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color,
                align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)

        text('COASTAL DRIVE', -1.58, .88, .052)
        text('海岸工坊', -.80, .88, .038, MUTED)
        text('改车', .33, .88, .045, BLUE)
        rounded_panel(self.root, 'active-tab', (.29, .59, .81, .823), BLUE, .006)
        self.vehicle = text('', -1.52, .53, .053)
        text('当前驾驶车辆', -1.52, .61, .028, MUTED)
        self.hardware = text('', -1.52, .40, .033, MUTED)
        self.hardware.textNode.setWordwrap(28)
        rounded_panel(self.root, 'parts-tray', (-1.68, 1.68, -.76, -.25), SURFACE, .04)
        text('准备本场方案', -1.53, -.35, .043)
        text('选挑战  →  调参数  →  去试车', -1.53, -.89, .033, MUTED)
        self.buttons, self.button_surfaces = [], []
        labels = ('轮胎与底盘', '制动设置', '自由试车', '方案', '参考试验  ›', '‹  主菜单')
        positions = ((-.83, -.53), (.30, -.53), (.90, .88), (1.31, .88), (1.20, -.58), (-1.32, .75))
        for index, (label, (x, z)) in enumerate(zip(labels, positions, strict=True)):
            width, height = ((1.04, .29) if index < 2 else (.34, .10) if index < 4 else (.64, .10))
            button = DirectButton(parent=self.root, text=label+('  ›' if index < 4 else ''), text_font=font,
                text_fg=TEXT, text_scale=.048 if index < 2 else .036,
                text_pos=(.07, .006) if index < 2 else (0, -.012), frameColor=(0, 0, 0, 0),
                frameSize=(-width/2, width/2, -height/2, height/2),
                pos=(x, 0, z), relief=DGG.FLAT, pressEffect=False,
                command=self.activate, extraArgs=[index])
            button.bind(DGG.ENTER, lambda event, i=index: self.select(i))
            self.buttons.append(button)
            surface = rounded_panel(button, 'button-surface',
                (-width/2, width/2, -height/2, height/2), SURFACE, .025)
            surface.detachNode()
            button['geom'] = surface
            self.button_surfaces.append(surface)
            if index < 2:
                part_icon(button, -.34, 0, brakes=index == 1, scale=.65)
                OnscreenText(parent=button, text='本关预算改装',
                    font=font, fg=MUTED, align=TextNode.ACenter, pos=(.07, -.077), scale=.029)
        text('完整车辆设置', .91, -.70, .026, MUTED)
        self.root.hide()

    def show(self, vehicle):
        self.vehicle.setText(vehicle_design(vehicle.design_id).name)
        config = vehicle.config
        self.hardware.setText(f'前轮 {config.lateral_stiffness/1000:g} kN/rad\n前轴制动 {config.front_brake_share:.0%}')
        self.vehicle_view.show(self.vehicle_layer, (-1.68, 1.68, -.20, .79), vehicle)
        self.vehicle_view.highlight(None)
        self.select(0)
        self.root.show()

    def select(self, index):
        self.selected = index % len(self.buttons)
        for i, button in enumerate(self.buttons):
            button['geom_color'] = SELECTED if i == self.selected else SURFACE
            button['text_fg'] = BLUE if i == self.selected else TEXT

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
