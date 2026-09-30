"""检查真实高速模块、既有碰撞树和流送边界，不用短测代替人工观感。"""

import math
from itertools import pairwise
from types import SimpleNamespace

import pytest
from panda3d.core import GeomVertexReader, Loader, LoaderOptions, NodePath

from environment.expressway import (
    END,
    KIT_NAMES,
    build_segment,
    includes,
    load_kit,
    placements,
    terrain_height,
)
from highway_segments import segment
from scene import Scene


class AssetLoader:
    def loadModel(self, path):
        return NodePath(Loader.getGlobalPtr().loadSync(path, LoaderOptions()))

    def loadTexture(self, path):
        from panda3d.core import TexturePool

        return TexturePool.loadTexture(path)


@pytest.fixture
def kit():
    parent = NodePath("templates")
    scene = Scene.__new__(Scene)
    trees = [scene.load_model(f"nature/tree_pineTall{variant}.glb") for variant in ("A", "B")]
    result = load_kit(AssetLoader(), parent, trees)
    yield result, trees
    parent.removeNode()


def vertices(node):
    for path in node.findAllMatches("**/+GeomNode"):
        for geom in path.node().getGeoms():
            reader = GeomVertexReader(geom.getVertexData(), "vertex")
            while not reader.isAtEnd():
                yield node.getRelativePoint(path, reader.getData3f())


def test_kit_clearance_uses_serialized_geometry(kit):
    assets, _ = kit
    for name in KIT_NAMES:
        assert not assets[name].isEmpty()
        assert all(math.isfinite(c) for p in vertices(assets[name]) for c in p)
    for name in ("gantry", "overpass"):
        # 检查跨越道路的三角形，不能只检查端点以漏掉整跨桥面。
        over_road = []
        for path in assets[name].findAllMatches("**/+GeomNode"):
            for geom in path.node().getGeoms():
                reader = GeomVertexReader(geom.getVertexData(), "vertex")
                for primitive in geom.getPrimitives():
                    tris = primitive.decompose()
                    for i in range(tris.getNumPrimitives()):
                        points = []
                        for j in range(tris.getPrimitiveStart(i), tris.getPrimitiveEnd(i)):
                            reader.setRow(tris.getVertex(j))
                            points.append(assets[name].getRelativePoint(path, reader.getData3f()))
                        if min(p.x for p in points) < 8.5 and max(p.x for p in points) > -8.5:
                            over_road.extend(p.z for p in points)
        assert min(over_road) > 5.7
    for index in range(4):
        for name, x, _, _, heading in placements(index):
            if name in ("gantry", "overpass", "drain-grate", "reflector"):
                continue
            node = assets[name].copyTo(NodePath("measure"))
            node.setPos(x, 0, 0)
            node.setH(heading)
            if name == "lamp":
                points = [node.getParent().getRelativePoint(node, p) for p in vertices(node)
                          if p.z < 5.7]
                assert all(abs(p.x) > 8.5 for p in points)
                continue
            low, high = node.getTightBounds(node.getParent())
            assert low.x > 8.5 or high.x < -8.5


def test_collision_tree_roots_and_trunks_survive(kit):
    assets, originals = kit
    from panda3d.core import MaterialAttrib

    def trunk(node):
        result = []
        for path in node.findAllMatches("**/+GeomNode"):
            mesh = path.node()
            for i in range(mesh.getNumGeoms()):
                mat = mesh.getGeomState(i).getAttrib(MaterialAttrib)
                if mat is not None and mat.getMaterial().getName() == "woodBarkDark":
                    reader = GeomVertexReader(mesh.getGeom(i).getVertexData(), "vertex")
                    while not reader.isAtEnd():
                        result.append(tuple(node.getRelativePoint(path, reader.getData3f())))
        return result

    for i, original in enumerate(originals):
        assert trunk(assets[f"tree-{i}"]) == trunk(original)
        assert trunk(original)
    for seed in (0, 17, 23):
        for index in range(4):
            for x, y, _, _ in segment(seed, index).trees:
                for dx in (-0.3, 0, 0.3):
                    assert terrain_height(x + dx, index * 200 + y) == pytest.approx(-0.32)


