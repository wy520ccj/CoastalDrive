"""道路结束记录的图解；余量与位置只作显示，不补轨迹或推进车辆。"""

import math

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, OnscreenText
from panda3d.core import LineSegs, TextNode

from slalom_lesson import GATES
from ui import theme


def gate_focus(a, b):
    values = [(value, index) for item in (a, b) if item is not None
              for index, value in enumerate(item['result']['clearances'])]
    failed = [index for value, index in values if value < 0]
    return min(failed) if failed else min(values)[1] if values else 0


def brake_position(item, short):
    if item is None:
        return None
    result = item['result']
    return result['stopping_m'] if short else result['position']


def brake_range(a, b, short):
    values = [brake_position(item, short) for item in (a, b)]
    values = [value for value in values if value is not None]
    if short:
        return 0., max(42., math.ceil(max(values, default=0.)/5)*5.)
    return min(150., math.floor(min(values, default=170.)/10)*10.), max(190., math.ceil(max(values, default=170.)/10)*10.)


class RoadDiagram:
    def __init__(self, parent, font, textures):
        self.root = parent.attachNewNode('road-result-diagram')
        self.font, self.labels = font, []
        self.plot = self.root.attachNewNode('recorded-values')
        self.legend = self.text('', -1.52, .12, .025, theme.MUTED)
        self.detail = self.text('', -1.52, -.30, .029, theme.INK)
        self.buttons = []
        for index in range(6):
            self.buttons.append(DirectButton(parent=self.root, text=f'{index+1}门', text_font=font,
                text_fg=theme.INK, text_scale=.029, frameTexture=textures, frameColor=(1, 1, 1, 1),
                relief=DGG.FLAT, pressEffect=False, frameSize=(-.15, .15, -.028, .028),
                pos=(-1.10+index*.44, 0., .065), command=self.select, extraArgs=[index]))
        self.root.hide()

    def text(self, value, x, z, scale=.027, color=theme.INK, *, plot=False):
        label = OnscreenText(parent=self.plot if plot else self.root, text=value, font=self.font, fg=color,
            align=TextNode.ALeft, pos=(x, z), scale=scale, mayChange=True)
        if plot:
            self.labels.append(label)
        return label

    def line(self, points, color, width=1.):
        line = LineSegs()
        line.setColor(*color)
        line.setThickness(width)
        line.moveTo(points[0][0], 0., points[0][1])
        for x, z in points[1:]:
            line.drawTo(x, 0., z)
        self.plot.attachNewNode(line.create())

    def clear(self):
        for label in self.labels:
            label.destroy()
        self.labels.clear()
        self.plot.removeNode()
        self.plot = self.root.attachNewNode('recorded-values')

    def show(self, store):
        self.a, self.b, self.brakes = store.a, store.b, store.brakes
        self.clear()
        for button in self.buttons:
            button.hide() if self.brakes else button.show()
        if self.brakes:
            self.draw_braking()
        else:
            self.draw_gates()
            self.select(gate_focus(self.a, self.b))
        self.root.show()

    def draw_gates(self):
        self.legend.setText('A海蓝 / B橙色 · 整车余量（米），负值超线 · —未到达')
        values = [value for item in (self.a, self.b) if item is not None for value in item['result']['clearances']]
        low, high = min(-.5, math.floor(min(values, default=0.)*2)/2), max(1., math.ceil(max(values, default=0.)*2)/2)

        def height(value):
            return -.235+(value-low)/(high-low)*.25

        for value in (low, 0., high):
            z = height(value)
            self.line([(-1.26, z), (1.34, z)], theme.FAILURE if value == 0 else theme.MUTED)
            self.text(f'{value:g}', -1.51, z-.008, .025, plot=True)
        for index in range(6):
            for side, item, color in zip((-.05, .05), (self.a, self.b), (theme.SEA, theme.ORANGE), strict=True):
                margins = item['result']['clearances'] if item else ()
                x = -1.10+index*.44+side
                if index < len(margins):
                    z = height(margins[index])
                    self.line([(x, height(0.)), (x, z)], color, 8.)
                    self.line([(x-.025, z), (x+.025, z)], color, 2.)
                else:
                    self.text('—', x-.02, -.266, .025, theme.MUTED, plot=True)

    def select(self, index):
        self.selected = index % 6
        for i, button in enumerate(self.buttons):
            button['text_fg'] = theme.SEA if i == self.selected else theme.INK
            button['frameColor'] = theme.PAPER if i == self.selected else (1, 1, 1, 1)
        parts = []
        for name, item in zip('AB', (self.a, self.b), strict=True):
            margins = item['result']['clearances'] if item else ()
            value = margins[self.selected] if self.selected < len(margins) else None
            parts.append(name+' 未到达' if value is None else f'{name} {value:+.3f}m'+(' 超线' if value < 0 else ' 门内'))
        self.detail.setText(f'第{self.selected+1}门 · {GATES[self.selected][0]:g}m · '+' / '.join(parts)+
                            '\n点击门号或←→切门；空格切换数值表')

    def draw_braking(self):
        short = self.a is None or self.a['result']['short']
        low, high = brake_range(self.a, self.b, short)
        self.legend.setText('A海蓝 / B橙色 · 实心完成 / 空心未通过 · '+('过门后最大前进（米）' if short else '车身中心位置（米），金±2 / 银±5 / 铜±10'))

        def x_at(value):
            return -1.12+(value-low)/(high-low)*2.46

        ticks = (0., 33., 36., 42.) if short else (160., 165., 168., 170., 172., 175., 180.)
        for value in ticks:
            self.line([(x_at(value), .01), (x_at(value), -.235)], theme.SUCCESS if value in (33., 170.) else theme.MUTED)
            if short or value in (160., 170., 180.):
                label = ('门0' if value == 0 else f'{value:g}') if short else f'{value:g}'
                self.text(label, x_at(value)-.025, .045, .025, plot=True)
        for name, item, color, z in zip('AB', (self.a, self.b), (theme.SEA, theme.ORANGE), (-.065, -.185), strict=True):
            self.text(name, -1.50, z-.01, .031, color, plot=True)
            self.line([(-1.12, z), (1.34, z)], theme.MUTED)
            point = brake_position(item, short)
            if point is None:
                self.text('未建立', -.15, z+.015, .029, theme.MUTED, plot=True)
            else:
                x = x_at(point)
                if item['result']['succeeded']:
                    self.line([(x-.022, z), (x+.022, z)], color, 8.)
                else:
                    self.line([(x-.027, z-.018), (x+.027, z-.018), (x+.027, z+.018),
                               (x-.027, z+.018), (x-.027, z-.018)], color, 2.)
                self.text(f'{point:.3f}m', x-.07, z+.035, .027, color, plot=True)
        speeds = []
        for name, item in zip('AB', (self.a, self.b), strict=True):
            speed = item['result']['entry_kph'] if item else None
            speeds.append(name+' 未过门' if speed is None else f'{name}入门 {speed:.3f}km/h')
        self.detail.setText(' / '.join(speeds)+'\n'+('短距标线：金33 / 银36 / 铜42m' if short else '目标170m；点为结束时位置，失败不算成绩')+' · 空格看数值表')

    def key(self, key):
        if not self.brakes and key in ('arrow_left', 'arrow_right'):
            self.select(self.selected+(-1 if key == 'arrow_left' else 1))
