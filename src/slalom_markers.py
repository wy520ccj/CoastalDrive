"""连续过门的纯显示门线；不生成可碰锥桶或替换道路碰撞。"""

from panda3d.core import BitMask32, CardMaker, TextNode

from slalom_lesson import COURSE_HALF_WIDTH, ENTRY_DISTANCE, GATE_HALF_WIDTH, GATES

MARKER_MASK = BitMask32.bit(29)


class SlalomMarkers:
    def __init__(self, parent, font, sun):
        self.root = parent.attachNewNode("slalom-lesson-markers")
        self.root.hide(BitMask32.allOn())
        self.root.show(MARKER_MASK)
        self.root.setShaderOff(1)
        self.root.setLightOff(1)
        sun.node().setCameraMask(sun.node().getCameraMask() & ~MARKER_MASK)
        self.gates = []
        self.entry_label = None
        self.fast = False
        self.practice = False
        for index, (distance, center) in enumerate(((ENTRY_DISTANCE, 0.), *GATES)):
            gate = self.root.attachNewNode(f"gate-{index}")
            half = COURSE_HALF_WIDTH if index == 0 else GATE_HALF_WIDTH
            paint = CardMaker("slalom-gate-paint")
            paint.setFrame(center-half, center+half, -.28, .28)
            node = gate.attachNewNode(paint.generate())
            node.setP(-90)
            node.setPos(0, distance, .04)
            node.setDepthOffset(1)
            for x in (center-half, center+half):
                stripe = CardMaker("slalom-gate-edge")
                stripe.setFrame(x-.10, x+.10, -2., 2.)
                node = gate.attachNewNode(stripe.generate())
                node.setP(-90)
                node.setPos(0, distance, .045)
            label = TextNode("slalom-label")
            label.setText("入口 40 km/h" if index == 0 else f"{index} · "+("终点" if index == len(GATES) else "左" if center < 0 else "右"))
            label.setFont(font)
            if index == 0:
                self.entry_label = label
            label.setAlign(TextNode.ACenter)
            label.setTextColor(1., 1., 1., 1)
            node = gate.attachNewNode(label)
            node.setPos(center, distance, 1.5)
            node.setScale(.48)
            node.setBillboardPointEye()
            self.gates.append(gate)
        self.root.hide(MARKER_MASK)

    def apply(self, result, origin_y):
        if result is None:
            self.root.hide(MARKER_MASK)
            return
        self.root.setY(result.start_progress-origin_y)
        if (result.fast, result.practice) != (self.fast, self.practice):
            self.fast = result.fast
            self.practice = result.practice
            self.entry_label.setText('练习入口 · 不限速度' if self.practice else '入口 70–80 km/h' if self.fast else '入口 40 km/h')
        self.root.show(MARKER_MASK)
        attempted = len(result.gate_times)
        next_index = 0 if result.entry_time is None else attempted+1
        for index, gate in enumerate(self.gates):
            passed = result.entry_time is not None if index == 0 else index <= attempted
            missed = index > 0 and passed and result.clearances[index-1] < 0
            gate.setColor(*((.95, .25, .15, 1) if missed else (.23, .64, .43, 1) if passed else
                           (1., .62, .16, 1) if index == next_index else (.22, .65, .76, 1)))
