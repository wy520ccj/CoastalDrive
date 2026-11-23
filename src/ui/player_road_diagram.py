"""道路结束记录的图解；余量与位置只作显示，不补轨迹或推进车辆。"""

import math

from panda3d.core import LineSegs

from slalom_lesson import GATES
from ui.garage_layout import GRAY, INK, ORANGE, WHITE


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
    def __init__(self, panel):
        self.panel = panel
        self.root = panel.content.attachNewNode('road-result-diagram')
        self.plot = self.root.attachNewNode('recorded-values')
        self.labels, self.selected = [], 0
        left, wide = panel.left, panel.wide
        self.legend = panel.text('', left+36, 432, 15, GRAY, parent=self.root)
        self.detail = panel.text('', left+wide*.64, 684, 18, parent=self.root, wrap=wide*.32)
        self.buttons, self.edges = [], []
        start, step = left+92, (wide*.53-92)/6
        for index in range(6):
            button = panel.button(f'第{index+1}门', start+index*step, 673, step, 44,
                                  self.select, args=(index,))
            button.reparentTo(self.root)
            self.buttons.append(button)
            self.edges.append(panel.fill(start+index*step+5, 715, step-10, 4, ORANGE,
                                         parent=self.root, radius=0))
        self.arrows = [panel.button(label, x, 673, 44, 44, self.change, args=(delta,))
                       for label, x, delta in (('‹', left+36, -1), ('›', left+wide*.55, 1))]
        for button in self.arrows:
            button.reparentTo(self.root)
        self.root.hide()

    def text(self, value, x, y, size=18, color=INK):
        item = self.panel.text(value, x, y, size, color, parent=self.plot)
        self.labels.append(item)
        return item

    def line(self, points, color, width=1.):
        line = LineSegs()
        line.setColor(*color)
        line.setThickness(width)
        for index, (x, y) in enumerate(points):
            px, pz = self.panel.point(x, y)
            line.moveTo(px, 0, pz) if index == 0 else line.drawTo(px, 0, pz)
        self.plot.attachNewNode(line.create())

    def fill(self, x, y, width, height, color, radius=0):
        return self.panel.fill(x, y, width, height, color, parent=self.plot, radius=radius)

    def clear(self):
        for label in self.labels:
            label.destroy()
        self.labels.clear()
        self.plot.removeNode()
        self.plot = self.root.attachNewNode('recorded-values')

    def destroy(self):
        self.clear()
        self.legend.destroy()
        self.detail.destroy()
        self.root.removeNode()

    def show(self, store):
        self.a, self.b, self.brakes = store.a, store.b, store.brakes
        self.clear()
        for button in (*self.buttons, *self.arrows):
            button.hide() if self.brakes else button.show()
        for edge in self.edges:
            edge.hide()
        if self.brakes:
            self.draw_braking()
        else:
            self.draw_gates()
            self.select(gate_focus(self.a, self.b))
        self.root.show()

    def draw_gates(self):
        left, wide = self.panel.left, self.panel.wide
        self.detail.setPos(*self.panel.point(left+wide*.64, 684))
        self.detail.textNode.setWordwrap(wide*.32/18)
        self.legend.setText('')
        for side, item, y in zip('AB', (self.a, self.b), (501, 600), strict=True):
            self.text(side, left+48, y+10, 28)
            self.fill(left+98, y-15, wide-142, 30, (.68, .70, .73, 1))
            for index in range(24):
                x = left+105+index*(wide-163)/24
                self.fill(x, y-1, (wide-163)/48, 2, WHITE)
            margins = item['result']['clearances'] if item else ()
            for index in range(6):
                x = left+wide*.14+index*wide*.147
                if side == 'A':
                    self.text(f'第{index+1}门', x-27, y-63, 18)
                reached = index < len(margins)
                color = (.1, .64, .24, 1) if reached and margins[index] >= 0 else ORANGE if reached else GRAY
                self.fill(x-3, y-27, 6, 43, INK)
                self.fill(x-9, y-45, 18, 18, color, 9)
                value = f'{margins[index]:+.3f}m' if reached else '未到达'
                self.text(value, x-35, y+43, 16, color)
        self.line([(left+36, 651), (left+wide-36, 651)], (.79, .81, .84, 1))

    def change(self, direction):
        self.select(self.selected+direction)

    def select(self, index):
        self.selected = index % 6
        for i, button in enumerate(self.buttons):
            button['text_fg'] = ORANGE if i == self.selected else INK
            self.edges[i].show() if i == self.selected else self.edges[i].hide()
        parts = []
        for name, item in zip('AB', (self.a, self.b), strict=True):
            margins = item['result']['clearances'] if item else ()
            value = margins[self.selected] if self.selected < len(margins) else None
            parts.append(name+' 未到达' if value is None else f'{name} {value:+.3f}m'+(' 超线' if value < 0 else ' 门内'))
        self.detail.setText(f'第{self.selected+1}门 · {GATES[self.selected][0]:g}m\n'+' / '.join(parts))

    def draw_braking(self):
        left, wide = self.panel.left, self.panel.wide
        short = self.a is None or self.a['result']['short']
        low, high = brake_range(self.a, self.b, short)
        self.legend.setText('实心为有效结束，空心为未通过 · '+('过门后最大前进距离 / m' if short else '车身中心位置 / m'))

        def x_at(value):
            return left+140+(value-low)/(high-low)*(wide-220)

        ticks = (0., 33., 36., 42.) if short else (160., 165., 168., 170., 172., 175., 180.)
        for value in ticks:
            x = x_at(value)
            self.line([(x, 469), (x, 635)], (.73, .76, .79, 1))
            if short or value in (160., 170., 180.):
                self.text(('门0' if value == 0 else f'{value:g}'), x-16, 461, 17, GRAY)
        for name, item, color, y in zip('AB', (self.a, self.b), (INK, ORANGE), (506, 605), strict=True):
            self.text(name, left+48, y+10, 28, color)
            self.line([(left+140, y), (left+wide-80, y)], (.66, .69, .73, 1), 3)
            point = brake_position(item, short)
            if point is None:
                self.text('未建立', left+wide*.46, y-16, 20, GRAY)
            else:
                x = x_at(point)
                if item['result']['succeeded']:
                    self.fill(x-8, y-8, 16, 16, color, 8)
                else:
                    self.line([(x-8, y-8), (x+8, y-8), (x+8, y+8),
                               (x-8, y+8), (x-8, y-8)], color, 2)
                self.text(f'{point:.3f}m', min(left+wide-140, max(left+140, x-40)), y-19, 20, color)
        speeds = []
        for name, item in zip('AB', (self.a, self.b), strict=True):
            speed = item['result']['entry_kph'] if item else None
            speeds.append(name+' 未过门' if speed is None else f'{name}入门 {speed:.3f}km/h')
        self.detail.setPos(*self.panel.point(left+36, 682))
        self.detail.textNode.setWordwrap((wide-72)/18)
        self.detail.setText(' / '.join(speeds)+'\n'+('短距标线：金33 / 银36 / 铜42m' if short else '目标170m；点为结束时位置，失败不算成绩'))

    def key(self, key):
        if not self.brakes and key in ('arrow_left', 'arrow_right'):
            self.select(self.selected+(-1 if key == 'arrow_left' else 1))
