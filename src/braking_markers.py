"""定点刹停的纯显示地面标线；不创建碰撞体。"""

from panda3d.core import BitMask32, CardMaker, TextNode

from braking_lesson import COURSE_HALF_WIDTH, ENTRY_DISTANCE, TARGET_DISTANCE

MARKER_MASK = BitMask32.bit(29)


class BrakingMarkers:
    def __init__(self, parent, font, sun):
        self.root = parent.attachNewNode("braking-lesson-markers")
        self.root.hide(BitMask32.allOn())
        self.root.show(MARKER_MASK)
        self.root.setShaderOff(1)
        self.root.setLightOff(1)
        sun.node().setCameraMask(sun.node().getCameraMask() & ~MARKER_MASK)
        self.standard = self.root.attachNewNode('precision-markings')
        self.short = self.root.attachNewNode('short-braking-markings')
        for index, (name, distance, half_length, color) in enumerate((
            ("stop-area", TARGET_DISTANCE, 10., (.12, .38, .48, 1)),
            ("silver-area", TARGET_DISTANCE, 5., (.27, .56, .59, 1)),
            ("gold-area", TARGET_DISTANCE, 2., (.65, .62, .27, 1)),
            ("target-line", TARGET_DISTANCE, .12, (1., .94, .66, 1)),
            ("entry-line", ENTRY_DISTANCE, .25, (1., .48, .13, 1)),
        ), start=1):
            card = CardMaker(name)
            card.setFrame(-COURSE_HALF_WIDTH, COURSE_HALF_WIDTH, -half_length, half_length)
            node = self.standard.attachNewNode(card.generate())
            node.setP(-90)
            node.setPos(0, distance, .025)
            node.setColor(*color)
            node.setDepthOffset(1)
            # 各层标线不共面，避免重叠区域闪烁。
            node.setZ(.025 + .002 * index)
        for text, distance in (("80 km/h", ENTRY_DISTANCE), ("停车中心", TARGET_DISTANCE)):
            label = TextNode("braking-label")
            label.setText(text)
            label.setFont(font)
            label.setAlign(TextNode.ACenter)
            label.setTextColor(1., .95, .78, 1)
            node = self.standard.attachNewNode(label)
            node.setPos(0, distance, 1.5)
            node.setScale(.55)
            node.setBillboardPointEye()
        for distance, text, color in ((100., '80–85 km/h', (1., .48, .13, 1)),
                (133., '金 · 33m', (.65, .62, .27, 1)), (136., '银 · 36m', (.27, .56, .59, 1)),
                (142., '铜 · 42m', (.12, .38, .48, 1))):
            card = CardMaker('short-braking-line')
            card.setFrame(-1.8, 1.8, -.15, .15)
            node = self.short.attachNewNode(card.generate())
            node.setP(-90)
            node.setPos(0, distance, .04)
            node.setColor(*color)
            label = TextNode('short-braking-label')
            label.setText(text)
            label.setFont(font)
            label.setAlign(TextNode.ACenter)
            label.setTextColor(1., .95, .78, 1)
            node = self.short.attachNewNode(label)
            node.setPos(2.3, distance, .8)
            node.setScale(.32)
            node.setBillboardPointEye()
        self.short.hide()
        self.root.hide(MARKER_MASK)

    def apply(self, result, origin_y):
        if result is None:
            self.root.hide(MARKER_MASK)
        else:
            self.short.show() if result.short else self.short.hide()
            self.standard.hide() if result.short else self.standard.show()
            self.root.setY(result.start_progress-origin_y)
            self.root.show(MARKER_MASK)
