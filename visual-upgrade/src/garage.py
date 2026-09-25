"""开放式海岸车库预览；整个布景随根节点一起卸载。"""

from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, DirectionalLight, PointLight, Vec3, Vec4

from skins import apply_skin
from vehicle_visual import _box, load_vehicle


class GaragePreview:
    def __init__(self, base: ShowBase, model_id: str, skin_index: int):
        self.base = base
        base.setBackgroundColor(0.31, 0.58, 0.78)
        self.root = base.render.attachNewNode("garage-preview")
        self.root.setLightOff(1)
        self.car_root = self.root.attachNewNode("car_root")
        self.angle = 0.0
        self.body = None
        self.wheels = ()
        self._build_environment()
        self.set_vehicle(model_id, skin_index)

    def _block(self, name, center, size, color, roughness=0.8, metallic=0.0):
        return _box(self.root, name, center, size, color, roughness, metallic)

    def _build_environment(self):
        from coastal_visuals import _add_ridge
        from scene import make_mesh, make_quad, water_texture
        from vehicle_visual import _ring

        # 开向海面的维修棚，梁架和地坪都保留实际三维纵深。
        self._block("garage-floor", (0, 1, -0.13), (22, 15, 0.24), (0.24, 0.25, 0.24))
        for ix in range(-6, 7):
            for iy in range(-3, 6):
                value = 0.26 + ((ix * 13 + iy * 7) % 5) * 0.014
                self._block(
                    "floor-tile",
                    (ix * 1.6, iy * 1.6, -0.002),
                    (1.575, 1.575, 0.025),
                    (value + 0.025, value + 0.02, value),
                    0.38,
                )
        for x in (-0.8, 4.1):
            self._block("bay-line", (x, 0.4, 0.018), (0.07, 6.2, 0.016), (0.95, 0.58, 0.10))
        for x in (-6.5, 7):
            self._block(
                "garage-column", (x, -4.7, 2.5), (0.35, 0.45, 5), (0.22, 0.25, 0.26), 0.5, 0.35
            )
            self._block("column-base", (x, -4.7, 0.25), (0.68, 0.7, 0.5), (0.33, 0.34, 0.32))
        self._block("roof-header", (0, -4.7, 3.8), (14, 0.5, 0.55), (0.28, 0.30, 0.29))
        for x in (-6, -3, 0, 3, 6):
            self._block("roof-beam", (x, 0, 4.1), (0.15, 10, 0.25), (0.11, 0.15, 0.17), 0.45, 0.5)
            self._block(
                "roof-beam-flange", (x, 0, 3.97), (0.32, 10, 0.05), (0.21, 0.24, 0.25), 0.5, 0.5
            )
        for y in (-4.3, -1, 2.3):
            self._block("cross-beam", (0, y, 4.22), (14, 0.18, 0.20), (0.19, 0.22, 0.23), 0.5, 0.5)
        # 海面延伸到远山，留出可见的天空与海平线。
        ocean = make_quad(
            "garage-sea", Vec3(0, -253, 0), 1000, 494, Vec4(0.045, 0.42, 0.61, 1), z=-1
        )
        ocean.reparentTo(self.root)
        ocean.setTexture(water_texture())
        ocean.setLightOff(2)
        for i in range(4):
            _add_ridge(
                self.root,
                make_mesh,
                (-90 + i * 55, -190 - i * 12, -3),
                28,
                15 + i * 3,
                60 + i,
                True,
            )
        # 维修柜、抽屉拉手、工作台和真正的圆环备胎。
        self._block(
            "tool-cabinet", (5.7, -3.7, 0.65), (1.15, 0.60, 1.3), (0.55, 0.06, 0.025), 0.4, 0.2
        )
        for z in (0.22, 0.42, 0.62, 0.82, 1.02):
            self._block(
                "drawer", (5.7, -3.385, z), (1.04, 0.03, 0.15), (0.72, 0.10, 0.04), 0.4, 0.2
            )
            self._block(
                "drawer-handle",
                (5.7, -3.36, z + 0.04),
                (0.72, 0.03, 0.025),
                (0.65, 0.68, 0.69),
                0.25,
                0.8,
            )
        self._block("worktop", (5.7, -3.7, 1.33), (1.3, 0.72, 0.08), (0.18, 0.20, 0.21), 0.4, 0.5)
        self._block("tool-board", (5.7, -4.03, 2.05), (1.5, 0.10, 1.0), (0.14, 0.18, 0.19))
        for i in range(7):
            self._block(
                "hanging-tool",
                (5.16 + i * 0.17, -3.965, 2.05),
                (0.032, 0.04, 0.48),
                (0.55, 0.59, 0.60),
                0.3,
                0.7,
            )
        for z in (0.18, 0.45, 0.72):
            tire = self.root.attachNewNode("spare-tyre")
            tire.setPos(4.6, -4, z)
            tire.setR(90)
            _ring(tire, "rubber", -0.12, 0.12, 0.34, 0.21, (0.02, 0.025, 0.03))
        for x in range(-6, 8, 2):
            self._block(
                "seaside-post", (x, -6, 0.55), (0.07, 0.09, 1.2), (0.23, 0.27, 0.28), 0.5, 0.6
            )
        for z in (0.55, 1.05):
            self._block("seaside-rail", (0, -6, z), (15, 0.08, 0.065), (0.38, 0.41, 0.41), 0.4, 0.6)

        ambient = AmbientLight("garage-ambient")
        ambient.setColor((0.12, 0.16, 0.22, 1))
        self.root.setLight(self.root.attachNewNode(ambient), 2)
        key = DirectionalLight("garage-warm-key")
        key.setColor((2.8, 2.2, 1.6, 1))
        key.setShadowCaster(True, 2048, 2048)
        key.getLens().setFilmSize(24, 24)
        key.getLens().setNearFar(1, 50)
        key_path = self.root.attachNewNode(key)
        key_path.setPos(-5, 7, 10)
        key_path.lookAt(self.car_root)
        self.root.setLight(key_path, 2)
        fill = PointLight("garage-softbox")
        fill.setColor((0.42, 0.62, 0.88, 1))
        fill_path = self.root.attachNewNode(fill)
        fill_path.setPos(7.0, -1.0, 4.3)
        fill_path.node().setAttenuation((1.0, 0.035, 0.004))
        self.root.setLight(fill_path, 2)

    def set_vehicle(self, model_id: str, skin_index: int):
        for child in self.car_root.getChildren():
            child.removeNode()
        self.body, self.wheels = load_vehicle(self.car_root, model_id)
        self.car_root.setPos(1.6, 0.0, 0.46)
        apply_skin(self.body.getChild(0), skin_index)

    def update(self, dt: float):
        self.angle = (self.angle + dt * 2.8) % 360
        self.car_root.setH(22 + self.angle * 0.16)
        self.base.camera.setPos(7.0, 9.5, 3.1)
        self.base.camera.lookAt(3.0, 0.0, 1.35)
        self.base.camLens.setFov(45)

    def close(self):
        if self.root is not None:
            self.root.removeNode()
            self.root = None
            self.car_root = None
            self.body = None
            self.wheels = ()
