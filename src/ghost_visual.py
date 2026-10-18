"""幽灵只有渲染节点；专用相机位避开阴影，并在主车附近渐隐。"""

import math

from panda3d.core import BitMask32, Quat, TransparencyAttrib

from vehicle_visual import batch_driving_geometry, load_vehicle

GHOST_MASK = BitMask32.bit(29)


class GhostVisual:
    def __init__(self, parent, definition, config, sun):
        self.root = parent.attachNewNode("personal-best-ghost")
        try:
            self.body, self.wheels = load_vehicle(self.root, definition, config=config)
        except (OSError, ValueError, RuntimeError):
            self.root.removeNode()
            raise
        batch_driving_geometry(self.body, self.wheels)
        self.root.hide(BitMask32.allOn())
        self.root.show(GHOST_MASK)
        sun.node().setCameraMask(sun.node().getCameraMask() & ~GHOST_MASK)
        self.root.setShaderOff(10)
        self.root.setLightOff(10)
        self.root.setTextureOff(10)
        self.root.setMaterialOff(10)
        self.root.setTransparency(TransparencyAttrib.MAlpha, 10)
        self.root.setDepthWrite(False, 10)
        self.root.setColor(.18, .75, 1., .25, 10)
        self.root.setBin("transparent", 0)
        self.root.hide(GHOST_MASK)

    def apply(self, pose, player_position, enabled):
        if not enabled or pose is None:
            self.root.hide(GHOST_MASK)
            return
        distance = math.dist(pose.position, player_position)
        if distance <= 3.:
            self.root.hide(GHOST_MASK)
            return
        self.root.show(GHOST_MASK)
        self.root.setColor(.18, .75, 1., .28*min(1., (distance-3.)/5.), 10)
        self.body.setPos(*pose.position)
        self.body.setHpr(*pose.hpr)
        for node, wheel in zip(self.wheels, pose.wheels):
            node.setPos(*wheel.position)
            node.setQuat(Quat(*wheel.orientation))
