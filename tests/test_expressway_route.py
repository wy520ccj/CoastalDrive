"""全路形、原物理表面、全局设施与山体接缝的针对性检查。"""

from itertools import pairwise
from types import SimpleNamespace

import pytest
import test_expressway
from panda3d.core import NodePath

import curve_mesh
from environment.expressway_mountains import mountain_point
from environment.expressway_route import anchor, build_segment, positions, terrain_point
from highway_curve import HighwayCurve
from highway_segments import surface_meshes
from scene import Scene

kit = test_expressway.kit


def test_speed_limit_and_triangle_warnings_have_separate_mileage_slots():
    signs = {"speed-limit", "curve-left", "curve-right", "hill-warning", "wind-warning"}
    for seed in range(25):
        curve = HighwayCurve(seed, hills=True)
        placements = [item for index in range(-2, 90) for item in positions(index, seed, curve)
                      if item[0] in signs]
        placements.sort(key=lambda item: item[2])
        assert any(item[0] == "wind-warning" for item in placements)
        for left, right in pairwise(placements):
            assert right[2] - left[2] >= 50, (seed, left, right)


def test_static_rail_coordinates_preserve_existing_geometry_and_material_channels():
    from panda3d.core import GeomVertexReader, Vec4

    from environment.surface_mesh import set_rail_shadow_coordinates
    from scene import make_mesh

    points = [(0, 0, 0), (2, 0, 0), (0, 3, 0)]
    faces = [(0, 1, 2)]
    node = make_mesh("shadow-coordinate-test", points, faces, Vec4(.11, .13, .14, 1))

    def channels():
        data = node.node().getGeom(0).getVertexData()
        result = {}
        for name, count in (("vertex", 3), ("normal", 3), ("color", 4), ("texcoord", 2)):
            reader = GeomVertexReader(data, name)
            values = []
            while not reader.isAtEnd():
                values.append(tuple({2: reader.getData2f, 3: reader.getData3f,
                                     4: reader.getData4f}[count]()))
            result[name] = values
        return result

    original = channels()
    coordinates = [(-8.5, .35), (-6.75, .35), (-8.5, .36)]
    set_rail_shadow_coordinates(node, coordinates, faces)
    assert channels() == original
    node.flattenStrong()
    node.setY(-2000)
    reader = GeomVertexReader(node.node().getGeom(0).getVertexData(), "rail_shadow_coord")
    for expected in coordinates:
        assert tuple(reader.getData2f()) == pytest.approx(expected, abs=1e-6)
    node.removeNode()


@pytest.mark.parametrize("curve", [None, HighwayCurve(23), HighwayCurve(23, hills=True)])
def test_all_shapes_keep_physical_surfaces_and_stream_lifetime(kit, curve, monkeypatch):
    import scene as scene_module

    assets, _ = kit
    captured = {}
    original = scene_module.make_mesh

    def capture(name, vertices, triangles, color):
        if name.startswith("expressway-"):
            captured[name.removeprefix("expressway-")] = (vertices, triangles)
        return original(name, vertices, triangles, color)

    monkeypatch.setattr(scene_module, "make_mesh", capture)
    scene = Scene.__new__(Scene)
    scene.render = NodePath("test-route")
    scene.segment_nodes = {}
    scene.segment_builds = {}
    scene.segment_work = {"frame_ms": 0, "max_step_ms": 0, "completed": 0,
                          "cancelled": 0, "phase": "", "near_pending": 0}
    scene.expressway_kit = assets
    scene.stabilize_rail = lambda node: None
    stream = SimpleNamespace(segments={42: []}, curve=curve)
    sim = SimpleNamespace(stream=stream, origin_y=8000, seed=23)
    scene.base = SimpleNamespace(session=SimpleNamespace(simulation=sim))
    scene.sync_segments()
    expected = curve_mesh.surfaces(curve, 42) if curve else surface_meshes()
    for name, surface in expected.items():
        if name != "ground":
            vertices, faces = captured[name]
            assert vertices == surface[0]
            assert faces == ([(a,c,b) for a,b,c in surface[1]] if curve and name.startswith("rail") else surface[1])
            if name.startswith("rail"):
                # 顶面必须朝上、底面朝下；此前曲线底面朝上，与路肩发生深度竞争。
                from panda3d.core import Vec3

                a,b,c = (Vec3(*vertices[i]) for i in faces[0])
                assert (b-a).cross(c-a).z < 0
                if curve:
                    top_faces = [f for f in faces if all(i % 4 in (2,3) for i in f)]
                else:
                    top_faces = [f for f in faces if all(i >= 4 for i in f)]
                assert top_faces
                for face in top_faces:
                    a,b,c = (Vec3(*vertices[i]) for i in face)
                    assert (b-a).cross(c-a).z > 0
    root = scene.segment_nodes[42]
    assert root.getTag("visual-route") == "HWY-02"
    x,y,z = anchor(curve,42)
    assert tuple(root.getPos()) == pytest.approx((x,y-8000,z),abs=.001)
    sim.origin_y += 2000
    scene.sync_segments()
    assert scene.segment_nodes[42] == root
    assert root.getY() == pytest.approx(y-10000,abs=.001)
    stream.segments = {-2: []}
    scene.sync_segments()
    assert root.isEmpty()
    assert set(scene.segment_nodes) == {-2}
    assert not scene.render.findAllMatches("**/+BulletRigidBodyNode")
    scene.close()


