"""城市必须落在连续大陆上，原路肩/碰撞树带和路段所有权保持。"""

import sys
from pathlib import Path

import pytest
import test_expressway
from panda3d.core import NodePath, Vec3

from environment.expressway_city import city_steps
from environment.expressway_route import anchor, city_weight, ground_height, terrain_point
from highway_curve import HighwayCurve

kit = test_expressway.kit


@pytest.mark.parametrize('seed', (0, 17, 23))
def test_city_is_supported_by_continuous_mainland(seed):
    distance = 4000-seed % 5*160
    curve = HighwayCurve(seed, hills=True)
    assert city_weight(distance, seed) == 1
    for across in range(201, 301, 5):
        assert terrain_point(curve, across, distance, seed).z == pytest.approx(.85, abs=1e-4)
    for across in (41, 51, 66, 86, 101, 116, 131):
        assert terrain_point(curve, across, distance, seed).z == pytest.approx(
            max(.85, curve.sample(distance).z-1.5), abs=1e-4)
    for across in (20, 26, 32, 34, 35):
        assert ground_height(across, distance, 20, seed) == -.32
    assert terrain_point(curve, 400, distance, seed).z == pytest.approx(-4.4, abs=1e-4)


@pytest.mark.parametrize('edge', (3200, 3440, 6160, 6400))
def test_urban_terrain_has_no_step_at_region_boundary(edge):
    for across in (35, 65, 120, 190, 280, 340, 400):
        a = ground_height(across, edge-1e-4, 15, 0)
        b = ground_height(across, edge+1e-4, 15, 0)
        assert abs(a-b) < 1e-4


def test_city_segment_owns_buildings_streets_and_shared_lods(kit):
    assets, _ = kit
    curve = HighwayCurve(0, hills=True)
    index = 19
    root = NodePath('city-block')
    origin = Vec3(*anchor(curve, index))
    phases = list(city_steps(root, index, 0, curve, assets))
    try:
        assert phases.count('city-building') == 8
        assert root.find('**/city-quay').isEmpty()
        buildings = root.findAllMatches('**/=city-footprint')
        assert len(buildings) == 8
        foundations = {node.getTag('city-lot'): node for node in root.findAllMatches('**/city-foundation')}
        assert len(foundations) == 8
        for building in buildings:
            assert building.getZ(root)+origin.z >= .50
            width, depth = map(float, building.getTag('city-footprint').split())
            foundation = foundations[building.getTag('city-lot')]
            bottom, top = foundation.getTightBounds(foundation)
            assert foundation.getZ(root)+top.z == pytest.approx(building.getZ(root), abs=1e-4)
            # 检查真实基础四角：底部入土，水平顶面托住楼体，不把门埋进纵坡。
            for x in (-width/2-.12, width/2+.12):
                for y in (-depth/2-.12, depth/2+.12):
                    corner = root.getRelativePoint(foundation, Vec3(x, y, bottom.z))+origin
                    distance, across = curve.project(tuple(corner))
                    ground = terrain_point(curve, across, distance, 0).z
                    assert corner.z <= ground+.02
                    assert ground <= foundation.getZ(root)+top.z+origin.z
            lod = building.find('**/+LODNode').node()
            assert lod.getNumSwitches() == 2
            near, far = building.find('**/city-near'), building.find('**/city-far')
            assert near.getTightBounds() == far.getTightBounds()
        assert root.findAllMatches('**/city-local-street').getNumPaths() == 2
        trees = root.findAllMatches('**/=city-tree')
        assert len(trees) == 8
        for tree in trees:
            low, high = tree.getTightBounds(root)
            assert 5.999 <= high.z-low.z <= 8.001
        assert root.findAllMatches('**/+BulletRigidBodyNode').getNumPaths() == 0
        assert len(assets['city-models']) == 4
    finally:
        root.removeNode()


