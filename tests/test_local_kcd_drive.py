"""本机试用的真实资源格式、坡面贴合和退出还原。"""

import math
import subprocess
import sys
from itertools import pairwise
from pathlib import Path
from zipfile import ZipFile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/environment'))

from kcd_local_assets import (
    GRASS,
    INSTALL,
    TREE,
    decode_texture,
    load_ferns,
    load_local,
    load_shrubs,
    read_mesh,
)
from local_kcd_drive import LocalVegetation, floor_point

from career_courses import CareerCourse
from environment import expressway, expressway_route
from highway_curve import HighwayCurve
from scene import Scene


@pytest.mark.parametrize('index', (0, 19))
def test_city_grass_cells_stop_before_the_local_street(tmp_path, monkeypatch, index):
    import local_kcd_drive
    from panda3d.core import NodePath, Vec3

    root = NodePath('street-grass-controls')
    profile = LocalVegetation(tmp_path)
    grass_phase = False
    positive_floors = []

    def floor(curve, across, station, seed):
        if grass_phase:
            if across > 0:
                positive_floors.append(across)
            return Vec3(across, station, 0)
        return None

    monkeypatch.setattr(local_kcd_drive, 'floor_point', floor)
    monkeypatch.setattr(local_kcd_drive, 'valid_verge', lambda *args: True)
    kit = {'local-kcd-grass': NodePath('near-grass'), 'local-kcd-grass-mid': NodePath('mid-grass')}
    try:
        for phase in profile.vegetation(root, index, 0, None, kit, lambda _s: root):
            if phase == 'local-grass-site-checks':
                grass_phase = True
        # 核对实际草格四角，而非只查中心；原35米内植被和非城市远侧草地仍存在。
        assert {11, 15, 19, 23, 27, 31} <= set(positive_floors)
        if index == 19:
            assert 31 < max(positive_floors) < 41-5.3
        else:
            assert max(positive_floors) > 100
    finally:
        root.removeNode()


def test_tiled_terrain_does_not_consume_scan_mesh_uv_atlas():
    from local_coastal_landscape import landscape_materials
    from panda3d.core import Shader, Texture

    from environment.expressway_materials import terrain_shader

    kit = {'mountain-shader': terrain_shader('route-mountain.frag')}
    landscape_materials(kit)
    rock = kit['rock']
    # 两种地形都重复读取这个槽；只有扫描模型本身可用岛状UV图集。
    assert Path(rock.getFullpath().toOsSpecific()).name == 'strata-albedo.png'
    assert rock.getFormat() == Texture.FSrgb
    assert rock.getWrapU() == rock.getWrapV() == Texture.WMRepeat
    assert 'texture(expressway_rock,p.yz)' in kit['mountain-shader'].getText(Shader.STFragment)


@pytest.mark.parametrize('index', (0, 8))
def test_rejected_vegetation_sites_still_return_frame_budget(tmp_path, monkeypatch, index):
    import local_kcd_drive
    from panda3d.core import NodePath

    root = NodePath('rejected-sites')
    profile = LocalVegetation(tmp_path)
    checks = 0

    def unavailable_floor(*args):
        nonlocal checks
        checks += 1

    monkeypatch.setattr(local_kcd_drive, 'floor_point', unavailable_floor)
    phases = []
    try:
        for phase in profile.vegetation(root, index, 0, CareerCourse('ridge-club'), {}, lambda _s: root):
            assert checks <= 128
            checks = 0
            phases.append(phase)
        assert checks <= 128
        assert phases.count('local-grass-site-checks') == 150
        assert 'local-grove-site-checks' in phases
        assert root.getNumChildren() == 0
    finally:
        root.removeNode()


