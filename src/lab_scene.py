"""实验车辆视窗；姿态和轮姿只读取完成步快照。"""

import math

from panda3d.core import AmbientLight, CardMaker, DirectionalLight, LineSegs, Quat, Vec3

from lab_maneuvers import bump_geometry, reference_path
from skins import apply_skin, vehicle_for_design
from vehicle_visual import load_vehicle


class LabScene:
    def __init__(self, base):
        self.base = base
        self.root = base.render.attachNewNode("vehicle-lab-scene")
        self.vehicle = None
        self.wheels = ()
        self.camera_mode = 0
        self.path_bounds = None
        self.path_node = self.root.attachNewNode("trajectory")
        self.reference_node = self.root.attachNewNode("reference-path")
        self.surface_node = self.root.attachNewNode("surface-markings")
        floor = CardMaker("lab-ground")
        floor.setFrame(-1000, 1000, -1000, 1000)
        self.floor = self.root.attachNewNode(floor.generate())
        self.floor.setP(-90)
        self.floor.setZ(-.015)
        self.floor.setColor(.47, .52, .51, 1)
        grid = LineSegs()
        grid.setColor(.65, .70, .65, 1)
        for offset in range(-400, 800, 10):
            grid.moveTo(offset, -400, .001)
            grid.drawTo(offset, 800, .001)
            grid.moveTo(-400, offset, .001)
            grid.drawTo(800, offset, .001)
        grid_node = self.root.attachNewNode(grid.create())
        grid_node.setShaderOff()
        grid_node.setLightOff()
        ambient = AmbientLight("lab-ambient")
        ambient.setColor((.48, .53, .60, 1))
        self.root.setLight(self.root.attachNewNode(ambient))
        key = DirectionalLight("lab-key")
        key.setColor((1.8, 1.7, 1.5, 1))
        key.setShadowCaster(True, 1024, 1024)
        key.getLens().setFilmSize(22, 22)
        key.getLens().setNearFar(1, 60)
        self.light = self.root.attachNewNode(key)
        self.light.setPos(105, -12, 20)
        self.light.lookAt(95, 0, .4)
        self.root.setLight(self.light)

    def set_vehicle(self, design, config=None):
        config = design.config if config is None else config
        self.config = config
        if self.vehicle is not None:
            self.vehicle.removeNode()
            for wheel in self.wheels:
                wheel.removeNode()
        definition = vehicle_for_design(design.id, "sports")
        self.vehicle, self.wheels = load_vehicle(self.root, definition, config=config)
        apply_skin(self.vehicle.getChild(0), 0)
        position = Vec3(95, 0, config.center_of_mass_height)
        self.vehicle.setPos(position)
        for wheel in self.wheels:
            wheel.setPos(wheel.getPos()+position)

    def apply(self, snapshot):
        state = snapshot.player
        self.vehicle.setPos(*state.position)
        self.vehicle.setQuat(Quat(*state.orientation))
        for visual, wheel in zip(self.wheels, state.wheels):
            visual.setPos(*wheel.position)
            visual.setQuat(Quat(*wheel.orientation))
        position = Vec3(*state.position)
        offsets = (Vec3(6, -9, 4), Vec3(0, 0, 24), Vec3(15, 0, 3))
        self.base.camLens.setFov(48)
        if self.camera_mode == 1 and self.path_bounds is not None:
            left, right, bottom, top = self.path_bounds
            center = Vec3((left+right)/2, (bottom+top)/2, 0)
            lens = self.base.camLens
            altitude = max(24., (top-bottom)/(2*math.tan(math.radians(lens.getHfov()/2))),
                           (right-left)/(2*math.tan(math.radians(lens.getVfov()/2))))*1.15
            self.base.camera.setPos(center+Vec3(0, 0, altitude))
            self.base.camera.setHpr(90, -90, 0)
        else:
            self.base.camera.setPos(position+offsets[self.camera_mode])
            self.base.camera.lookAt(position+Vec3(0, 0, .35))
        self.light.setPos(position+Vec3(10, -12, 20))
        self.light.lookAt(position)

    def trajectory(self, snapshots):
        self.path_node.removeNode()
        line = LineSegs()
        line.setColor(.26, .85, .81, 1)
        line.setThickness(2)
        for index, snapshot in enumerate(snapshots):
            x, y, _ = snapshot.player.position
            line.drawTo(x, y, .025) if index else line.moveTo(x, y, .025)
        self.path_node = self.root.attachNewNode(line.create())
        self.path_node.setShaderOff()
        self.path_node.setLightOff()
        self.path_node.setDepthTest(False)
        self.path_node.setDepthWrite(False)
        self.path_node.setBin("fixed", 10)
        self.path_node.setColor(.14, .49, .59, 1)
        self.path_bounds = (min(state.player.position[0] for state in snapshots)-5,
                            max(state.player.position[0] for state in snapshots)+5,
                            min(state.player.position[1] for state in snapshots)-5,
                            max(state.player.position[1] for state in snapshots)+5)

    def set_trial(self, options, initial):
        """目标路径和对开附着分界与记录使用同一工况坐标。"""
        self.reference_node.removeNode()
        self.surface_node.removeNode()
        line = LineSegs()
        line.setColor(.95, .94, .86, 1)
        line.setThickness(2)
        for index, (x, y) in enumerate(reference_path(options, initial)):
            line.drawTo(x, y, .018) if index else line.moveTo(x, y, .018)
        self.reference_node = self.root.attachNewNode(line.create())
        self.reference_node.setShaderOff()
        self.reference_node.setLightOff()
        self.reference_node.setDepthTest(False)
        self.reference_node.setDepthWrite(False)
        self.reference_node.setBin("fixed", 5)
        self.surface_node = self.root.attachNewNode("surface-markings")
        if options.maneuver == "ride_bump":
            center, half = bump_geometry(options, initial.position, self.config)
            card = CardMaker("left-bump-top")
            card.setFrame(-half[0], half[0], -half[1], half[1])
            top = self.surface_node.attachNewNode(card.generate())
            top.setP(-90)
            top.setPos(center[0], center[1], options.bump_height_m)
            top.setColor(.98, .43, .10, 1)
        if options.maneuver == "split_braking":
            boundary = initial.position[0]
            for name, low, high, color in (("mu-left", boundary-500, boundary, (.43, .48, .47, 1)),
                                          ("mu-right", boundary, boundary+500, (.58, .60, .54, 1))):
                card = CardMaker(name)
                card.setFrame(low, high, -500, 1000)
                side = self.surface_node.attachNewNode(card.generate())
                side.setP(-90)
                side.setZ(-.008)
                side.setColor(*color)

    def close(self):
        self.root.removeNode()