def test_scope_spacing_and_global_boundary():
    assert [i for i in range(-2, 7) if includes(i, None)] == [0, 1, 2, 3]
    assert not includes(1, object())
    items = [(name, x, y + i * 200) for i in range(4)
             for name, x, y, _, _ in placements(i)]
    lamps = sorted(s for name, x, s in items if name == "lamp" and x < 0)
    assert all(b - a == 40 for a, b in pairwise(lamps))
    assert all(0 <= s < END for _, _, s in items)
    for x in (-120, -72, -35, -8.5, 8.5, 35, 72, 120):
        assert terrain_height(x, 0) == pytest.approx(-0.32)
        assert terrain_height(x, 800) == pytest.approx(-0.32)
        for boundary in (200, 400, 600):
            assert abs(terrain_height(x, boundary - 1e-6)
                       - terrain_height(x, boundary + 1e-6)) < 1e-5


def test_scene_segment_unload_reload_and_rebase(kit):
    assets, _ = kit
    scene = Scene.__new__(Scene)
    scene.render = NodePath("scene")
    scene.segment_nodes = {}
    scene.segment_builds = {}
    scene.segment_work = {"frame_ms": 0, "max_step_ms": 0, "completed": 0,
                          "cancelled": 0, "phase": "", "near_pending": 0}
    scene.expressway_kit = assets
    scene.stabilize_rail = lambda node: None
    stream = SimpleNamespace(segments={0: [], 1: [], 2: [], 3: []}, curve=None)
    simulation = SimpleNamespace(stream=stream, origin_y=0, seed=23)
    scene.base = SimpleNamespace(session=SimpleNamespace(simulation=simulation))
    scene.sync_segments()
    old = scene.segment_nodes[2]
    initial = [scene.segment_nodes[i].getNumChildren() for i in range(4)]
    assert all(scene.segment_nodes[i].getTag("visual-route") == "HWY-02" for i in range(4))
    simulation.origin_y = 2000
    scene.sync_segments()
    assert scene.segment_nodes[2] == old
    assert old.getY() == -1600
    stream.segments = {}
    scene.sync_segments()
    assert old.isEmpty()
    assert not scene.segment_nodes
    stream.segments = {i: [] for i in range(4)}
    scene.sync_segments()
    assert [scene.segment_nodes[i].getNumChildren() for i in range(4)] == initial
    scene.close()


def test_build_is_presentation_only(kit):
    import random

    assets, _ = kit
    rng = random.getstate()
    root = NodePath("slice")
    build_segment(root, 1, 23, assets, lambda node: None)
    assert random.getstate() == rng
    assert root.findAllMatches("**/+BulletRigidBodyNode").getNumPaths() == 0
    assert root.getTightBounds()[0].z > -5


def test_shadow_grid_stays_world_aligned_across_rebase():
    from panda3d.core import DirectionalLight, Vec3

    from environment.expressway import stabilize_sun

    light = DirectionalLight("probe")
    light.setShadowCaster(True, 2048, 2048)
    light.getLens().setFilmSize(95, 95)
    light.getLens().setNearFar(10, 300)
    sun = NodePath(light)
    for y in (130.0, 130.08, 130.16, 2007.5):
        stabilize_sun(sun, Vec3(-3.5, y, 0.5), 0)
        position = sun.getPos()
        local = sun.getQuat().conjugate().xform(position)
        for axis in (0, 2):
            # Panda的节点存储为float32；2km处来回投影误差上界取1mm。
            step = 95 / 2048
            assert local[axis] == pytest.approx(round(local[axis] / step) * step, abs=0.001)
        stabilize_sun(sun, Vec3(-3.5, y - 2000, 0.5), 2000)
        assert tuple(sun.getPos() + Vec3(0, 2000, 0)) == pytest.approx(tuple(position), abs=0.001)
    assert light.isShadowCaster()
    assert light.getLens().getFilmSize() == (95, 95)
    assert light.getShadowBufferSize() == (2048, 2048)


def test_landscape_has_real_color_detail_and_matching_shore(kit):
    from panda3d.core import Filename, PNMImage

    from environment.expressway import build_terrain, support_height
    from paths import resource_root

    assets, _ = kit
    root = NodePath("landscape")
    build_terrain(root, 2, assets)
    surfaces = root.findAllMatches("**/expressway-landscape")
    assert len(surfaces) == 2
    for surface in surfaces:
        assert surface.getTexture() == assets["ground"]
        reader = GeomVertexReader(surface.node().getGeom(0).getVertexData(), "color")
        colors = set()
        while not reader.isAtEnd():
            colors.add(tuple(round(c, 3) for c in reader.getData4f()))
        assert len(colors) > 256
    profile = PNMImage()
    assert profile.read(Filename.fromOsSpecific(str(resource_root() / "assets/game/expressway/shore-profile.png")))
    for s in (100, 250, 400, 510, 600, 700):
        x = profile.getGray(s, 0) * 160
        assert abs(support_height(x, s) + 3) < 0.005
