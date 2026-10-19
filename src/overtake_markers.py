"""弯坡车流的终点与提前告示；纯表现节点，不添加碰撞。"""

from panda3d.core import BitMask32, CardMaker, TextNode

from overtake_routes import OVERTAKE_ROUTES
from race import GameMode
from slalom_markers import MARKER_MASK


class OvertakeMarkers:
    def __init__(self, parent, font, sun):
        self.root = parent.attachNewNode('overtake-finish-markers')
        self.root.hide(BitMask32.allOn())
        self.root.setShaderOff(1)
        self.root.setLightOff(1)
        sun.node().setCameraMask(sun.node().getCameraMask() & ~MARKER_MASK)
        self.finish = self.root.attachNewNode('overtake-finish')
        for index in range(13):
            card = CardMaker('overtake-finish-paint')
            card.setFrame(-6.5+index, -5.5+index, -.35, .35)
            node = self.finish.attachNewNode(card.generate())
            node.setP(-90)
            node.setZ(.045)
            node.setDepthOffset(1)
            node.setColor(*((1., .82, .22, 1.) if index % 2 else (.16, .3, .34, 1.)))
        for x in (-6.5, 6.5):
            card = CardMaker('overtake-finish-post')
            card.setFrame(-.12, .12, 0., 2.4)
            node = self.finish.attachNewNode(card.generate())
            node.setPos(x, 0, .05)
            node.setColor(1., .65, .2, 1.)
            node.setTwoSided(True)
        self.labels = []
        for name, anchor in (('终点 · 安全超车至少3辆', self.finish), ('前方150米终点 · 保持安全间距', self.root)):
            label = TextNode('overtake-finish-sign')
            label.setFont(font)
            label.setAlign(TextNode.ACenter)
            label.setText(name)
            node = anchor.attachNewNode(label)
            node.setScale(.50)
            node.setBillboardPointEye()
            node.setColor(1., .7, .25, 1.)
            self.labels.append(node)
        self.labels[0].setZ(2.7)

    def apply(self, result, road):
        route = None if result is None else OVERTAKE_ROUTES[GameMode(result.route_id)]
        if route is None or not route.finish_at_end:
            self.root.hide(MARKER_MASK)
            return
        self.root.show(MARKER_MASK)
        for node, offset in ((self.finish, 0.), (self.labels[1], -150.)):
            point = road.sample_lateral(result.start_progress+route.distance+offset, 0.)
            node.setPos(point.x, point.y, point.z+(2.7 if offset else 0.))
            node.setHpr(point.heading, point.grade, 0.)
