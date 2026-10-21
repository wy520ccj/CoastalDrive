"""工坊中的真实车辆预览；独立显示场景，不创建物理世界。"""

import math

from direct.gui.DirectGui import DirectFrame
from panda3d.core import (
    AmbientLight,
    CardMaker,
    DirectionalLight,
    LineSegs,
    NodePath,
    PerspectiveLens,
)

from skins import apply_skin, vehicle_for_design
from vehicle_visual import load_vehicle


class WorkshopVehicle:
    def __init__(self, base):
        self.base = base
        self.buffer = None
        self.frame = None
        self.identity = None

    def show(self, parent, box, vehicle):
        skin_index = self.base.skin_index
        if self.buffer is None:
            self.scene = NodePath('workshop-display-only')
            self.scene.setShaderAuto()
            self.buffer = self.base.win.makeTextureBuffer('workshop-vehicle', 960, 600)
            self.buffer.setClearColor((.055, .078, .092, 1))
            lens = PerspectiveLens()
            lens.setFov(38)
            lens.setAspectRatio(1.6)
            lens.setNearFar(.1, 80)
            self.camera = self.base.makeCamera(self.buffer, scene=self.scene, lens=lens)
            self.camera.setPos(5.0, 6.0, 2.8)
            self.camera.lookAt(0, 0, .60)
            ambient = AmbientLight('workshop-ambient')
            ambient.setColor((1.6, 1.7, 1.8, 1))
            self.scene.setLight(self.scene.attachNewNode(ambient))
            key = DirectionalLight('workshop-key')
            key.setColor((1.2, 1.05, .83, 1))
            light = self.scene.attachNewNode(key)
            light.setPos(4, 8, 9)
            light.lookAt(0, 0, .5)
            self.scene.setLight(light)
            wall = CardMaker('workshop-back-wall')
            wall.setFrame(-10, 10, 0, 6)
            wall_node = self.scene.attachNewNode(wall.generate())
            wall_node.setY(-6)
            wall_node.setTwoSided(True)
            wall_node.setColor(.075, .10, .12, 1)
            wall_node.setLightOff()
            floor = CardMaker('workshop-floor')
            floor.setFrame(-15, 15, -15, 15)
            surface = self.scene.attachNewNode(floor.generate())
            surface.setP(-90)
            surface.setZ(-.025)
            surface.setColor(.09, .12, .14, 1)
            lines = LineSegs('workshop-floor-joints')
            lines.setColor(.11, .15, .17, 1)
            for index in range(-6, 7):
                for a, b in (((index*2, -12, -.018), (index*2, 12, -.018)),
                             ((-12, index*2, -.018), (12, index*2, -.018))):
                    lines.moveTo(*a)
                    lines.drawTo(*b)
            self.scene.attachNewNode(lines.create())
            trim = LineSegs('workshop-bay')
            trim.setThickness(2)
            trim.setColor(.75, .48, .19, 1)
            for x in (-2., 2.):
                trim.moveTo(x, -3.5, 0)
                trim.drawTo(x, 3.5, 0)
            for x in (-7., -4., 4., 7.):
                trim.moveTo(x, -5.98, 0)
                trim.drawTo(x, -5.98, 5)
            trim.moveTo(-8, -5.98, 4.7)
            trim.drawTo(8, -5.98, 4.7)
            trim_node = self.scene.attachNewNode(trim.create())
            trim_node.setLightOff()
            self.car_root = self.scene.attachNewNode('current-vehicle')
        identity = (vehicle.design_id, vehicle.config, skin_index)
        if identity != self.identity:
            for child in self.car_root.getChildren():
                child.removeNode()
            definition = vehicle_for_design(vehicle.design_id, 'sports')
            body, self.wheels = load_vehicle(self.car_root, definition, config=vehicle.config)
            self.car_root.setZ(vehicle.config.center_of_mass_height)
            apply_skin(body.getChild(0), skin_index)
            self.identity = identity
            self.wheel_radius = vehicle.config.wheel_radius+.035
        if self.frame is not None:
            self.frame.destroy()
        self.frame = DirectFrame(parent=parent, frameSize=box, frameColor=(1, 1, 1, 1),
                                 frameTexture=self.buffer.getTexture())
        self.camera.node().getLens().setAspectRatio((box[1]-box[0])/(box[3]-box[2]))
        self.buffer.setActive(True)

    def highlight(self, topic):
        for index, wheel in enumerate(self.wheels):
            wheel.setColorScale(1, .72, .30, 1) if topic == 'tires' and index < 2 else wheel.clearColorScale()
        old = self.car_root.find('part-highlight')
        if not old.isEmpty():
            old.removeNode()
        if topic is None:
            return
        ring = LineSegs('part-highlight')
        ring.setThickness(3)
        ring.setColor(1, .66, .22, 1)
        for wheel in self.wheels[:2] if topic == 'tires' else self.wheels:
            center = wheel.getPos(self.car_root)
            for step in range(41):
                angle = step*math.pi/20
                point = (center.x*1.04, center.y+math.cos(angle)*self.wheel_radius,
                         center.z+math.sin(angle)*self.wheel_radius)
                ring.moveTo(*point) if step == 0 else ring.drawTo(*point)
        node = self.car_root.attachNewNode(ring.create())
        node.setLightOff()

    def hide(self):
        if self.buffer is not None:
            self.buffer.setActive(False)

    def close(self):
        if self.buffer is not None:
            self.frame.destroy()
            self.camera.removeNode()
            self.scene.removeNode()
            self.base.graphicsEngine.removeWindow(self.buffer)
            self.buffer = None
