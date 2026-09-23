"""Static garage preview for the main menu."""

from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, CardMaker, DirectionalLight

from skins import apply_skin
from vehicle_visual import load_vehicle


class GaragePreview:
    def __init__(self, base: ShowBase, model_id: str, skin_index: int):
        self.base = base
        base.setBackgroundColor(0.035, 0.05, 0.08)
        self.root = base.render.attachNewNode("garage-preview")
        self.car_root = self.root.attachNewNode("car_root")
        self.floor = self._make_floor()
        self._make_lights()
        self.angle = 0.0
        self.body = None
        self.wheels = ()
        self.set_vehicle(model_id, skin_index)

    def _make_floor(self):
        card = CardMaker("garage-floor")
        card.setFrame(-8, 8, -5, 5)
        floor = self.root.attachNewNode(card.generate())
        floor.setP(-90)
        floor.setZ(-0.02)
        floor.setColor(0.08, 0.11, 0.15, 1)
        return floor

    def _make_lights(self):
        ambient = AmbientLight("garage-ambient")
        ambient.setColor((0.32, 0.36, 0.44, 1))
        self.root.setLight(self.root.attachNewNode(ambient))
        key = DirectionalLight("garage-key")
        key.setColor((1.4, 1.25, 1.1, 1))
        key.setShadowCaster(True, 2048, 2048)
        key.getLens().setFilmSize(12, 12)
        key.getLens().setNearFar(1, 40)
        key_path = self.root.attachNewNode(key)
        key_path.setPos(5, -7, 8)
        key_path.lookAt(self.car_root)
        self.root.setLight(key_path)

    def set_vehicle(self, model_id: str, skin_index: int):
        for child in self.car_root.getChildren():
            child.removeNode()
        self.body, self.wheels = load_vehicle(self.car_root, model_id)
        self.car_root.setZ(0.45)
        apply_skin(self.body.getChild(0), skin_index)

    def update(self, dt: float):
        self.angle = (self.angle + dt * 8.0) % 360
        self.car_root.setH(self.angle)
        self.base.camera.setPos(8.4, -10.5, 4.2)
        self.base.camera.lookAt(1.7, 0, 0.75)
        self.base.camLens.setFov(52)

    def close(self):
        if self.root is not None:
            self.root.removeNode()
            self.root = None
            self.car_root = None
            self.body = None
            self.wheels = ()