@pytest.mark.parametrize('course_id', ['coast-club', 'ridge-club', 'coast-final'])
def test_incremental_ground_normals_equal_original_complete_terrain(course_id):
    from local_kcd_drive import course_normal_steps
    from panda3d.core import Vec3

    from career_terrain import terrain

    reference = {}
    for vertices, faces in terrain(course_id).values():
        for a, b, c in faces:
            normal = (Vec3(*vertices[b])-Vec3(*vertices[a])).cross(Vec3(*vertices[c])-Vec3(*vertices[a]))
            for number in (a, b, c):
                x, y, _z = vertices[number]
                key = round(x/8), round(y/8)
                reference[key] = reference.get(key, Vec3(0)) + normal
    reference = {key: tuple(normal.normalized()) for key, normal in reference.items()}
    work = course_normal_steps(course_id)
    yields = []
    while True:
        try:
            yields.append(next(work))
        except StopIteration as completed:
            assert completed.value == reference
            break
    assert yields.count('local-kcd-normal-accumulation') > 10
    assert yields.count('local-kcd-normal-normalization') > 10


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要本机原始网格与带作者mip的图集')
def test_native_asset_cache_keeps_mesh_and_authored_texture_mips(tmp_path, monkeypatch):
    import hashlib
    import json

    import kcd_local_assets as assets

    with ZipFile(INSTALL / 'IPL_Objects-part5.pak') as package:
        raw = package.read(TREE + 'quercus_a_lod2.cgfm')
        original = assets.read_mesh(raw)
        cold = assets.cached_mesh(raw, tmp_path)
        hit = assets.cached_mesh(raw, tmp_path)
        assert json.dumps(original) == json.dumps(cold) == json.dumps(hit)
        # 材质选择必须进入键，不能复用包含另一组面的缓存。
        selected = assets.cached_mesh(raw, tmp_path, visible_materials={1})
        assert json.dumps(selected) == json.dumps(assets.read_mesh(raw, visible_materials={1}))

        def unexpected_parse(*args, **kwargs):
            pytest.fail('有效缓存仍重新解析了原始网格')

        monkeypatch.setattr(assets, 'read_mesh', unexpected_parse)
        assert assets.cached_mesh(raw, tmp_path) == hit
        path = tmp_path / 'oak.png'
        cold_texture = assets.decode_texture(package, TREE + 'quercus_atlas_diff.dds', '.5', (2048, 1024), path)
        hit_texture = assets.decode_texture(package, TREE + 'quercus_atlas_diff.dds', '.5', (2048, 1024), path)

        def signature(texture):
            return (texture.getFormat(), texture.getComponentType(), texture.getMinfilter(),
                    texture.getAnisotropicDegree(), texture.getXSize(), texture.getYSize(),
                    [hashlib.sha256(bytes(texture.getRamMipmapImage(i))).hexdigest()
                     for i in range(texture.getNumRamMipmapImages())])

        assert signature(cold_texture) == signature(hit_texture)
        assert hit_texture.getNumRamMipmapImages() == 12
        key = assets.texture_cache_key(package, TREE + 'quercus_atlas_diff.dds', ['changed-settings'])
        assert assets.read_texture_cache(path, key, ['color']) is None


@pytest.mark.parametrize('course', ['coast-club', 'ridge-club', 'coast-final'])
def test_gpu_heightfield_preserves_actual_world_elevations(tmp_path, course):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'tools/environment/check_heightfield_gpu.py'),
                    '--course', course, '--output', str(tmp_path / 'gpu-height.json')],
                   cwd=root, check=True, capture_output=True, text=True, timeout=30)


def test_meadow_growth_gpu_keeps_world_rebasing_and_actual_patch_range(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'tools/environment/check_meadow_growth_gpu.py'),
                    '--output', str(tmp_path / 'growth.json')], cwd=root, check=True,
                   capture_output=True, text=True, timeout=30)


