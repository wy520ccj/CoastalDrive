"""围绕当前车辆选择零件；预览、安装、试车各有明确状态。"""

import math

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import LineSegs, TextNode

from tire_tuning import previous_path
from ui.lab_widgets import rounded_panel
from vehicle_designs import vehicle_design
from workshop import BRAKE_SHARES
from workshop_cornering import FRONT_STIFFNESS

BACKGROUND = (.97, .965, .94, 1)
SURFACE = (1., 1., .99, 1)
TEXT = (.045, .14, .27, 1)
MUTED = (.29, .39, .48, 1)
AMBER = (.93, .23, .13, 1)
SELECTED = (.84, .93, .99, 1)
BLUE = (.025, .38, .79, 1)


def part_icon(parent, x, z, *, brakes=False, scale=1.):
    """统一的轮胎/刹车盘示意；不虚构不同配方的花纹或实物。"""
    node = parent.attachNewNode('part-icon')
    node.setPos(x, 0, z)
    node.setScale(scale)
    drawing = LineSegs('wheel-and-disc')
    drawing.setThickness(3)
    drawing.setColor(*BLUE)
    for radius in (.078, .105, .136):
        for step in range(49):
            phase = step*math.pi/24
            point = (radius*math.cos(phase), 0, radius*math.sin(phase))
            drawing.moveTo(*point) if step == 0 else drawing.drawTo(*point)
    for index in range(8 if brakes else 5):
        phase = index*math.pi*2/(8 if brakes else 5)
        drawing.moveTo(.024*math.cos(phase), 0, .024*math.sin(phase))
        drawing.drawTo(.080*math.cos(phase+.18), 0, .080*math.sin(phase+.18))
    node.attachNewNode(drawing.create())
    if brakes:
        rounded_panel(node, 'caliper', (.074, .137, -.055, .055), AMBER, .018)
    return node


