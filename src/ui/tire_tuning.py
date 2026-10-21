"""围绕当前车辆选择零件；预览、安装、试车各有明确状态。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from tire_tuning import previous_path
from vehicle_designs import vehicle_design
from workshop import BRAKE_SHARES
from workshop_cornering import FRONT_STIFFNESS

BACKGROUND = (.038, .055, .072, 1)
SURFACE = (.085, .112, .135, 1)
TEXT = (.94, .95, .94, 1)
MUTED = (.62, .70, .74, 1)
AMBER = (1., .65, .23, 1)
SELECTED = (.20, .27, .30, 1)


class TireTuningPanel:
    def __init__(self, parent, font, textures, apply, undo, back, compare, *, vehicle_view=None, drive=None):
        self.apply, self.undo, self.back, self.compare = apply, undo, back, compare
        self.vehicle_view, self.drive = vehicle_view, drive
        self.selected, self.recipe = 0, None
        self.root = DirectFrame(parent=parent, frameColor=BACKGROUND,
            frameSize=(-1.78, 1.78, -1.5, 1.5), sortOrder=112, state=DGG.NORMAL)
        DirectFrame(parent=self.root, frameColor=SURFACE,
                    frameSize=(.38, 1.65, -.91, .64), state=DGG.DISABLED)

        def text(value, x, z, scale=.038, color=TEXT):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color,
                align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)

        text('COASTAL DRIVE', -1.56, .88, .044, AMBER)
        text('海岸工坊  /  改装车辆', -.57, .88, .040)
        text('选择零件  →  安装配方  →  实际试车', -1.56, -.94, .032, MUTED)
        self.title = text('前轮配方', .49, .51, .064)
        self.vehicle = text('', -1.56, -.47, .045)
        self.vehicle.textNode.setWordwrap(40)
        self.hardware_note = text('', .49, .42, .035, MUTED)
        self.preview = text('', .49, -.39, .033, AMBER)
        self.preview.textNode.setWordwrap(31)
        self.advice = text('', -1.56, -.57, .042, MUTED)
        self.advice.textNode.setWordwrap(53)
        self.notice = text('', -1.56, -.73, .030, AMBER)
        self.notice.textNode.setWordwrap(55)
        self.buttons, self.card_notes, self.bars = [], [], []
        choices = [(f'{value/1000:g} kN/rad', 1.01, .27-i*.145, 1.02, .12)
                   for i, value in enumerate(FRONT_STIFFNESS)]
        choices.extend((('安装配方', 1.01, -.68, 1.02, .13),
                        ('恢复安装前车辆', -.33, -.82, .88, .10),
                        ('返回', 1.39, .87, .40, .10),
                        ('改装前后对比', -1.10, -.82, .86, .10)))
        if drive is not None:
            choices.append(('去试车  ›', 1.01, -.84, 1.02, .11))
        for index, (label, x, z, width, height) in enumerate(choices):
            button = DirectButton(parent=self.root, text=label, text_font=font,
                text_fg=TEXT, text_scale=.052 if index < 4 else .044,
                text_align=TextNode.ALeft if index < 4 else TextNode.ACenter,
                text_pos=(-.43, -.012) if index < 4 else (0, -.012),
                frameColor=SURFACE, relief=DGG.FLAT, pressEffect=False,
                frameSize=(-width/2, width/2, -height/2, height/2), pos=(x, 0, z),
                command=self.activate, extraArgs=[index])
            button.bind(DGG.ENTER, lambda event, i=index: self.select(i))
            self.buttons.append(button)
            if index < 4:
                self.card_notes.append(OnscreenText(parent=button, text='', font=font, fg=MUTED,
                    align=TextNode.ARight, pos=(.43, -.008), scale=.032, mayChange=True))
        self.root.hide()

    def show(self, vehicle, path, label, *, topic='tires'):
        self.topic, self.original, self.recipe = topic, vehicle, None
        brakes = topic == 'brakes'
        self.title.setText('制动分配' if brakes else '前轮配方')
        self.vehicle.setText(vehicle_design(vehicle.design_id).name)
        self.hardware_note.setText('前轴 / 后轴制动份额' if brakes else '前轴侧偏刚度 · kN/rad')
        self.advice.setText('制动力如何分给前后轮。\n装好后，在同一场地比较停车距离。' if brakes else
                            '改变前轮的转向响应。\n装好后，在同一场地比较过门表现。')
        if self.vehicle_view is not None:
            self.vehicle_view.show(self.root, (-1.62, .30, -.37, .74), vehicle)
            self.vehicle_view.highlight(topic)
        for index, button in enumerate(self.buttons[:4]):
            current = (vehicle.config.front_brake_share == BRAKE_SHARES[index] if brakes else
                       vehicle.config.lateral_stiffness == FRONT_STIFFNESS[index])
            button['text'] = f'{BRAKE_SHARES[index]:.0%} / {1-BRAKE_SHARES[index]:.0%}' if brakes else f'{FRONT_STIFFNESS[index]/1000:g} kN/rad'
            descriptor = '' if brakes else ('低刚度', '较低', '中等', '高刚度')[index]
            self.card_notes[index].setText('已安装' if current else descriptor)
        value = f'前轴 {vehicle.config.front_brake_share:.0%}' if brakes else f'{vehicle.config.lateral_stiffness/1000:g} kN/rad'
        self.preview.setText('已安装  '+value+'\n选择右侧配方预览')
        self.notice.setText('选择配方只作预览，安装后再去试车。')
        self.buttons[4]['state'] = DGG.DISABLED
        if self.drive is not None:
            self.buttons[8]['state'] = DGG.NORMAL
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
            primary = i == (4 if self.recipe is not None else 8)
            button['frameColor'] = AMBER if primary and not disabled else SELECTED if i == self.selected else SURFACE
            button['text_fg'] = BACKGROUND if primary and not disabled else MUTED if disabled else TEXT
            button['borderWidth'] = (.008, .008) if i == self.selected else (0, 0)

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
                self.preview.setText(f'已安装 {old:g} → 待安装 {new:g}\nkN/rad')
            self.notice.setText('与当前配方相同。' if old == new else '安装时保存完整原车，之后可恢复。')
            self.buttons[4]['state'] = DGG.NORMAL
            if self.drive is not None:
                self.buttons[8]['state'] = DGG.DISABLED
            self.select(4)
        elif index == 4:
            self.apply(self.recipe)
        elif index == 5:
            self.undo()
        elif index == 6:
            self.back()
        elif index == 7:
            self.compare()
        else:
            self.drive()

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