def test_city_lawn_gpu_keeps_region_phase_and_protected_band(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root/'tools/environment/check_meadow_growth_gpu.py'),
                    '--city-lawn', '--output', str(tmp_path/'city-lawn.json')],
                   cwd=root, check=True, capture_output=True, text=True, timeout=30)


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要实际原草模板的图元与株根元数据')
def test_actual_grass_triangles_share_the_initial_whole_plant_predicate(tmp_path):
    from local_kcd_drive import grass_shader, grass_template
    from panda3d.core import GeomVertexReader

    from environment.expressway_materials import foliage_shader

    _trees, grasses, _ground = load_local(tmp_path, foliage_shader(), tree_letters='a')
    for grid in (11, 6):
        node = grass_template(grasses, grass_shader(foliage_shader()), grid=grid)
        geom = node.node().getGeom(0)
        reader = GeomVertexReader(geom.getVertexData(), 'color')
        colors = [tuple(reader.getData4f()) for _ in range(geom.getVertexData().getNumRows())]
        assert len(set(colors)) == grid*grid
        checked = 0
        for primitive in geom.getPrimitives():
            indices = primitive.decompose().getVertexList()
            for start in range(0, len(indices), 3):
                a, b, c = indices[start:start+3]
                assert colors[a] == colors[b] == colors[c]
                checked += 1
        assert checked > 1000


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要完整本机草地的真实GPU核对')
def test_grass_vertex_early_return_preserves_actual_driving_view(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'tools/environment/check_grass_vertex_cull.py'),
                    '--output', str(tmp_path / 'grass-vertices')], cwd=root, check=True,
                   capture_output=True, text=True, timeout=120)


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要原草与实际4x MSAA核对距离过渡')
def test_grass_distance_fade_keeps_actual_near_pixels_and_fixed_height(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root/'tools/environment/check_grass_distance_fade.py'),
                    '--output', str(tmp_path/'grass-distance')], cwd=root, check=True,
                   capture_output=True, text=True, timeout=120)


@pytest.mark.skipif(not INSTALL.is_dir(), reason='只在用户指定的本机安装存在时核对原始资源')
def test_actual_tree_lod_changes_are_distributed_across_rendered_frames(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'tools/environment/check_tree_lod_transition.py'),
                    '--output', str(tmp_path / 'tree-lod')], cwd=root, check=True,
                   capture_output=True, text=True, timeout=90)


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要本机原树核对GPU图像')
def test_root_parameter_transport_keeps_actual_rendered_shape_and_uv(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'tools/environment/check_tree_root_transport.py'),
                    '--output', str(tmp_path / 'tree-root')], cwd=root, check=True,
                   capture_output=True, text=True, timeout=90)


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要本机原树/atlas核对天空遮蔽和阴影深度')
def test_canopy_sky_mask_preserves_actual_opacity_and_shadow_depth(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'tools/environment/check_canopy_visibility_gpu.py'),
                    '--output', str(tmp_path / 'canopy')], cwd=root, check=True,
                   capture_output=True, text=True, timeout=90)


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要本机完整草树地表核对真实随车GPU帧')
def test_scoped_woodland_preserves_consumed_inputs_and_reduces_tree_states(tmp_path):
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'tools/environment/check_woodland_state.py'),
                    '--output', str(tmp_path / 'woodland-state')], cwd=root, check=True,
                   capture_output=True, text=True, timeout=120)


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要本机原树核对相邻实际树冠的林地覆盖')
def test_neighboring_woodland_segments_share_coverage_and_release_removed_crowns(tmp_path):
    import numpy as np
    from panda3d.core import NodePath

    from environment.expressway_materials import foliage_shader

    trees, _, _ = load_local(tmp_path, foliage_shader(), distance_lods=True, tree_letters='a')
    profile = LocalVegetation(tmp_path)
    first, second = NodePath('first-segment'), NodePath('second-segment')
    a, b = trees[0].copyTo(first), trees[0].copyTo(second)
    a.setPos(-20, 196, 0)
    b.setPos(-20, 4, 0)

    def samples(path):
        texture, bounds = path.getPythonTag('woodland-coverage')
        pixels = np.frombuffer(texture.getRamImage(), dtype=np.uint8).reshape(texture.getYSize(), texture.getXSize())
        return {(round(bounds[0] + (col + .5) * 2), round(bounds[1] + (row + .5) * 2)): int(value)
                for row, line in enumerate(pixels) for col, value in enumerate(line)}

    list(profile.surface_weights(first, 0, None))
    alone = samples(first)
    list(profile.surface_weights(second, 1, None))
    left, right = samples(first), samples(second)
    shared = left.keys() & right.keys()
    assert len(shared) > 20
    assert max(abs(left[key] - right[key]) for key in shared) <= 1
    assert max(left[key] - alone[key] for key in left) > 10
    first.removeNode()
    list(profile.surface_weights(second, 1, None))
    remaining = samples(second)
    assert set(profile.forest_canopies) == {1}
    assert max(right[key] - remaining[key] for key in right) > 10
    second.removeNode()