def test_natural_coast_does_not_receive_city_nodes(kit):
    root = NodePath('natural-coast')
    try:
        assert list(city_steps(root, 0, 0, HighwayCurve(0, hills=True), kit[0])) == []
        assert root.getNumChildren() == 0
    finally:
        root.removeNode()


def test_city_front_doors_face_streets_and_leave_courtyard_clear(kit):
    curve = HighwayCurve(0, hills=True)
    root = NodePath('city-layout')
    origin = Vec3(*anchor(curve, 19))
    try:
        list(city_steps(root, 19, 0, curve, kit[0]))
        buildings = root.findAllMatches('**/=city-footprint')
        for building in buildings:
            width, depth = map(float, building.getTag('city-footprint').split())
            center = building.getPos(root)+origin
            _s, across = curve.project(tuple(center))
            if int(building.getTag('city-lot')) < 4:
                assert 60 < across < 76
            road = 41 if across < 85 else 131
            gate = root.getRelativePoint(building, Vec3(-width/2-7.5, 0, 0))+origin
            _gate_s, gate_d = curve.project(tuple(gate))
            assert abs(gate_d-road) < abs(across-road)
            for x in (-width/2, width/2):
                for y in (-depth/2, depth/2):
                    point = root.getRelativePoint(building, Vec3(x, y, 0))+origin
                    _corner_s, corner_d = curve.project(tuple(point))
                    assert 46.3 < corner_d < 125.7
                    assert corner_d < 84 or corner_d > 86
        assert not root.find('**/city-courtyard-path').isEmpty()
    finally:
        root.removeNode()


def test_full_segment_keeps_city_template_vertex_storage(kit):
    from environment.expressway_route import build_segment

    assets, _ = kit

    def vertex_storage(node):
        return {int(geom.getVertexData().this)
                for part in node.findAllMatches('**/+GeomNode') for geom in part.node().getGeoms()}

    templates = set().union(*(vertex_storage(model) for model in assets['city-models']))
    root = NodePath('whole-city-segment')
    try:
        build_segment(root, 19, 0, assets, lambda _node: None, HighwayCurve(0, hills=True))
        buildings = root.findAllMatches('**/=city-footprint')
        assert len(buildings) == 8
        for building in buildings:
            assert vertex_storage(building) <= templates
    finally:
        root.removeNode()


def test_city_static_batch_preserves_bounds_and_independent_lods(kit):
    from panda3d.core import GeomNode, SceneGraphAnalyzer

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/environment'))
    from city_static_candidate import batch_static_steps

    root = NodePath('city-local-batch')
    try:
        list(city_steps(root, 19, 0, HighwayCurve(0, hills=True), kit[0]))
        original_bounds = root.getTightBounds()
        lods = {int(node.node().this): (node.getMat(root), node.node().getNumSwitches())
                for node in root.findAllMatches('**/+LODNode')}
        before = SceneGraphAnalyzer()
        before.addNode(root.node())
        list(batch_static_steps(root, kit[0]['lamp'].getName()))
        after = SceneGraphAnalyzer()
        after.addNode(root.node())
        assert after.getNumTris() == before.getNumTris()
        assert after.getNumGeoms() < before.getNumGeoms()-40
        for low, high in zip(original_bounds, root.getTightBounds(), strict=True):
            assert tuple(low) == pytest.approx(tuple(high), abs=1e-4)
        assert {int(node.node().this): (node.getMat(root), node.node().getNumSwitches())
                for node in root.findAllMatches('**/+LODNode')} == lods
        batches = root.findAllMatches('**/city-static-surfaces*')
        assert len(batches) == 5
        assert all(batch.find('**/+LODNode').isEmpty() for batch in batches)
        assert len(root.findAllMatches('**/=city-garden-tree')) == 8
        assert len(root.findAllMatches('**/=city-greenbelt-tree')) == 6
        assert len(root.findAllMatches('**/=city-garden-ground-shrub')) == 16
        assert len(root.findAllMatches('**/=city-parked-car')) == 2
        assert all(isinstance(part.node(), GeomNode)
                   for batch in batches for part in batch.findAllMatches('**/+GeomNode'))
    finally:
        root.removeNode()


