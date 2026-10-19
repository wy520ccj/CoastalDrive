"""短途道路门的纯显示标线，位置和姿态直接读取同一道路。"""

from panda3d.core import BitMask32, CardMaker, TextNode

from race import GameMode
from slalom_markers import MARKER_MASK
from sprint_routes import SPRINT_ROUTES
from sprint_run import ROAD_HALF_WIDTH


class SprintMarkers:
    def __init__(self, parent, font, sun):
        self.root = parent.attachNewNode('sprint-route-markers')
        self.root.hide(BitMask32.allOn())
        self.gates = []
        sun.node().setCameraMask(sun.node().getCameraMask() & ~MARKER_MASK)
        self.root.setShaderOff(1)
        self.root.setLightOff(1)
        # 两条路线均四门，具体位置由当前路线与实际道路采样决定。
        for index in range(4):
            gate = self.root.attachNewNode(f'sprint-gate-{index}')
            card = CardMaker('sprint-gate-paint')
            card.setFrame(-ROAD_HALF_WIDTH, ROAD_HALF_WIDTH, -.35, .35)
            node = gate.attachNewNode(card.generate())
            node.setP(-90)
            node.setZ(.045)
            node.setDepthOffset(1)
            for x in (-ROAD_HALF_WIDTH, ROAD_HALF_WIDTH):
                card = CardMaker('sprint-gate-post')
                card.setFrame(-.13, .13, 0., 2.4)
                node = gate.attachNewNode(card.generate())
                node.setPos(x, 0, .05)
                node.setTwoSided(True)
            text = TextNode('sprint-gate-number')
            text.setText('终点' if index == 3 else f'{index+1} · 道路门')
            text.setFont(font)
            text.setAlign(TextNode.ACenter)
            node = gate.attachNewNode(text)
            node.setPos(0, 0, 2.5)
            node.setScale(.65)
            node.setBillboardPointEye()
            self.gates.append(gate)

    def apply(self, result, road):
        if result is None:
            self.root.hide(MARKER_MASK)
            return
        route = SPRINT_ROUTES[GameMode(result.route_id)]
        self.root.show(MARKER_MASK)
        for index, (gate, distance) in enumerate(zip(self.gates, route.gates, strict=True)):
            point = road.sample_lateral(result.start_progress+distance, 0.)
            gate.setPos(point.x, point.y, point.z)
            gate.setHpr(point.heading, point.grade, 0.)
            gate.setColor(*((.23, .64, .43, 1) if index < result.gates else
                           (1., .62, .16, 1) if index == result.gates else (.22, .65, .76, 1)))