def test_local_woodland_raster_matches_dense_reference():
    import numpy as np
    from local_kcd_drive import woodland_texture

    centers = np.array([(x, y) for x in (-35., -21., -8., 25.) for y in (186., 200., 214.)], dtype=np.float32)
    radii = np.array([6., 8., 7.] * 4, dtype=np.float32)
    work = woodland_texture(centers, radii, (-60., 160., 48., 240.))
    while True:
        try:
            next(work)
        except StopIteration as done:
            texture, coordinates = done.value
            break
    actual = np.frombuffer(texture.getRamImage(), dtype=np.uint8).reshape(texture.getYSize(), texture.getXSize())
    x = coordinates[0] + (np.arange(texture.getXSize()) + .5) * 2
    y = coordinates[1] + (np.arange(texture.getYSize()) + .5) * 2
    distance = ((x[None, :, None] - centers[None, None, :, 0]) ** 2
                + (y[:, None, None] - centers[None, None, :, 1]) ** 2)
    influence = np.exp(-distance / (radii[None, None, :] * 1.2) ** 2).sum(axis=2) * .8
    weight = np.clip((influence - .3) / 1.1, 0, 1)
    expected = np.rint(weight * weight * (3 - 2 * weight) * 255).astype(np.uint8)
    assert np.max(np.abs(actual.astype(int) - expected.astype(int))) <= 1


@pytest.mark.skipif(not INSTALL.is_dir(), reason='只在用户指定的本机安装存在时核对原始资源')
def test_actual_tree_lods_keep_uvs_and_valid_geometry():
    with ZipFile(INSTALL / 'IPL_Objects-part5.pak') as package:
        for letter in 'abcde':
            counts = []
            for suffix in ('', '_lod1', '_lod2'):
                mesh = read_mesh(package.read(TREE + 'quercus_' + letter + suffix + '.cgfm'))
                counts.append(len(mesh['faces']))
                assert min(i for face in mesh['faces'] for i in face) >= 0
                assert max(i for face in mesh['faces'] for i in face) < len(mesh['points'])
                assert max(u for u, v in mesh['uv']) - min(u for u, v in mesh['uv']) > .5
                assert all(abs(sum(v * v for v in normal) - 1) < 1e-5 for normal in mesh['normals'])
            assert counts[0] > counts[1] > counts[2] > 0


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要本机原蕨的CGF材质引用和原始距离档')
def test_original_ferns_share_referenced_grass_atlas_and_keep_source_geometry(tmp_path):
    from panda3d.core import GeomVertexReader

    from environment.expressway_materials import foliage_shader

    _trees, grasses, _ground = load_local(tmp_path, foliage_shader(), tree_letters='a')
    ferns = load_ferns(tmp_path, foliage_shader(), grasses)
    base = 'Objects/natural/vegetation/forest_undergrowth/'
    with ZipFile(INSTALL / 'IPL_Objects-part4.pak') as package:
        for variant, fern in zip(('a', 'b', 'large_a'), ferns, strict=True):
            metadata = package.read(base+'ferns_'+variant+'.cgf')
            assert (GRASS+'grass').encode() in metadata
            counts = []
            for level in range(3 if variant == 'large_a' else 2):
                name = base+'ferns_'+variant+('' if level == 0 else '_lod'+str(level))+'.cgfm'
                source = read_mesh(package.read(name), visible_materials={0})
                node = fern.getChild(level)
                geom = node.node().getGeom(0)
                counts.append(geom.getPrimitive(0).getNumPrimitives())
                assert counts[-1] == len(source['faces'])
                position = GeomVertexReader(geom.getVertexData(), 'vertex')
                uv = GeomVertexReader(geom.getVertexData(), 'texcoord')
                for point, texcoord in zip(source['points'], source['uv'], strict=True):
                    assert tuple(position.getData3f()) == point
                    assert tuple(uv.getData2f()) == texcoord
                assert node.findAllTextures()[0] == grasses[0][1]
            assert all(a > b > 0 for a, b in pairwise(counts))


