"""验证真实导出模型的单位、原点和道路净空，保护装饰与仿真的边界。"""

import json
import math
import random

import gltf
import pytest
from panda3d.core import MaterialAttrib, NodePath

from coastal_map import RAIL_OFFSET, point_at, project
from environment.coastal_slice import build_slice, placements, road_clearance
from environment.foundation import asset_path, style_existing_prop
from paths import resource_root
from scene import Scene

MANIFEST = json.loads((resource_root() / "assets/game/environment/kit-manifest.json").read_text())


@pytest.mark.parametrize("entry", MANIFEST["assets"], ids=lambda item: item["name"])
def test_exported_models_have_ground_pivot_and_measured_bounds(entry):
    model = NodePath(gltf.load_model(asset_path(entry["file"])))
    lower, upper = model.getTightBounds()
    assert lower.z == pytest.approx(0, abs=0.001)
    assert lower.x + upper.x == pytest.approx(0, abs=0.002)
    assert lower.y + upper.y == pytest.approx(0, abs=0.002)
    assert tuple(upper - lower) == pytest.approx(tuple(entry["bounds_m"].values()), abs=0.002)
    triangles = 0
    for path in model.findAllMatches("**/+GeomNode"):
        for geom in path.node().getGeoms():
            triangles += sum(primitive.decompose().getNumPrimitives()
                             for primitive in geom.getPrimitives())
    assert triangles == entry["triangles"]
    assert sum(item["triangles"] for item in MANIFEST["assets"]) < MANIFEST["triangle_budget"]


def test_decorations_keep_full_footprints_outside_rails_and_do_not_use_global_rng():
    before = random.getstate()
    items = placements()
    assert items == placements()
    assert random.getstate() == before
    dimensions = {item["name"]: item["bounds_m"] for item in MANIFEST["assets"]}
    for item in items:
        bounds = dimensions[item.model]
        # 包围圆比旋转后的矩形更保守：整个外廓仍须离开护栏。
        radius = math.hypot(bounds["x"] * item.scale[0], bounds["y"] * item.scale[1]) / 2
        assert road_clearance(item) - radius > RAIL_OFFSET + 0.2, item
        if item.model in {"flowers_coastal_a", "bush_round_a", "bush_round_b"}:
            assert 0 <= project(*item.position[:2])[2] <= 365
    root = NodePath("test-decorations")
    build_slice(root)
    assert root.findAllMatches("**/+BulletRigidBodyNode").getNumPaths() == 0
    assert root.findAllMatches("**/+CollisionNode").getNumPaths() == 0


def test_road_signs_point_into_the_actual_bend():
    for sign in (item for item in placements() if item.model == "road_chevron_sign_a"):
        distance = project(*sign.position[:2])[2]
        turn = (point_at(distance + 12).heading - point_at(distance - 12).heading + 180) % 360 - 180
        assert (sign.scale[0] < 0) == (turn > 0)


@pytest.mark.parametrize("filename", ["tree_pineTallA.glb", "tree_pineTallB.glb", "rock_largeA.glb"])
def test_existing_collision_prop_palette_preserves_geometry(filename):
    scene = Scene.__new__(Scene)
    original = scene.load_model("nature/" + filename)
    fresh = scene.load_model("nature/" + filename)
    bounds = original.getTightBounds()
    nodes = original.findAllMatches("**/+GeomNode")
    meshes = [path.node().getGeom(i) for path in nodes for i in range(path.node().getNumGeoms())]
    style_existing_prop(original)
    assert original.getTightBounds() == bounds
    assert meshes == [path.node().getGeom(i) for path in nodes
                      for i in range(path.node().getNumGeoms())]
    for path in nodes:
        for state in path.node().getGeomStates():
            assert state.getAttrib(MaterialAttrib).getMaterial().getMetallic() == 0
    # 修改不能污染其他赛道重新加载的模型材质。
    for path in fresh.findAllMatches("**/+GeomNode"):
        for state in path.node().getGeomStates():
            assert state.getAttrib(MaterialAttrib).getMaterial().getMetallic() == 1


def test_sky_water_and_surface_assets_exist_and_are_packaged():
    setup = (resource_root() / "setup.py").read_text()
    for relative in ("sky/coastal-clouds.png", "materials/asphalt.png", "materials/meadow.png",
                     "materials/limestone.png", "shaders/sky.vert", "shaders/sky.frag",
                     "shaders/water.vert", "shaders/water.frag"):
        assert asset_path(relative).exists()
    assert "assets/game/environment/shaders/*.vert" in setup
    assert "assets/game/environment/shaders/*.frag" in setup
