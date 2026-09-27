"""验证真实车辆导出外廓、材质分区和物理快照驱动的显示轮姿。"""

import json
import math
from types import SimpleNamespace

import pytest
from panda3d.core import GeomVertexReader, MaterialAttrib, NodePath, Quat

from paths import resource_root
from scene import Scene
from simulation import Control, Simulation
from vehicle_config import CAR
from vehicle_visual import WHEEL_NAMES, load_vehicle


def vertices_relative_to(root):
    for path in root.findAllMatches("**/+GeomNode"):
        matrix = path.getMat(root)
        for geom in path.node().getGeoms():
            reader = GeomVertexReader(geom.getVertexData(), "vertex")
            while not reader.isAtEnd():
                yield matrix.xformPoint(reader.getData3f())


def test_hero_body_and_steered_rolling_wheels_fit_frozen_collision_envelope():
    parent = NodePath("visual-contract")
    body, wheels = load_vehicle(parent, "sports")
    for vertex in vertices_relative_to(body):
        assert abs(vertex.x) <= CAR.collision_half_width
        assert abs(vertex.y) <= CAR.collision_half_length
    assert tuple(w.getName() for w in wheels) == WHEEL_NAMES
    for wheel in wheels:
        hub = wheel.getPos()
        assert abs(hub.x) == pytest.approx(CAR.track_width / 2)
        assert abs(hub.y) == pytest.approx(CAR.wheelbase / 2)
        assert hub.z == pytest.approx(-0.12)
        # 逐顶点扫过完整转动和满舵，不能用轮胎包围盒角点代替圆肩胎面。
        points = tuple(vertices_relative_to(wheel))
        assert max(math.hypot(p.y, p.z) for p in points) == pytest.approx(
            CAR.wheel_radius, abs=0.004
        )
        for steering in (-CAR.steering_degrees, 0, CAR.steering_degrees):
            angle = math.radians(steering if hub.y > 0 else 0)
            for roll in range(0, 360, 30):
                rotation = math.radians(roll)
                for point in points:
                    y = point.y * math.cos(rotation) - point.z * math.sin(rotation)
                    x = hub.x + point.x * math.cos(angle) - y * math.sin(angle)
                    y = hub.y + point.x * math.sin(angle) + y * math.cos(angle)
                    assert abs(x) <= CAR.collision_half_width
                    assert abs(y) <= CAR.collision_half_length


def test_export_has_distinct_materials_and_bounded_geometry():
    parent = NodePath("asset-materials")
    load_vehicle(parent, "sports")
    materials = set()
    triangles = 0
    for path in parent.findAllMatches("**/+GeomNode"):
        node = path.node()
        for geom, state in zip(node.getGeoms(), node.getGeomStates()):
            material = state.getAttrib(MaterialAttrib).getMaterial()
            materials.add(material.getName())
            if material.getName() == "Tire Rubber":
                assert material.getRoughness() >= 0.85
                assert material.getMetallic() == 0
            if material.getName() == "Blue Grey Glass":
                assert material.getBaseColor().z > material.getBaseColor().x
            triangles += sum(p.decompose().getNumPrimitives() for p in geom.getPrimitives())
    assert {
        "Body Paint",
        "Blue Grey Glass",
        "Satin Black Plastic",
        "Tire Rubber",
        "Brushed Wheel Metal",
        "Tail Light",
        "Head Light",
    } <= materials
    manifest = json.loads(
        (resource_root() / "assets/game/vehicles/classic-coupe-manifest.json").read_text()
    )
    assert triangles == manifest["triangles"]
    assert triangles <= manifest["triangle_budget"]


def test_sedan_and_npc_sports_keep_legacy_body_and_wheel_geometry():
    parent = NodePath("legacy-vehicles")
    for model_id in ("sports", "sedan"):
        body, wheels = load_vehicle(parent, model_id, hero=False)
        assert body.getChild(0).getName() != "classic-coupe-v1"
        assert len(wheels) == 4
        assert not body.findAllMatches("**/paint").isEmpty()
        if model_id == "sedan":
            other, other_wheels = load_vehicle(parent, model_id)
            assert other.getTightBounds() == body.getTightBounds()
            assert [w.getTightBounds() for w in wheels] == [
                w.getTightBounds() for w in other_wheels
            ]


def test_scene_applies_actual_bullet_wheel_positions_and_quaternions():
    simulation = Simulation(track="test", traffic_count=0)
    scene = Scene.__new__(Scene)
    scene.render = NodePath("wheel-sync")
    scene.sky = scene.render.attachNewNode("sky")
    scene.base = SimpleNamespace(session=SimpleNamespace(simulation=simulation))
    scene.player, scene.wheels = load_vehicle(scene.render, "sports")
    scene.traffic, scene.traffic_wheels, scene.traffic_signals = [], [], []
    try:
        for tick in range(360):
            simulation.step(Control(throttle=0.45, steering=0.15 if tick > 180 else 0))
            if tick % 30:
                continue
            snapshot = simulation.snapshot()
            scene.apply(snapshot)
            assert tuple(scene.player.getPos()) == pytest.approx(snapshot.player.position)
            for node, state in zip(scene.wheels, snapshot.player.wheels):
                assert tuple(node.getPos()) == pytest.approx(state.position)
                assert abs(node.getQuat().dot(Quat(*state.orientation))) == pytest.approx(
                    1, abs=1e-5
                )
        assert snapshot.player.speed > 1
    finally:
        simulation.close()


def test_hero_color_space_and_local_ambient_do_not_change_scene_or_npcs():
    from panda3d.core import AmbientLight, DirectionalLight, LightAttrib

    from skins import SKINS, paint_color

    parent = NodePath("lighting-contract")
    ambient = parent.attachNewNode(AmbientLight("world-fill"))
    ambient.node().setColor((0.3, 0.4, 0.5, 1))
    sun = parent.attachNewNode(DirectionalLight("world-sun"))
    parent.setLight(ambient)
    parent.setLight(sun)
    before = parent.getState()
    body, wheels = load_vehicle(parent, "sports")
    for node in (body, *wheels):
        lights = node.getNetState().getAttrib(LightAttrib)
        assert not lights.hasOnLight(ambient)
        assert lights.hasOnLight(sun)
        assert lights.getNumOnLights() == 2
    npc, _ = load_vehicle(parent, "sports", hero=False)
    assert npc.getNetState().getAttrib(LightAttrib).hasOnLight(ambient)
    assert parent.getState() == before
    # 已知sRGB参考值，防止把测试写成转换实现的复制品。
    assert paint_color(0, hero=True) == pytest.approx((0.7874123, 0.1548725, 0.0100228), abs=1e-6)
    assert paint_color(0) == SKINS[0].color