def test_grove_plants_belong_to_one_absolute_segment_and_are_reproducible():
    from local_kcd_drive import grove_positions

    first = list(grove_positions(0, 17))
    second = list(grove_positions(1, 17))
    # 先请求邻段不能消耗共享随机状态，也不能让跨界地块重复种植。
    assert first == list(grove_positions(0, 17))
    assert all(0 <= row[1] < 200 for row in first)
    assert all(200 <= row[1] < 400 for row in second)
    sites = [(row[0], row[1]) for row in first+second]
    assert len(sites) == len(set(sites))
    assert first != list(grove_positions(0, 23))


def test_profile_restores_actual_scene_and_streaming_entrypoints(tmp_path):
    from environment import expressway_mountains

    original = (expressway.load_kit, expressway_route.landscape_steps, expressway_route.vegetation_steps,
                Scene.setup_endless, expressway_route.segment_steps, Scene.__init__,
                expressway_mountains.mountain_point)
    profile = LocalVegetation(tmp_path)
    profile.install()
    try:
        assert Scene.setup_endless is not original[3]
        assert expressway_route.vegetation_steps == profile.vegetation
    finally:
        profile.restore()
    assert (expressway.load_kit, expressway_route.landscape_steps,
            expressway_route.vegetation_steps, Scene.setup_endless, expressway_route.segment_steps,
            Scene.__init__, expressway_mountains.mountain_point) == original


def test_local_entry_does_not_redirect_lab_and_player_storage(tmp_path, monkeypatch):
    import bake_kcd_canopy_visibility
    import local_kcd_drive

    import main

    environment = tmp_path / 'environment'
    environment.mkdir()
    (environment / 'original-environment.json').write_text('{}', encoding='utf-8')
    arguments = ['local_kcd_drive.py', '--output', str(tmp_path / 'asset-cache'),
                 '--environment', str(environment), '--seed', '17']
    monkeypatch.setattr(sys, 'argv', arguments)
    monkeypatch.setattr(LocalVegetation, 'install', lambda _self: None)
    monkeypatch.setattr(LocalVegetation, 'restore', lambda _self: None)
    monkeypatch.setattr(bake_kcd_canopy_visibility, 'prepare', lambda _folder: None)
    received = []
    monkeypatch.setattr(main, 'main', lambda: received.extend(sys.argv) or 0)
    assert local_kcd_drive.main() == 0
    assert '--output' not in received
    assert received[-2:] == ['--seed', '17']
    assert sys.argv is arguments


@pytest.mark.parametrize('course_id', ['coast-club', 'ridge-club', 'coast-final'])
def test_grass_floor_matches_actual_cartesian_course_triangles(course_id, monkeypatch):
    monkeypatch.setenv('COASTALDRIVE_COAST_CANDIDATE', '1')
    from career_terrain import terrain

    course = CareerCourse(course_id)
    triangles = [tuple(vertices[i] for i in face) for vertices, faces in terrain(course_id).values()
                 for face in faces]
    for distance in (100, course.length * .4, course.length * .7):
        for lateral in (-35, -23, -11, 11, 23, 35):
            p = floor_point(course, lateral, distance, 0)
            # 独立从已显示的三角形平面求交，包含回头弯笛卡尔网格，不能用道路解析高度代替。
            candidates = [t for t in triangles if min(v[0] for v in t) <= p.x <= max(v[0] for v in t)
                          and min(v[1] for v in t) <= p.y <= max(v[1] for v in t)]
            heights = []
            for a, b, c in candidates:
                area = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
                u = ((p.x - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p.y - a[1])) / area
                v = ((b[0] - a[0]) * (p.y - a[1]) - (p.x - a[0]) * (b[1] - a[1])) / area
                if u >= -1e-6 and v >= -1e-6 and u + v <= 1 + 1e-6:
                    heights.append(a[2] * (1 - u - v) + b[2] * u + c[2] * v)
            assert heights and p.z == pytest.approx(heights[0], abs=1e-4)