class TireTuningPanel:
    def __init__(self, parent, font, textures, apply, undo, back, compare, *, vehicle_view=None, drive=None,
                 navigate=None):
        self.apply, self.undo, self.back, self.compare = apply, undo, back, compare
        self.vehicle_view, self.drive = vehicle_view, drive
        self.navigate = navigate
        self.selected, self.recipe = 0, None
        self.root = DirectFrame(parent=parent, frameColor=BACKGROUND,
            frameSize=(-1.78, 1.78, -1.5, 1.5), sortOrder=112, state=DGG.NORMAL)
        self.vehicle_layer = self.root.attachNewNode('vehicle-display')
        rounded_panel(self.root, 'vehicle-note', (-1.58, -.68, .32, .68), (.98, .98, .96, .95), .035)
        rounded_panel(self.root, 'parts-tray', (-1.68, 1.68, -.79, -.24), SURFACE, .04)
        rounded_panel(self.root, 'install-summary', (1.01, 1.62, -.74, -.29), SELECTED, .035)

        def text(value, x, z, scale=.038, color=TEXT):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color,
                align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)

        text('COASTAL DRIVE', -1.58, .88, .052, TEXT)
        text('海岸工坊', -.80, .88, .038, MUTED)
        text('改车', .33, .88, .045, BLUE)
        for index, (x, label) in enumerate(((-1.53, '选择零件'), (-.96, '装到车上'), (-.39, '去试车'))):
            rounded_panel(self.root, 'step', (x-.028, x+.028, -.91, -.854), BLUE, .028)
            text(str(index+1), x-.009, -.894, .030, SURFACE)
            text(label, x+.06, -.895, .032, MUTED)
            if index < 2:
                rounded_panel(self.root, 'step-link', (x+.36, x+.48, -.884, -.88), (.69, .75, .77, 1), 0.)
        rounded_panel(self.root, 'active-tab', (.29, .59, .81, .823), BLUE, .006)
        self.title = text('前轮配方', -1.55, -.335, .045)
        self.vehicle = text('', -1.52, .60, .050)
        self.vehicle.textNode.setWordwrap(40)
        self.hardware_note = text('', -.67, -.335, .030, MUTED)
        self.preview = text('', 1.065, -.38, .032, BLUE)
        self.preview.textNode.setWordwrap(17)
        self.advice = text('', -1.52, .50, .031, MUTED)
        self.advice.textNode.setWordwrap(31)
        self.notice = text('', -1.55, -.75, .026, MUTED)
        self.notice.textNode.setWordwrap(87)
        self.buttons, self.button_surfaces, self.card_notes, self.icons, self.bars = [], [], [], [], []
        choices = [(f'{value/1000:g}', -1.25+i*.61, -.535, .565, .32)
                   for i, value in enumerate(FRONT_STIFFNESS)]
        choices.extend((('只安装', 1.17, -.70, .27, .07),
                        ('恢复原车', -.77, .75, .44, .085),
                        ('‹  返回', -1.35, .75, .42, .09),
                        ('改装前后对比', 1.29, -.89, .66, .09)))
        if drive is not None:
            choices.append(('去试车  ›', 1.315, -.57, .52, .13))
            choices.append(('取消', 1.47, -.70, .27, .07))
        if navigate is not None:
            choices.extend((('试车  ›', .90, .88, .34, .10), ('方案  ›', 1.31, .88, .34, .10)))
        for index, (label, x, z, width, height) in enumerate(choices):
            button = DirectButton(parent=self.root, text=label, text_font=font,
                text_fg=TEXT, text_scale=.045 if index < 4 else .041 if index == 8 else .034,
                text_align=TextNode.ACenter,
                text_pos=(0, -.128) if index < 4 else (0, -.011),
                frameColor=(0, 0, 0, 0), relief=DGG.FLAT, pressEffect=False,
                frameSize=(-width/2, width/2, -height/2, height/2), pos=(x, 0, z),
                command=self.activate, extraArgs=[index])
            button.bind(DGG.ENTER, lambda event, i=index: self.select(i))
            self.buttons.append(button)
            self.button_surfaces.append(rounded_panel(button, 'button-surface',
                (-width/2, width/2, -height/2, height/2), SURFACE, .025))
            self.button_surfaces[-1].detachNode()
            button['geom'] = self.button_surfaces[-1]
            if index < 4:
                self.icons.append(part_icon(button, 0, .005, scale=.68))
                self.card_notes.append(OnscreenText(parent=button, text='', font=font, fg=MUTED,
                    align=TextNode.ACenter, pos=(0, .105), scale=.026, mayChange=True))
        self.root.hide()

    def show(self, vehicle, path, label, *, topic='tires', trial_label='六门自由练习'):
        self.topic, self.original, self.recipe = topic, vehicle, None
        self.show_arguments = vehicle, path, label, trial_label
        brakes = topic == 'brakes'
        self.title.setText('制动分配' if brakes else '前轮配方')
        self.vehicle.setText(vehicle_design(vehicle.design_id).name)
        self.hardware_note.setText('前轴 / 后轴制动份额' if brakes else '前轴侧偏刚度 · kN/rad')
        self.advice.setText(('调整前后轮的制动力分配。' if brakes else '调整前轮的转向响应。')
                            +'\n试车：'+trial_label)
        if self.vehicle_view is not None:
            self.vehicle_view.show(self.vehicle_layer, (-1.68, 1.68, -.20, .79), vehicle)
            self.vehicle_view.highlight(topic)
        for index, button in enumerate(self.buttons[:4]):
            current = (vehicle.config.front_brake_share == BRAKE_SHARES[index] if brakes else
                       vehicle.config.lateral_stiffness == FRONT_STIFFNESS[index])
            button['text'] = f'{BRAKE_SHARES[index]:.0%} / {1-BRAKE_SHARES[index]:.0%}' if brakes else f'{FRONT_STIFFNESS[index]/1000:g} kN/rad'
            self.icons[index].removeNode()
            self.icons[index] = part_icon(button, 0, .005, brakes=brakes, scale=.68)
            descriptor = '' if brakes else ('低刚度', '较低', '中等', '高刚度')[index]
            self.card_notes[index].setText('已安装' if current else descriptor)
        self.installed_notes = [note.getText() for note in self.card_notes]
        value = f'前轴 {vehicle.config.front_brake_share:.0%}' if brakes else f'{vehicle.config.lateral_stiffness/1000:g} kN/rad'
        self.preview.setText('已安装\n'+value)
        self.notice.setText('选择零件查看待安装值，车辆不会立即改变。')
        self.buttons[4]['state'] = DGG.DISABLED
        if self.drive is not None:
            self.buttons[8]['state'] = DGG.NORMAL
            self.buttons[8]['text'] = '去试车  ›'
            self.buttons[9]['state'] = DGG.DISABLED
        try:
            available = previous_path(vehicle, path) is not None
        except ValueError as error:
            available = False
            self.notice.setText('原车副本引用无效：'+str(error))
        self.buttons[5]['state'] = DGG.NORMAL if available else DGG.DISABLED
        self.select(0)
        self.root.show()

    def select(self, index):
        self.selected = index % len(self.buttons)
        for i, button in enumerate(self.buttons):
            disabled = button['state'] == DGG.DISABLED
            primary = i == (8 if self.drive is not None else 4)
            active_recipe = i < 4 and self.recipe == i
            color = AMBER if primary and not disabled else SELECTED if i == self.selected or active_recipe else SURFACE
            button['geom_color'] = color
            button['text_fg'] = SURFACE if primary and not disabled else MUTED if disabled else TEXT
            if i < 4:
                self.card_notes[i]['fg'] = AMBER if active_recipe else BLUE
                self.card_notes[i].setText('待安装' if active_recipe else self.installed_notes[i])

    def activate(self, index):
        if self.buttons[index]['state'] == DGG.DISABLED:
            return
        if index < len(FRONT_STIFFNESS):
            self.recipe = index
            if self.topic == 'brakes':
                old, new = self.original.config.front_brake_share, BRAKE_SHARES[index]
                self.preview.setText(f'已安装 {old:.0%}\n待安装 {new:.0%}')
            else:
                old, new = self.original.config.lateral_stiffness/1000, FRONT_STIFFNESS[index]/1000
                self.preview.setText(f'已安装 {old:g}\n待安装 {new:g}\nkN/rad')
            self.notice.setText('与当前配方相同。' if old == new else '安装时保存完整原车，之后可恢复。')
            self.buttons[4]['state'] = DGG.NORMAL
            if self.drive is not None:
                self.buttons[8]['state'] = DGG.NORMAL
                self.buttons[8]['text'] = '安装并去试车'
                self.buttons[9]['state'] = DGG.NORMAL
            self.select(8 if self.drive is not None else 4)
        elif index == 4:
            self.apply(self.recipe)
        elif index == 5:
            self.undo()
        elif index == 6:
            self.back()
        elif index == 7:
            self.compare()
        elif index == 8:
            self.drive()
        elif index == 9:
            vehicle, path, label, trial_label = self.show_arguments
            self.show(vehicle, path, label, topic=self.topic, trial_label=trial_label)
        else:
            self.navigate(2 if index == 10 else 3)

    def key(self, key):
        if key in ('arrow_up', 'arrow_left', 'w', 'a'):
            self.select(self.selected-1)
        elif key in ('arrow_down', 'arrow_right', 's', 'd'):
            self.select(self.selected+1)
        elif key == 'enter':
            self.activate(self.selected)
        elif key == 'escape':
            self.back()

    def hide(self):
        self.root.hide()
        if self.vehicle_view is not None:
            self.vehicle_view.hide()
