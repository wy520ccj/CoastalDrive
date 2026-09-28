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
    scene.expressway_kit = assets
    scene.stabilize_rail = lambda node: None
    stream = SimpleNamespace(segments={0: [], 1: [], 2: [], 3: []}, curve=None)
    simulation = SimpleNamespace(stream=stream, origin_y=0, seed=23)
    scene.base = SimpleNamespace(session=SimpleNamespace(simulation=simulation))
    scene.sync_segments()
    old = scene.segment_nodes[2]
    initial = [scene.segment_nodes[i].getNumChildren() for i in range(4)]
    assert all(scene.segment_nodes[i].getTag("visual-slice") == "HWY-01" for i in range(4))
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