def test_facilities_are_global_and_never_double_owned():
    items = [item for index in range(-8,50) for item in positions(index,23)]
    assert len(items) == len(set(items))
    lamps = [s for model,d,s,h in items if model == "lamp" and d < 0]
    assert len(lamps) < 20
    assert all(s % 80 == 20 for s in lamps)
    assert all(abs(d)>8 for model,d,s,h in items if model not in ("gantry","overpass","drain-grate"))
    assert {item[0] for item in items} >= {"overpass","gantry","soundwall","kilometer"}


@pytest.mark.parametrize("s", [-400,0,200,800,2000,8400,100000])
def test_mountain_matches_terrain_edge_and_preserves_tree_band(s):
    curve = HighwayCurve(23,hills=True)
    for width in (20,26,32,34):
        assert terrain_point(curve,-width,s,23).z == pytest.approx(curve.sample(s).z-.32,abs=.00001)
    assert tuple(mountain_point(curve,-1,0,s,23)) == tuple(terrain_point(curve,-120,s,23))
    # 分段两侧独立计算的全局点必须一致，不依赖已加载邻段。
    for d in (-120,-35,35,120):
        a = terrain_point(curve,d,s,23)
        b = terrain_point(curve,d,s+1e-4,23)
        assert (a-b).length() < .003


def test_far_segment_build_does_not_depend_on_history(kit):
    assets,_ = kit
    root = NodePath("far-route")
    build_segment(root,500,23,assets,lambda node: None,HighwayCurve(23,hills=True))
    assert root.getTag("visual-route") == "HWY-02"
    assert root.getTightBounds()[1].y < 400
    root.removeNode()


def test_indexed_surface_preserves_triangle_attributes():
    from panda3d.core import GeomVertexReader

    from environment.surface_mesh import surface_mesh

    points = [(0,0,0),(1,0,0),(1,1,.2),(0,1,.2)]
    faces = [(0,1,2),(0,2,3)]
    colors = [(.2,.4,.6,1),(.3,.5,.7,.4)]*2
    normals = [(0,-.2,1)]*4
    uv = [(0,0),(1,0),(1,1),(0,1)]
    root = surface_mesh("probe",points,faces,normals,colors,uv)
    geom = root.node().getGeom(0)
    data = geom.getVertexData()
    assert data.getNumRows() == 4
    primitive = geom.getPrimitive(0)
    assert [primitive.getVertex(i) for i in range(6)] == [0,1,2,0,2,3]
    for name,expected in (("vertex",points),("normal",normals),("texcoord",uv),("color",colors)):
        reader = GeomVertexReader(data,name)
        for item in expected:
            actual = tuple(reader.getData4f())[:len(item)]
            assert actual == pytest.approx(item,abs=1/255 if name == "color" else 1e-6)


