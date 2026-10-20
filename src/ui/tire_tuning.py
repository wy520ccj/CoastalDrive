"""固定前胎配方面板：预览和确认分开，原始试验不替改装后硬件背书。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from tire_tuning import previous_path
from ui import theme
from workshop import BRAKE_SHARES
from workshop_cornering import FRONT_STIFFNESS


class TireTuningPanel:
    def __init__(self, parent, font, textures, apply, undo, back, compare):
        self.apply, self.undo, self.back = apply, undo, back
        self.compare = compare
        self.textures, self.selected, self.recipe = textures, 6, None
        self.root = DirectFrame(parent=parent, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.70, 1.70, -.86, .80), sortOrder=112, state=DGG.NORMAL)

        def text(value, x, z, scale=.038, color=theme.INK):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color,
                align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)

        self.title = text('前胎配方 · 改装后亲自验车', -1.52, .62, .062)
        self.vehicle = text('', -1.52, .47, .034, theme.MUTED)
        self.vehicle.textNode.setWordwrap(88)
        self.hardware_note = text('', -1.52, .31, .037, theme.SEA)
        self.preview = text('', -1.52, -.03, .047)
        self.advice = text('', -1.52, -.17, .035, theme.SEA)
        text('确认安装前保存完整原车副本；当前车重新计成绩，原方案和报告保留。', -1.52, -.34, .030, theme.MUTED)
        self.notice = text('', -1.52, -.45, .032, theme.SEA)
        self.notice.textNode.setWordwrap(92)
        self.buttons = []
        choices = [(f'前胎 {value/1000:g}k', -1.14+i*.76, .16, .68) for i, value in enumerate(FRONT_STIFFNESS)]
        choices.extend((('确认安装', -1.20, -.72, .72), ('恢复安装前车辆', -.40, -.72, .76),
                        ('返回课题', 1.20, -.72, .72), ('道路 A/B', .40, -.72, .72)))
        for index, (label, x, z, width) in enumerate(choices):
            self.buttons.append(DirectButton(parent=self.root, text=label, text_font=font, text_fg=theme.INK,
                text_scale=.039, frameTexture=textures, frameColor=(1, 1, 1, 1), relief=DGG.FLAT, pressEffect=False,
                frameSize=(-width/2, width/2, -.060, .060), pos=(x, 0, z), command=self.activate, extraArgs=[index]))
        text('方向键选择 · Enter确认 · Esc返回；仅选择配方不会安装。', -1.52, -.83, .027, theme.MUTED)
        self.root.hide()

    def show(self, vehicle, path, label, *, topic='tires'):
        self.topic = topic
        self.original = vehicle
        self.vehicle.setText(label)
        self.recipe = None
        brakes = topic == 'brakes'
        self.title.setText('制动分配 · 改装后亲自验车' if brakes else '前胎配方 · 改装后亲自验车')
        self.hardware_note.setText('只改变前后制动扭矩份额；总制动扭矩、轮胎与路面保持。' if brakes else
                                  '教学侧偏刚度，单位kN/rad；只改变前轴，后胎与路面保持。')
        self.advice.setText('制动时前后轮荷不同；更大的前轴份额并不总是更好。\n'
                            '去短距验车比较距离，再到实验台查看四轮滑移/ABS。' if brakes else
                            '刚度影响转向响应；更大不等于所有工况更好。\n'
                            '去同一道课题看完成情况和余量，再到实验台比较侧偏与循迹。')
        self.preview.setText(f'当前前制动 {vehicle.config.front_brake_share:.0%} · 总扭矩 {vehicle.config.brake_torque:g}Nm' if brakes else
                            f'当前前胎 {vehicle.config.lateral_stiffness/1000:g}k · 后胎 {vehicle.config.rear_lateral_stiffness/1000:g}k')
        for index, button in enumerate(self.buttons[:4]):
            button['text'] = f'前制动 {BRAKE_SHARES[index]:.0%}' if brakes else f'前胎 {FRONT_STIFFNESS[index]/1000:g}k'
        for index in range(4, 7):
            self.buttons[index].setX((-1.05, 0., 1.05)[index-4] if brakes else (-1.20, -.40, 1.20)[index-4])
            width = (.92, .98, .92)[index-4] if brakes else (.72, .76, .72)[index-4]
            self.buttons[index]['frameSize'] = (-width/2, width/2, -.060, .060)
        self.buttons[7]['state'] = DGG.DISABLED if brakes else DGG.NORMAL
        self.buttons[7].hide() if brakes else self.buttons[7].show()
        self.notice.setText('先选配方，再确认安装；取消返回会保留当前车。')
        self.buttons[4]['state'] = DGG.DISABLED
        try:
            available = previous_path(vehicle, path) is not None
        except ValueError as error:
            available = False
            self.notice.setText('原车副本引用无效：'+str(error))
        self.buttons[5]['state'] = DGG.NORMAL if available else DGG.DISABLED
        self.select(0)
        self.root.show()

    def select(self, index):
        self.selected = index % (7 if self.topic == 'brakes' else 8)
        for i, button in enumerate(self.buttons):
            button['frameTexture'] = ((self.textures[2], self.textures[1], self.textures[2], self.textures[3])
                                      if i == self.selected else self.textures)

    def activate(self, index):
        if self.buttons[index]['state'] == DGG.DISABLED:
            return
        if index < len(FRONT_STIFFNESS):
            self.recipe = index
            if self.topic == 'brakes':
                old, new = self.original.config.front_brake_share, BRAKE_SHARES[index]
                self.preview.setText(f'前制动 {old:.0%} → {new:.0%} · 总扭矩/轮胎/路面保持')
            else:
                old, new = self.original.config.lateral_stiffness/1000, FRONT_STIFFNESS[index]/1000
                self.preview.setText(f'前胎 {old:g}k → {new:g}k · 后胎/路面/其他硬件保持')
            self.notice.setText('与当前车相同，确认后保持原方案关联。' if old == new else '确认后保存原车副本，并解除当前车的原试验/方案成绩关联。')
            self.buttons[4]['state'] = DGG.NORMAL
            self.select(4)
        elif index == 4:
            self.apply(self.recipe)
        elif index == 5:
            self.undo()
        elif index == 6:
            self.back()
        else:
            self.compare()

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