def test_far_windows_keep_openings_without_coplanar_wall(kit):
    from panda3d.core import (
        BitMask32,
        CollisionHandlerQueue,
        CollisionNode,
        CollisionSegment,
        CollisionTraverser,
        GeomVertexReader,
    )

    # 远窗不能靠毫米级偏移叠在整面墙上；长距离深度精度会使玻璃和墙交替出现。
    for model in kit[0]['city-models']:
        far = model.find('**/city-far')
        glass = far.find('**/city-glass').node().getGeom(0)
        reader = GeomVertexReader(glass.getVertexData(), 'vertex')
        points = [Vec3(reader.getData3f()) for _ in range(3)]
        center = sum(points, Vec3(0))/3
        normal = (points[1]-points[0]).cross(points[2]-points[0]).normalized()
        root = NodePath('far-window-query')
        try:
            wall = far.find('**/city-plaster').copyTo(root)
            wall.setCollideMask(BitMask32.bit(0))
            ray = CollisionNode('window-normal')
            ray.addSolid(CollisionSegment(center+normal*.5, center-normal*.5))
            ray.setFromCollideMask(BitMask32.bit(0))
            ray.setIntoCollideMask(BitMask32.allOff())
            collider = root.attachNewNode(ray)
            result = CollisionHandlerQueue()
            query = CollisionTraverser()
            query.addCollider(collider, result)
            query.traverse(root)
            assert result.getNumEntries() == 0, model.getName()
        finally:
            root.removeNode()


def test_city_entrance_is_not_blocked_by_stone_plinth(kit):
    from panda3d.core import (
        BitMask32,
        CollisionHandlerQueue,
        CollisionNode,
        CollisionSegment,
        CollisionTraverser,
    )

    for model in kit[0]['city-models']:
        width, _depth = map(float, model.getTag('city-footprint').split())
        for name in ('city-near', 'city-far'):
            level = model.find('**/'+name)
            root = NodePath('entrance-check')
            try:
                for part in level.findAllMatches('**/+GeomNode'):
                    if part.getName() != 'city-glass':
                        part.copyTo(root).setCollideMask(BitMask32.bit(0))
                ray = CollisionNode('door-clearance')
                # 检查两扇门片，避开本来就应存在的中央门框。
                for side in (-1, 1):
                    ray.addSolid(CollisionSegment(Vec3(-width/2-.4, side*.45, .35),
                                                  Vec3(-width/2+.4, side*.45, .35)))
                ray.setFromCollideMask(BitMask32.bit(0))
                ray.setIntoCollideMask(BitMask32.allOff())
                collider = root.attachNewNode(ray)
                result = CollisionHandlerQueue()
                query = CollisionTraverser()
                query.addCollider(collider, result)
                query.traverse(root)
                assert result.getNumEntries() == 0, (model.getName(), name)
            finally:
                root.removeNode()


def test_city_lods_keep_common_surface_colors(kit):
    from panda3d.core import GeomVertexReader

    def faces(level):
        result = {}
        for part in level.findAllMatches('**/+GeomNode'):
            for geom in part.node().getGeoms():
                data = geom.getVertexData()
                vertex = GeomVertexReader(data, 'vertex')
                color = GeomVertexReader(data, 'color')
                positions = [tuple(vertex.getData3f()) for _ in range(data.getNumRows())]
                colors = [tuple(color.getData4f()) for _ in range(data.getNumRows())]
                for primitive in geom.getPrimitives():
                    for number in range(primitive.getNumPrimitives()):
                        indices = [primitive.getVertex(i) for i in range(
                            primitive.getPrimitiveStart(number), primitive.getPrimitiveEnd(number))]
                        key = tuple(sorted(positions[i] for i in indices))
                        result[key] = tuple(sorted((positions[i], colors[i]) for i in indices))
        return result

    for model in kit[0]['city-models']:
        near, far = (faces(model.find('**/'+name)) for name in ('city-near', 'city-far'))
        common = near.keys() & far.keys()
        assert common
        changed = [face for face in common if near[face] != far[face]]
        assert not changed, (model.getName(), len(changed))


