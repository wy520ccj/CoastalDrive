"""验证真实导出模型的单位、原点和道路净空，保护装饰与仿真的边界。"""

import json
import math
import random

import gltf
import pytest
from panda3d.core import GeomVertexReader, InternalName, MaterialAttrib, NodePath, PNMImage

from coastal_map import RAIL_OFFSET, point_at, project
from environment.coastal_slice import (
    build_slice,
    build_terrain,
    dress_existing_tree,
    placements,
    road_clearance,
)
from environment.foundation import asset_path, style_existing_prop
from environment.terrain import (
    base_height,
    existing_roots,
    ground_height,
    landscape_meshes,
    shoreline_segments,
)
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
            triangles += sum(
                primitive.decompose().getNumPrimitives() for primitive in geom.getPrimitives()
            )
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


@pytest.mark.parametrize(
    "filename", ["tree_pineTallA.glb", "tree_pineTallB.glb", "rock_largeA.glb"]
)
def test_existing_collision_prop_palette_preserves_geometry(filename):
    scene = Scene.__new__(Scene)
    original = scene.load_model("nature/" + filename)
    fresh = scene.load_model("nature/" + filename)
    bounds = original.getTightBounds()
    nodes = original.findAllMatches("**/+GeomNode")
    meshes = [path.node().getGeom(i) for path in nodes for i in range(path.node().getNumGeoms())]
    style_existing_prop(original)
    assert original.getTightBounds() == bounds
    assert meshes == [
        path.node().getGeom(i) for path in nodes for i in range(path.node().getNumGeoms())
    ]
    for path in nodes:
        for state in path.node().getGeomStates():
            assert state.getAttrib(MaterialAttrib).getMaterial().getMetallic() == 0
    # 修改不能污染其他赛道重新加载的模型材质。
    for path in fresh.findAllMatches("**/+GeomNode"):
        for state in path.node().getGeomStates():
            assert state.getAttrib(MaterialAttrib).getMaterial().getMetallic() == 1


def test_sky_water_and_surface_assets_exist_and_are_packaged():
    setup = (resource_root() / "setup.py").read_text()
    for relative in (
        "sky/coastal-clouds.png",
        "materials/asphalt.png",
        "materials/meadow.png",
        "materials/limestone.png",
        "shaders/sky.vert",
        "shaders/sky.frag",
        "shaders/water.vert",
        "shaders/water.frag",
    ):
        assert asset_path(relative).exists()
    assert "assets/game/environment/shaders/*.vert" in setup
    assert "assets/game/environment/shaders/*.frag" in setup


def test_visual_ground_keeps_original_tree_roots_and_road_edge():
    from coastal_map import MAP_POINTS, offset_point

    for x, y in existing_roots():
        assert ground_height(x, y) == pytest.approx(base_height(x, y), abs=1e-5)
    inland, coast, _ = landscape_meshes()
    for i, point in enumerate(MAP_POINTS):
        assert inland["vertices"][32 * len(MAP_POINTS) + i] == pytest.approx(
            offset_point(point, -6.4)
        )
        assert coast["vertices"][i * 13] == pytest.approx(offset_point(point, 6.4))


def test_near_road_shore_preserves_existing_collision_rock_contacts():
    from coastal_map import strip_mesh
    from environment.terrain import triangle_weights
    from world_props import props_for

    original_vertices, original_faces = strip_mesh(6.4, 16, 0, -14)
    coast = landscape_meshes()[1]

    def sample(x, y, vertices, faces):
        for face in faces:
            points = [vertices[i] for i in face]
            weights = triangle_weights(x, y, points)
            if weights is not None:
                return sum(w * p[2] for w, p in zip(weights, points))
        raise AssertionError("岩石底部没有岸坡支撑")

    for prop in props_for("coastal"):
        if prop.kind == "rock":
            old = sample(prop.x, prop.y, original_vertices, original_faces)
            new = sample(prop.x, prop.y, coast["vertices"], coast["faces"])
            # 重细分的误差须小于岩体厚度，保留原岩石的可见露头。
            assert abs(new - old) < 0.06


