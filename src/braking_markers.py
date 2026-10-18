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
        for name, distance, half_length, color in (
            ("stop-area", TARGET_DISTANCE, 10., (.12, .38, .48, 1)),
            ("silver-area", TARGET_DISTANCE, 5., (.27, .56, .59, 1)),
            ("gold-area", TARGET_DISTANCE, 2., (.65, .62, .27, 1)),
            ("target-line", TARGET_DISTANCE, .12, (1., .94, .66, 1)),
            ("entry-line", ENTRY_DISTANCE, .25, (1., .48, .13, 1)),
        ):
            card = CardMaker(name)
            card.setFrame(-COURSE_HALF_WIDTH, COURSE_HALF_WIDTH, -half_length, half_length)
            node = self.root.attachNewNode(card.generate())
            node.setP(-90)
            node.setPos(0, distance, .025)
            node.setColor(*color)
            node.setDepthOffset(1)
            # 各层标线不共面，避免重叠区域闪烁。
            node.setZ(.025 + .002 * len(self.root.getChildren()))
        for text, distance in (("80 km/h", ENTRY_DISTANCE), ("停车中心", TARGET_DISTANCE)):
            label = TextNode("braking-label")
            label.setText(text)
            label.setFont(font)
            label.setAlign(TextNode.ACenter)
            label.setTextColor(1., .95, .78, 1)
            node = self.root.attachNewNode(label)
            node.setPos(0, distance, 1.5)
            node.setScale(.55)
            node.setBillboardPointEye()
        self.root.hide(MARKER_MASK)

    def apply(self, result, origin_y):
        if result is None:
            self.root.hide(MARKER_MASK)
        else:
            self.root.setY(result.start_progress-origin_y)
            self.root.show(MARKER_MASK)