def test_hilly_highway_floor_stays_on_source_mesh_at_segment_boundary():
    curve = HighwayCurve(23, hills=True)
    for distance in (199.999, 200, 200.001, 399.999, 400):
        a = floor_point(curve, 15, distance, 23)
        b = floor_point(curve, 15, distance + .001, 23)
        assert math.dist(a, b) < .005


def test_infinite_highway_has_no_planting_surface_outside_actual_strip():
    curve = HighwayCurve(0, hills=True)
    for lateral in (-155., -120.01, -8., 0., 8., 120.01, 155.):
        assert floor_point(curve, lateral, 270., 0) is None
    for lateral in (-120., -8.5, 8.5, 120.):
        assert floor_point(curve, lateral, 270., 0) is not None


def test_finite_course_preload_outside_authored_terrain_has_no_planting_surface():
    course = CareerCourse('ridge-club')
    assert floor_point(course, -28, -400, 0) is None
    assert floor_point(course, 15, course.length + 400, 0) is None


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要用户指定的本机原件')
def test_original_tree_roots_stay_buried_below_authored_planting_origin(tmp_path):
    import xml.etree.ElementTree as ET

    from environment.expressway_materials import foliage_shader

    trees, _grasses, _ground = load_local(tmp_path, foliage_shader(), distance_lods=True)
    with ZipFile(INSTALL / 'IPL_Objects-part5.pak') as package:
        material = ET.fromstring(package.read(TREE + 'quercus_robur.mtl')).find('SubMaterials')[1]
        source_color = tuple(float(v) for v in material.find('PublicParams').attrib['TransmittanceColor'].split(','))
    for tree in trees:
        offsets = {part.getZ() for part in tree.getChildren()}
        assert len(offsets) == 1
        assert next(iter(offsets)) == pytest.approx(-.03)
        low, _high = tree.getTightBounds()
        # 原件最低点在z=0以下，必须留在土中；抬到包围盒底部会露出锥形根。
        assert low.z < -.5
        color = tree.getChild(0).getShaderInput('local_transmittance_color').getVector()
        assert tuple(color.xyz) == pytest.approx(source_color)


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要用户指定的本机原件')
def test_hawthorn_uses_visible_branch_material_and_linear_detail_channels(tmp_path):
    import xml.etree.ElementTree as ET

    from panda3d.core import Texture

    from environment.expressway_materials import foliage_shader

    base = 'Objects/natural/vegetation/bushes/crataegus/'
    with ZipFile(INSTALL / 'IPL_Objects-part4.pak') as package:
        materials = ET.fromstring(package.read(base + 'crataegus.mtl')).find('SubMaterials')
        assert materials[1].get('Shader') == 'Vegetation'
        assert materials[4].get('Name') == 'shadow_proxy'
        raw = package.read(base + 'crataegus_a.cgfm')
        assert len(read_mesh(raw, visible_materials={1})['faces']) < len(read_mesh(raw)['faces'])
    shrubs = load_shrubs(tmp_path, foliage_shader())
    assert len(shrubs) == 3
    for shrub in shrubs:
        part = shrub.find('**/+GeomNode')
        base = part.findAllTextures()[0]
        assert base.getFormat() == Texture.FSrgbAlpha
        normal = part.getShaderInput('local_normal').getTexture()
        assert normal.getXSize() == normal.getYSize() == 1024
        assert normal.getFormat() != Texture.FSrgb
        assert part.getShaderInput('local_gloss').getTexture().getNumComponents() == 1


def test_source_sun_shadow_coordinates_follow_actual_sun_direction():
    from kcd_local_environment import source_rail_shadow

    parameters = {'lighting': {'SunVector': '0.6,0,-0.8'}}
    assert source_rail_shadow(None, 0, -8.5, parameters) == pytest.approx((-8.5, .6))


def test_sun_lux_conversion_preserves_luminance():
    from kcd_local_environment import sun_color

    rgb = sun_color({'sun_color': '.238398,.205079,.194618', 'sun_lux': '79963.62'})
    assert sum(v * w for v, w in zip(rgb, (.2126, .7152, .0722), strict=False)) == pytest.approx(7.996362)
    assert rgb[0] / rgb[1] == pytest.approx(.238398 / .205079)


