"""工程曲线绘制；只消费记录值，未定义信号断开连线。"""

import math

from direct.gui.DirectGui import OnscreenText
from panda3d.core import LineSegs, TextNode

from lab_signals import SIGNAL_BY_KEY
from ui import theme
from ui.lab_widgets import rounded_panel

TEXT = theme.INK
MUTED = theme.MUTED
COLORS = (theme.SEA, theme.ORANGE)


class LabPlot:
    def __init__(self, parent, font, box, key):
        self.root = parent.attachNewNode("lab-plot")
        self.font, self.box, self.keys = font, box, (key,)
        left, _right, bottom, top = box
        rounded_panel(self.root, "signal-card", box, theme.PAPER_LIGHT)
        self.title = OnscreenText(parent=self.root, font=font, text="", fg=TEXT,
            pos=(left+.06, top-.065), scale=.039, align=TextNode.ALeft, mayChange=True)
        self.readout = OnscreenText(parent=self.root, font=font, text="", fg=MUTED,
            pos=(left+.06, bottom+.020), scale=.031, align=TextNode.ALeft, mayChange=True)
        self.axis_labels = []
        self.lines = self.root.attachNewNode("curves")
        self.cursor = self.root.attachNewNode("cursor")
        self.duration = 1.
        self.series = []

    def update(self, records):
        self.lines.removeNode()
        self.lines = self.root.attachNewNode("curves")
        series = [record.samples for record in records]
        self.series = series
        values = [row[key] for rows in series for row in rows for key in self.keys if row[key] is not None]
        low, high = (min(values), max(values)) if values else (0., 1.)
        span = max(high-low, .1)
        power = 10**math.floor(math.log10(span/4))
        step = next(scale*power for scale in (1, 2, 2.5, 5, 10) if scale*power >= span/4)
        low, high = math.floor(low/step)*step, math.ceil(high/step)*step
        if high == low:
            low, high = low-step, high+step
        self.duration = max((rows[-1]["time"] for rows in series if rows), default=1.) or 1.
        left, right, bottom, top = self.box
        x0, x1, z0, z1 = left+.14, right-.065, bottom+.115, top-.135
        for label in self.axis_labels:
            label.destroy()
        self.axis_labels.clear()
        grid = LineSegs()
        grid.setColor(.79, .83, .80, 1)
        for index in range(round((high-low)/step)+1):
            value = low+index*step
            z = z0+(value-low)/(high-low)*(z1-z0)
            grid.moveTo(x0, 0, z)
            grid.drawTo(x1, 0, z)
            label = f"{value:.2f}" if step < 1 else f"{value:g}"
            self.axis_labels.append(OnscreenText(parent=self.root, font=self.font, text=label, fg=MUTED,
                pos=(x0-.025, z-.009), scale=.032, align=TextNode.ARight))
        for index in range(5):
            x = x0+index*(x1-x0)/4
            grid.moveTo(x, 0, z0)
            grid.drawTo(x, 0, z1)
            self.axis_labels.append(OnscreenText(parent=self.root, font=self.font,
                text=f"{self.duration*index/4:.1f}", fg=MUTED,
                pos=(x, z0-.052), scale=.032))
        self.lines.attachNewNode(grid.create())
        for rows, color in zip(series, COLORS):
            for channel, key in enumerate(self.keys):
                curve = LineSegs()
                curve.setThickness(1.8)
                curve.setColor(*color)
                connected = False
                for index, row in enumerate(rows):
                    value = row[key]
                    if value is None or (channel and index//6%2):
                        connected = False
                        continue
                    point = (x0+row["time"]/self.duration*(x1-x0), 0,
                             z0+(value-low)/(high-low)*(z1-z0))
                    curve.drawTo(*point) if connected else curve.moveTo(*point)
                    connected = True
                self.lines.attachNewNode(curve.create())
        signal = SIGNAL_BY_KEY[self.keys[0]]
        label = signal.label
        if len(self.keys) == 2:
            if self.keys[0].endswith("_fl"):
                label = label.replace(" FL", " · 前轮")
            elif self.keys[0].endswith("_rl"):
                label = label.replace(" RL", " · 后轮")
            elif self.keys[0] == "steering_request":
                label = "转角请求 / 响应"
        self.title.setText(f"{label}  /  {signal.unit}")

    def seek(self, time):
        self.cursor.removeNode()
        self.cursor = self.root.attachNewNode("cursor")
        left, right, bottom, top = self.box
        x = left+.14+min(1., time/self.duration)*(right-left-.205)
        lines = LineSegs()
        lines.setColor(*theme.INK)
        lines.moveTo(x, 0, bottom+.115)
        lines.drawTo(x, 0, top-.135)
        self.cursor.attachNewNode(lines.create())
        values = []
        for index, rows in enumerate(self.series):
            sample = round(time*120)
            value = rows[sample][self.keys[0]] if sample < len(rows) else None
            values.append(f"{'AB'[index]} {value:.2f}" if value is not None else f"{'AB'[index]} —")
        suffix = "  实线 / 虚线" if len(self.keys) > 1 else ""
        self.readout.setText(f"t {time:.3f} s    {'   '.join(values)}{suffix}")
