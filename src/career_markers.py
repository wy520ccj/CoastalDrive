"""生涯终点、宽门与停车区，仅按权威道路采样绘制。"""

from panda3d.core import BitMask32, CardMaker, TextNode

from career import EVENT_BY_ID
from career_run import GATE_HALF_WIDTH
from slalom_markers import MARKER_MASK


class CareerMarkers:
    def __init__(self, parent, font, sun):
        self.root = parent.attachNewNode('career-markers')
        self.root.hide(BitMask32.allOn())
        self.root.setShaderOff(1)
        self.root.setLightOff(1)
        sun.node().setCameraMask(sun.node().getCameraMask() & ~MARKER_MASK)
        self.font, self.event_id, self.markers = font, None, []

    def build(self, event):
        self.root.getChildren().detach()
        self.markers = []
        rows = event.gates if event.kind == 'slalom' else ((event.distance, 0.),)
        for index, (distance, center) in enumerate(rows):
            node = self.root.attachNewNode('career-gate')
            half = GATE_HALF_WIDTH if event.kind == 'slalom' else 7.
            paint = CardMaker('career-line')
            paint.setFrame(-half, half, -.35, .35)
            stripe = node.attachNewNode(paint.generate())
            stripe.setP(-90)
            stripe.setDepthOffset(1)
            for x in (-half, half):
                post = CardMaker('career-post')
                post.setFrame(-.16, .16, 0., 2.6)
                stripe = node.attachNewNode(post.generate())
                stripe.setX(x)
                stripe.setTwoSided(True)
            label = TextNode('career-label')
            label.setFont(self.font)
            label.setText(f'{index+1} / 5' if event.kind == 'slalom' else
                          '停车区中心' if event.kind == 'parking' else '终点')
            label.setAlign(TextNode.ACenter)
            text = node.attachNewNode(label)
            text.setZ(2.8)
            text.setScale(.65)
            text.setBillboardPointEye()
            if event.kind == 'parking':
                for box in ((-7., -6.8, -20., 20.), (6.8, 7., -20., 20.),
                            (-7., 7., -20., -19.7), (-7., 7., 19.7, 20.)):
                    zone = CardMaker('career-parking-zone')
                    zone.setFrame(*box)
                    band = node.attachNewNode(zone.generate())
                    band.setP(-90)
                    band.setZ(-.005)
                    band.setDepthOffset(1)
            self.markers.append((node, distance, center))
        self.event_id = event.id

    def apply(self, result, road):
        if result is None:
            self.root.hide(MARKER_MASK)
            return
        event = EVENT_BY_ID[result.event_id]
        if self.event_id != event.id:
            self.build(event)
        self.root.show(MARKER_MASK)
        for index, (node, distance, center) in enumerate(self.markers):
            point = road.sample_lateral(result.start_progress+distance, center)
            node.setPos(point.x, point.y, point.z+.06)
            node.setHpr(point.heading, point.grade, 0.)
            passed = index < len(result.passed)
            color = ((.12, .65, .38, 1) if result.passed[index] else (.96, .3, .16, 1)) if passed else (.08, .65, .82, 1)
            node.setColor(*color)