def test_city_garden_tree_roots_follow_their_own_ground(kit):
    curve = HighwayCurve(0, hills=True)
    origin = Vec3(*anchor(curve, 19))
    root = NodePath('sloping-gardens')
    try:
        list(city_steps(root, 19, 0, curve, kit[0]))
        shrubs = root.findAllMatches('**/=city-garden-ground-shrub')
        assert len(shrubs) == 16
        trees = [tree for tag in ('city-garden-tree', 'city-tree', 'city-courtyard-tree',
                                 'city-greenbelt-tree')
                 for tree in root.findAllMatches('**/='+tag)]
        assert len(trees) == 24
        for tree in (*trees, *shrubs):
            position = tree.getPos(root)+origin
            low, _high = tree.getTightBounds(tree)
            bottom = position.z+low.z*tree.getSz(root)
            along, across = curve.project(tuple(position))
            ground = terrain_point(curve, across, along, 0).z
            assert bottom == pytest.approx(ground-.04, abs=.005)
        # 根位须在地方车道、公共步道和楼基之外，树群不能靠穿墙来连接。
        for tree in trees:
            position = tree.getPos(root)
            _along, across = curve.project(tuple(position+origin))
            assert abs(across-41) > 3.5
            assert abs(across-131) > 3.5
            assert not 84 <= across <= 86
            for building in root.findAllMatches('**/=city-footprint'):
                point = building.getRelativePoint(root, position)
                width, depth = map(float, building.getTag('city-footprint').split())
                assert max(abs(point.x)-width/2, abs(point.y)-depth/2) > .35
    finally:
        root.removeNode()


def test_city_masonry_keeps_linear_data_and_shared_material_batches(kit):
    from panda3d.core import GeomNode, Texture

    root = NodePath('masonry-resources')
    try:
        list(city_steps(root, 19, 0, HighwayCurve(0, hills=True), kit[0]))
        walls = root.findAllMatches('**/city-masonry')
        assert len(walls) == 16
        diffuse = walls[0].getTexture()
        normal = walls[0].getShaderInput('city_normal').getTexture()
        roughness = walls[0].getShaderInput('city_roughness').getTexture()
        assert diffuse.getFormat() == Texture.FSrgb
        assert normal.getFormat() != Texture.FSrgb
        assert roughness.getFormat() != Texture.FSrgb
        assert normal.getName().endswith('_nor_gl_1k')
        preparation = kit[0]['city-models'][0].getParent().find('**/city-masonry-prepare')
        assert preparation.isHidden()
        prepared_maps = set(preparation.findAllTextures())
        plaster = kit[0]['city-models'][0].find('**/city-plaster')
        assert {normal, roughness, plaster.getShaderInput('city_normal').getTexture(),
                plaster.getShaderInput('city_roughness').getTexture()} <= prepared_maps
        for wall in walls:
            assert wall.getTexture() == diffuse
            assert wall.getShaderInput('city_normal').getTexture() == normal
            assert wall.getShaderInput('city_roughness').getTexture() == roughness
            assert wall.getShaderInput('city_tex_scale').getVector().x*1.5 == pytest.approx(1.)
        for garden in root.findAllMatches('**/city-garden'):
            groups = [part for part in garden.getChildren() if isinstance(part.node(), GeomNode)]
            parked = not garden.find('**/=city-parked-car').isEmpty()
            assert len(groups) == 3+parked
        for foundation in root.findAllMatches('**/city-foundation'):
            assert foundation.findAllMatches('**/+GeomNode').getNumPaths() == 1
    finally:
        root.removeNode()


