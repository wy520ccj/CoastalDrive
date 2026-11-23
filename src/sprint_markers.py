"""短途道路门的纯显示标线，位置和姿态直接读取同一道路。"""

from panda3d.core import BitMask32, CardMaker, TextNode

from slalom_markers import MARKER_MASK
from sprint_routes import sprint_result_route
from sprint_run import ROAD_HALF_WIDTH


class SprintMarkers:
    def __init__(self, parent, font, sun):
        self.root = parent.attachNewNode('sprint-route-markers')
        self.root.hide(BitMask32.allOn())
        self.gates = []
        self.labels = []
        self.label_nodes = []
        self.zone_root = self.root.attachNewNode('speed-zone-band')
        self.zone_key = None
        sun.node().setCameraMask(sun.node().getCameraMask() & ~MARKER_MASK)
        self.root.setShaderOff(1)
        self.root.setLightOff(1)
        # 当前短途均四门，具体位置由路线与实际道路采样决定。
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
            self.labels.append(text)
            node = gate.attachNewNode(text)
            node.setPos(0, 0, 2.5)
            node.setScale(.65)
            node.setBillboardPointEye()
            self.label_nodes.append(node)
            self.gates.append(gate)
        self.font = font

    def show_zone(self, result, route, road):
        key = route, result.start_progress
        if self.zone_key != key:
            self.zone_root.getChildren().detach()
            self.zone_key = key
            zone = route.speed_zone
            names = (f'测速 ≥{route.entry_kph:g}km/h', '限速带入口 35–50', '限速带出口', '终点') if zone is not None else (
                '1 · 道路门', '2 · 道路门', '3 · 道路门', '终点')
            for label, name in zip(self.labels, names, strict=True):
                label.setText(name)
            if zone is not None:
                for distance in range(int(zone.start), int(zone.end), 5):
                    point = road.sample_lateral(result.start_progress+distance+2.5, 0.)
                    anchor = self.zone_root.attachNewNode('speed-zone-paint')
                    anchor.setPos(point.x, point.y+road.origin_y, point.z+.045)
                    anchor.setHpr(point.heading, point.grade, 0.)
                    for x in (-6., 6.):
                        card = CardMaker('speed-zone-edge')
                        card.setFrame(x-.25, x+.25, -2.5, 2.5)
                        node = anchor.attachNewNode(card.generate())
                        node.setP(-90)
                        node.setColor(.18, .69, .78, 1.)
                        node.setDepthOffset(1)
                approach = (f'{route.gates[0]:g}米测速 ≥{route.entry_kph:g}km/h' if route.version
                            else '前方控速带 35–50 km/h')
                signs = ((zone.start-90., approach),)
                if not route.version:
                    signs += ((zone.start, '保持 35–50 km/h'), (zone.end, '控速结束 · 重新加速'))
                for distance, text in signs:
                    point = road.sample_lateral(result.start_progress+distance, 0.)
                    label = TextNode('speed-zone-sign')
                    label.setText(text)
                    label.setFont(self.font)
                    label.setAlign(TextNode.ACenter)
                    node = self.zone_root.attachNewNode(label)
                    node.setPos(point.x, point.y+road.origin_y, point.z+3.)
                    node.setScale(.55)
                    node.setColor(.25, .8, .95, 1.)
                    node.setBillboardPointEye()
        self.zone_root.setY(-road.origin_y)

    def apply(self, result, road):
        if result is None:
            self.root.hide(MARKER_MASK)
            return
        route = sprint_result_route(result)
        self.show_zone(result, route, road)
        self.root.show(MARKER_MASK)
        for index, (gate, distance) in enumerate(zip(self.gates, route.gates, strict=True)):
            point = road.sample_lateral(result.start_progress+distance, 0.)
            gate.setPos(point.x, point.y, point.z)
            gate.setHpr(point.heading, point.grade, 0.)
            gate.setColor(*((.23, .64, .43, 1) if index < result.gates else
                           (1., .62, .16, 1) if index == result.gates else (.22, .65, .76, 1)))
            # 山谷的测速门紧邻限速带，依次显示牌面，避免两个提示叠在视线正中。
            label = self.label_nodes[index]
            if route.version and index != result.gates:
                label.hide()
            else:
                label.show()