def test_shadow_camera_survives_real_ghost_initialization(monkeypatch):
    from types import SimpleNamespace

    from local_kcd_drive import cutout_shadows
    from panda3d.core import DirectionalLight, NodePath

    import ghost_visual

    root = NodePath('render')
    scene = SimpleNamespace(base=SimpleNamespace(render=root), render=root,
                            sun_path=root.attachNewNode(DirectionalLight('sun')))
    cutout_shadows(scene)
    monkeypatch.setattr(ghost_visual, 'load_vehicle',
                        lambda parent, definition, config: (parent.attachNewNode('body'), []))
    monkeypatch.setattr(ghost_visual, 'batch_driving_geometry', lambda body, wheels: None)
    ghost_visual.GhostVisual(root, None, None, scene.sun_path)
    mask = scene.sun_path.node().getCameraMask()
    assert not mask.isZero()
    assert (mask & ghost_visual.GHOST_MASK).isZero()


def test_original_environment_probe_is_used_for_ibl_and_not_as_visible_sky():
    from kcd_local_environment import load_environment
    from panda3d.core import LColor, NodePath, Texture

    from environment.expressway_materials import terrain_shader

    folder = Path(__file__).resolve().parents[1] / 'logs/local-kcd-original-environment'
    if not (folder / 'original-pasture-pbr.env').is_file():
        pytest.skip('需先从用户本机原件准备环境探针')
    original_sky = Texture('approved-sky')
    kit = {'sky': original_sky, 'route-terrain-shader': terrain_shader('route-terrain.frag')}
    parent = NodePath('local-material-check')
    load_environment(kit, parent, folder)
    assert kit['sky'] is original_sky
    environment = kit['daylight-environment']
    assert environment.cubemap.getXSize() == 128
    assert environment.filtered_env_map.getXSize() == 64
    color, peeker = LColor(), environment.cubemap.peek()
    peeker.lookup(color, 0, 0, 1)
    sky_brightness = sum(color.xyz)
    peeker.lookup(color, 0, 0, -1)
    assert sky_brightness > sum(color.xyz) * 10
    assert parent.getShaderInput('pasture_gloss').getTexture().getNumComponents() == 1
    assert parent.getShaderInput('pasture_normal').getTexture().getFormat() != Texture.FSrgb


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要本机原件的新增砂岩群')
def test_short_rock_banks_leave_actual_combination_bend_drivable(tmp_path):
    from kcd_local_assets import load_sandstone
    from local_coastal_landscape import load_rocks, rock_steps, sandstone_shader
    from panda3d.core import GeomVertexReader, NodePath, Vec3

    course = CareerCourse('coast-club')
    templates = NodePath('templates')
    rocks = load_rocks(templates)
    stones = load_sandstone(tmp_path, sandstone_shader())
    for stone in stones.values():
        stone.reparentTo(templates)
    placed = 0
    for index in (1, 2):
        root = NodePath('segment')
        origin = Vec3(*expressway_route.anchor(course, index))
        kit = {'local-rocks': rocks, 'local-kcd-rocks': stones}
        list(rock_steps(root, index, 0, course, kit, lambda _s, parent=root: parent, floor_point))
        nodes = [node for node in root.findAllMatches('**/+LODNode')
                 if node.getName().startswith(('local-coastal-bank-', 'kcd-sandstone-'))]
        for bank in nodes:
            placed += 1
            # 独立检查实际LOD0顶点，不能只复用摆放代码的包围盒判断。
            for path in bank.getChild(0).findAllMatches('**/+GeomNode'):
                for geom in path.node().getGeoms():
                    points = GeomVertexReader(geom.getVertexData(), 'vertex')
                    while not points.isAtEnd():
                        world = root.getRelativePoint(path, points.getData3f()) + origin
                        _distance, lateral = course.project(tuple(world))
                        assert abs(lateral) > 9, world
        root.removeNode()
    assert placed > 0
    templates.removeNode()


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要原始草图集作独立覆盖率对照')
def test_grass_mips_match_actual_authored_lower_resolution_sources(tmp_path):
    import json

    with ZipFile(INSTALL / 'IPL_Objects-part4.pak') as package:
        name = GRASS + 'plants_grass_merged_diff.dds'
        large = decode_texture(package, name, '.6', (2048, 2048), tmp_path / 'grass.png', alpha_cutoff=.15)
        lower = decode_texture(package, name, '.5', (1024, 1024), tmp_path / 'lower.png', alpha_cutoff=.15)
        # 父级的mip1应与直接读原件下一档完全相同，含RGB、alpha和Panda上下方向。
        assert bytes(large.getRamMipmapImage(1)) == bytes(lower.getRamImage())
        assert bytes(large.getRamMipmapImage(2)) == bytes(lower.getRamMipmapImage(1))
        records = json.loads((tmp_path / 'grass-mip-coverage.json').read_text())
        assert records[0]['alpha_cutoff'] == .15
        assert records[1]['source'] == name + '.5'
        assert any('@148' in row['source'] for row in records)