@pytest.mark.parametrize('index', (19, 28))
def test_city_entrance_paths_end_at_the_actual_front_facade(kit, index):
    from panda3d.core import GeomVertexReader

    curve = HighwayCurve(0, hills=True)
    origin = Vec3(*anchor(curve, index))
    root = NodePath('entrance-paving')
    try:
        list(city_steps(root, index, 0, curve, kit[0]))
        paths = []
        for path in root.findAllMatches('**/city-entrance-path'):
            data = path.node().getGeom(0).getVertexData()
            reader = GeomVertexReader(data, 'vertex')
            points = [Vec3(reader.getData3f())+origin for _ in range(data.getNumRows())]
            station, _across = curve.project(tuple(sum(points, Vec3(0))/len(points)))
            paths.append((station, [curve.project(tuple(point))[1] for point in points]))
        for building in root.findAllMatches('**/=city-footprint'):
            width, _depth = map(float, building.getTag('city-footprint').split())
            center = building.getPos(root)+origin
            station, _across = curve.project(tuple(center))
            door = root.getRelativePoint(building, Vec3(-width/2, 0, 0))+origin
            _door_s, door_d = curve.project(tuple(door))
            path_station, edges = min(paths, key=lambda path: abs(path[0]-station))
            assert abs(path_station-station) < .05
            end = max(edges) if int(building.getTag('city-lot')) < 4 else min(edges)
            assert end == pytest.approx(door_d, abs=.03)
    finally:
        root.removeNode()


def test_city_street_bends_around_existing_bridge_abutment(kit):
    from panda3d.core import GeomVertexReader

    curve = HighwayCurve(0, hills=True)
    origin = Vec3(*anchor(curve, 28))
    root = NodePath('bridge-city')
    try:
        list(city_steps(root, 28, 0, curve, kit[0]))
        edges = {5620: [], 5700: []}
        for street in root.findAllMatches('**/city-local-street'):
            reader = GeomVertexReader(street.node().getGeom(0).getVertexData(), 'vertex')
            while not reader.isAtEnd():
                station, across = curve.project(tuple(Vec3(reader.getData3f())+origin))
                for location, values in edges.items():
                    if abs(station-location) < .02:
                        values.append(across)
        # 原桥台外沿约51米；普通区仍靠近，但桥下街道不能切进原桥台。
        assert min(edges[5620]) > 59
        assert min(edges[5700]) == pytest.approx(37.5, abs=.02)
    finally:
        root.removeNode()


def test_city_inner_street_is_supported_by_displayed_terrain_rows(kit):
    from panda3d.core import GeomVertexReader

    from environment.expressway_route import landscape_steps

    curve = HighwayCurve(0, hills=True)
    origin = Vec3(*anchor(curve, 19))
    root = NodePath('displayed-city-floor')
    steps = landscape_steps(root, 19, 0, curve, kit[0], lambda _s: root)
    meshes = 0
    try:
        for phase in steps:
            if phase == 'terrain-mesh':
                meshes += 1
                if meshes == 2:
                    break
        checked = 0
        for node in root.findAllMatches('**/route-landscape'):
            data = node.node().getGeom(0).getVertexData()
            points, uv = GeomVertexReader(data, 'vertex'), GeomVertexReader(data, 'texcoord')
            while not points.isAtEnd():
                point, texture = points.getData3f(), uv.getData2f()
                if abs(texture.x-37.5) < 1e-4:
                    station = 3800+(texture.y-200)
                    assert point.z+origin.z == pytest.approx(curve.sample(station).z-1.5, abs=1e-4)
                    checked += 1
        # 直接检查实际显示网格的41行，避免街道按公式落地却被粗地形三角面埋住。
        assert checked == 41
    finally:
        steps.close()
        root.removeNode()