def test_terrain_export_and_texture_coordinate_binding():
    model = build_terrain(NodePath("terrain-test"))
    assert model.findAllTextureStages()[0].getTexcoordName() == InternalName.getTexcoordName("0")
    triangles = 0
    for path in model.findAllMatches("**/+GeomNode"):
        for geom in path.node().getGeoms():
            data = geom.getVertexData()
            assert data.getFormat().hasColumn(InternalName.getTexcoordName("0"))
            uv = GeomVertexReader(data, InternalName.getTexcoordName("0"))
            values = set()
            while not uv.isAtEnd():
                point = uv.getData2f()
                values.add((round(point.x, 2), round(point.y, 2)))
            assert len(values) > 10
            triangles += sum(p.decompose().getNumPrimitives() for p in geom.getPrimitives())
    assert triangles == sum(len(mesh["faces"]) for mesh in landscape_meshes()) + 1800


@pytest.mark.parametrize(
    "filename,variant", [("tree_pineTallA.glb", "a"), ("tree_pineTallB.glb", "b")]
)
def test_replaced_canopy_keeps_original_collidable_trunk(filename, variant):
    from coastal_map import nearest_point
    from world_props import props_for

    tree = Scene.__new__(Scene).load_model("nature/" + filename)
    original_top = tree.getTightBounds()[1].z
    trunks = []
    for path in tree.findAllMatches("**/+GeomNode"):
        for index in range(path.node().getNumGeoms()):
            state = path.node().getGeomState(index)
            if state.getAttrib(MaterialAttrib).getMaterial().getName() == "woodBarkDark":
                trunks.append((path, path.getNetTransform(), path.node().getGeom(index)))
    assert trunks
    dress_existing_tree(tree, variant)
    assert tree.getTightBounds()[1].z == pytest.approx(original_top, abs=0.001)
    for path, transform, geom in trunks:
        assert path.getNetTransform() == transform
        assert geom in list(path.node().getGeoms())
    for path in tree.findAllMatches("**/+GeomNode"):
        assert all(
            s.getAttrib(MaterialAttrib).getMaterial().getName() != "leafsDark"
            for s in path.node().getGeomStates()
        )
    lower, upper = tree.getTightBounds()
    radius = math.hypot(upper.x - lower.x, upper.y - lower.y) / 2
    for prop in props_for("coastal"):
        if prop.kind == "tree" and project(prop.x, prop.y)[2] < 360:
            assert nearest_point(prop.x, prop.y)[1] - radius * prop.scale > RAIL_OFFSET + 0.2


def test_new_trees_and_rocks_are_embedded_in_final_ground():
    for item in placements():
        if item.model.startswith(("pine", "rock")):
            x, y, z = item.position
            assert ground_height(x, y) > z
            # 根部四周均须接触坡面，避免中心埋入、背坡面却悬空。
            radius = (0.24 if item.model.startswith("pine") else 0.8) * item.scale[0]
            for dx, dy in ((radius, 0), (-radius, 0), (0, radius), (0, -radius)):
                assert ground_height(x + dx, y + dy) >= z - 0.03, item


def test_baked_water_contact_matches_final_shoreline():
    image = PNMImage()
    assert image.read(asset_path("materials/shore-distance.png"))
    info = json.loads(
        (resource_root() / "assets/game/environment/materials/shore-distance.json").read_text()
    )
    assert (image.getXSize(), image.getYSize()) == (info["size"], info["size"])
    for a, b in shoreline_segments()[::13]:
        x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        ix = int((x - info["minimum"]) / info["span"] * info["size"])
        iy = info["size"] - 1 - int((y - info["minimum"]) / info["span"] * info["size"])
        assert image.getGray(ix, iy) * info["range_m"] < 1.0
    assert image.getGray(0, 0) > 0.99