def test_mountain_caches_are_bounded_and_repeatable():
    from environment.expressway_mountains import mountain_height, noise_value

    before = mountain_height(48,8400,23)
    for s in range(9000):
        mountain_height(48,s,23)
    assert mountain_height.cache_info().currsize <= 8192
    assert noise_value.cache_info().currsize <= 8192
    assert mountain_height(48,8400,23) == before


def test_partial_segment_stays_detached_and_is_cancelled_on_unload(kit, monkeypatch):
    """一帧用尽预算后不能显示半段；切换方向或菜单不能遗留构建节点。"""
    import scene as scene_module

    assets, _ = kit
    scene = Scene.__new__(Scene)
    scene.render = NodePath("budget-test")
    scene.segment_nodes = {}
    scene.segment_builds = {}
    scene.segment_work = {"frame_ms": 0, "max_step_ms": 0, "completed": 0,
                          "cancelled": 0, "phase": "", "near_pending": 0}
    scene.expressway_kit = assets
    scene.stabilize_rail = lambda node: None
    stream = SimpleNamespace(segments={6: [], -6: []}, curve=HighwayCurve(23, hills=True))
    simulation = SimpleNamespace(stream=stream, origin_y=0, seed=23)
    scene.base = SimpleNamespace(session=SimpleNamespace(simulation=simulation))
    clock = iter(n * .0001 for n in range(10000))
    monkeypatch.setattr(scene_module, "perf_counter", lambda: next(clock))
    scene.sync_segments(budget_ms=1, distance=-8)
    assert set(scene.segment_builds) == {-6}
    root, steps = scene.segment_builds[-6]
    assert root.getNumChildren() > 0
    assert root.getParent().isEmpty()
    assert scene.render.getNumChildren() == 0

    # 原点移动时，未完成节点仍在局部空间；取消关闭生成器并销毁所有部分几何。
    simulation.origin_y = -2000
    stream.segments = {6: []}
    scene.sync_segments(budget_ms=0)
    assert root.isEmpty()
    assert steps.gi_frame is None
    assert scene.segment_work["cancelled"] == 1
    scene.sync_segments(budget_ms=1, distance=1208)
    closing_root, closing_steps = scene.segment_builds[6]
    scene.close()
    assert closing_root.isEmpty()
    assert closing_steps.gi_frame is None
    assert not scene.segment_builds


@pytest.mark.parametrize("curve", [None, HighwayCurve(23), HighwayCurve(23, hills=True)])
def test_budgeted_completion_attaches_whole_segment_at_current_origin(kit, monkeypatch, curve):
    from panda3d.core import SceneGraphAnalyzer

    import scene as scene_module

    assets, _ = kit
    scene = Scene.__new__(Scene)
    scene.render = NodePath("completion-test")
    scene.segment_nodes = {}
    scene.segment_builds = {}
    scene.segment_work = {"frame_ms": 0, "max_step_ms": 0, "completed": 0,
                          "cancelled": 0, "phase": "", "near_pending": 0}
    scene.expressway_kit = assets
    scene.stabilize_rail = lambda node: None
    stream = SimpleNamespace(segments={-7: []}, curve=curve)
    simulation = SimpleNamespace(stream=stream, origin_y=0, seed=23)
    scene.base = SimpleNamespace(session=SimpleNamespace(simulation=simulation))
    clock = iter(n * .0001 for n in range(100000))
    monkeypatch.setattr(scene_module, "perf_counter", lambda: next(clock))
    calls = 0
    while -7 not in scene.segment_nodes:
        scene.sync_segments(budget_ms=3, distance=-1400)
        calls += 1
        simulation.origin_y = -2000
        assert calls < 200
    assert calls > 1
    assert not scene.segment_builds
    root = scene.segment_nodes[-7]
    assert root.getParent() == scene.render
    x, y, z = anchor(curve, -7)
    assert tuple(root.getPos()) == pytest.approx((x, y + 2000, z), abs=.001)
    full = NodePath("synchronous-test")
    build_segment(full, -7, 23, assets, lambda node: None, curve)
    counts = []
    for node in (root, full):
        graph = SceneGraphAnalyzer()
        graph.addNode(node.node())
        counts.append((graph.getNumGeoms(), graph.getNumTris()))
    assert counts[0] == counts[1]
    full.removeNode()
    scene.close()