def test_grass_height_texture_preserves_actual_course_vertices_and_world_orientation(monkeypatch):
    monkeypatch.setenv('COASTALDRIVE_COAST_CANDIDATE', '1')
    import numpy as np
    from local_kcd_drive import grass_heightfield
    from panda3d.core import Texture

    from environment.career_coast import _data

    texture, origin, mode = grass_heightfield('coast-club')
    assert mode == 1.
    assert texture.getComponentType() == Texture.TFloat
    pixels = np.frombuffer(texture.getRamImage(), dtype=np.float32).reshape(texture.getYSize(), texture.getXSize())
    # 对照最终三角面烘焙的2米场；近路与原物理表面的关系另由真实面求交检查。
    data = _data('coast-club')
    assert origin == tuple(data['grid_origin'])
    np.testing.assert_array_equal(pixels, np.nan_to_num(data['heights'], nan=0.))
    _unused, _origin, mode = grass_heightfield(None)
    assert mode == 0.


@pytest.mark.skipif(not INSTALL.is_dir(), reason='需要本机原树与砂岩原件核对实际摆放外廓')
def test_grove_roots_keep_clear_of_actual_rock_extents(tmp_path):
    from kcd_local_assets import load_sandstone, load_young_oaks
    from local_coastal_landscape import load_rocks, rock_steps, sandstone_shader
    from local_kcd_drive import tree_shader
    from panda3d.core import NodePath

    from environment.expressway_materials import foliage_shader

    templates = NodePath('source-templates')
    shader = tree_shader(foliage_shader())
    trees, grasses, _ground = load_local(tmp_path, shader, distance_lods=True, tree_letters='abcde')
    shrubs, young = load_shrubs(tmp_path, shader), load_young_oaks(tmp_path, shader, trees[0].getChild(0))
    stones = load_sandstone(tmp_path, sandstone_shader())
    kit = {'local-kcd-trees': trees, 'local-kcd-shrubs': shrubs, 'local-kcd-young-oaks': young,
           'local-kcd-ferns': load_ferns(tmp_path, shader, grasses),
           'local-kcd-rocks': stones, 'local-rocks': load_rocks(templates),
           'local-kcd-grass': NodePath('grass-fixture'), 'local-kcd-grass-mid': NodePath('grass-mid-fixture')}
    course = CareerCourse('coast-club')
    profile = LocalVegetation(tmp_path)
    counted = 0
    for index in (0, 1):
        root = NodePath('grove-segment')
        parent = lambda _s, root=root: root
        list(rock_steps(root, index, 0, course, kit, parent, floor_point))
        list(profile.vegetation(root, index, 0, course, kit, parent))
        bounds = [node.getTightBounds(root) for node in root.findAllMatches('**/+LODNode')
                  if node.getName().startswith(('local-coastal-bank-', 'kcd-sandstone-'))]
        for plant in root.findAllMatches('**/+LODNode'):
            if not plant.getName().startswith(('kcd-oak-', 'kcd-young-oak-', 'kcd-hawthorn-')):
                continue
            point = plant.getPos(root)
            gap = 1.5 if plant.getName().startswith('kcd-oak-') else .7
            for low, high in bounds:
                assert not (low.x - gap <= point.x <= high.x + gap and low.y - gap <= point.y <= high.y + gap)
            counted += 1
        root.removeNode()
    assert counted > 100
    templates.removeNode()
