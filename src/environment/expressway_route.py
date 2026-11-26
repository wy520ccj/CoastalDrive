"""全程高速表现；消费现有道路采样与分段，不管理物理或streaming。"""

import math
from functools import lru_cache
from weakref import WeakKeyDictionary

import numpy as np
from panda3d.core import GeomVertexReader, GeomVertexWriter, LODNode, Vec3, Vec4

import curve_mesh
from career_courses import CareerCourse
from environment.career_coast import _enabled as coast_candidate
from environment.expressway import WHITE, smooth
from environment.expressway_signs import SIGN_MODELS, kilometer_face
from environment.expressway_vegetation import (
    TERRAIN_COLUMNS,
    understory,
    vegetation_steps,
)
from highway_curve import HighwayCurve
from highway_segments import SEGMENT_LENGTH, segment, surface_meshes

_TERRAIN_XYZ_BY_CURVE = WeakKeyDictionary()


def anchor(curve, index):
    return curve_mesh.anchor(curve, index) if curve else (0, index * SEGMENT_LENGTH, 0)


def sample(curve, s, lateral=0):
    if curve:
        p = curve.sample(s, lateral)
        return Vec3(p.x, p.y, p.z)
    return Vec3(lateral, s, 0)


def district(s, seed):
    """工程区间长短交错，设施不用随机数决定是否出现。"""
    cell = math.floor((s + seed % 5 * 160) / 1600)
    return (cell % 5, (s + seed % 5 * 160) % 1600)


def city_weight(s, seed):
    """城市缓台两端渐接原海岸，不在工程区边界产生矩形孤岛。"""
    phase = (s + seed % 5 * 160) % 8000
    return smooth(3200, 3440, phase) * (1-smooth(6160, 6400, phase))


def _city_shift(s, seed):
    """街区常规靠近公路；跨线桥附近退回原位置，绕开原桥台。"""
    zone, local = district(s, seed)
    bridge = 1-smooth(18, 75, abs(local-820)) if zone in (1, 3) else 0
    return -24*(1-bridge)


def ground_height(d, s, road_z, seed):
    """距离轴连续；原20–34m碰撞树带仍为路面下0.32m。"""
    width = abs(d)
    if width < 19:
        return -.32 + math.sin((width - 8.5) / 10.5 * math.pi) * .22
    if width <= 35:
        return -.32
    phase = seed % 19 * .3
    zone, local = district(s, seed)
    bridge = (1-smooth(6, 28, abs(local-820))) if zone in (1, 3) else 0
    ramp = bridge * smooth(35, 54, width) * (1-smooth(56, 115, width))
    if d < 0:
        height = 13 + 7 * math.sin(s / 470 + phase) + 3 * math.sin(s / 139)
        hill = smooth(35, 76, width) * height + smooth(76, 120, width) * 12
        detail = smooth(35, 44, width) * (1 - smooth(108, 120, width))
        base = -.32 + hill + detail * (.55 * math.sin(s * .11 + d * .3))
        return max(base, -.32 + ramp * 7.4)
    # 右侧填方始终接到同一个真实海平面，高架/丘陵路不会把海面抬起来。
    edge = 74 + 5 * math.sin(s / 63 + phase) + 3 * math.sin(s / 23)
    base = -.32 - smooth(35, edge, width) * (road_z + 4.4)
    urban = city_weight(s, seed)
    if urban:
        # 主路及35米内树带原样；城市在连续大陆上，岸线位于街区外侧。
        shore = 340 + 18*math.sin(s/220+phase) + 9*math.sin(s/61)
        shift = _city_shift(s, seed)
        upper = max(.85, road_z-1.5)
        deck = upper+(.85-upper)*smooth(155+shift, 225+shift, width)
        terrace = -.32*(1-smooth(35, 61.5+shift, width)) + (deck-road_z)*smooth(35, 61.5+shift, width)
        coast = smooth(shore-28, shore+22, width)
        mainland = terrace*(1-coast) - (road_z+4.4)*coast
        base = base*(1-urban) + mainland*urban
    return base * (1-ramp) + 7.0 * ramp


def _row_ground_params(s, seed):
    phase = seed % 19 * .3
    zone, local = district(s, seed)
    bridge_ramp = (1 - smooth(6, 28, abs(local - 820))) if zone in (1, 3) else 0
    left_height = 13 + 7 * math.sin(s / 470 + phase) + 3 * math.sin(s / 139)
    s_sin11 = s * .11
    edge = 74 + 5 * math.sin(s / 63 + phase) + 3 * math.sin(s / 23)
    urban = city_weight(s, seed)
    if urban:
        shore = 340 + 18 * math.sin(s / 220 + phase) + 9 * math.sin(s / 61)
        shift = _city_shift(s, seed)
    else:
        shore = shift = 0.0
    return bridge_ramp, left_height, s_sin11, edge, urban, shore, shift


def _fast_ground_height(d, params, road_z):
    width = abs(d)
    if width < 19:
        return -.32 + math.sin((width - 8.5) / 10.5 * math.pi) * .22
    if width <= 35:
        return -.32
    bridge_ramp, left_height, s_sin11, edge, urban, shore, shift = params
    ramp = bridge_ramp * smooth(35, 54, width) * (1 - smooth(56, 115, width))
    if d < 0:
        hill = smooth(35, 76, width) * left_height + smooth(76, 120, width) * 12
        detail = smooth(35, 44, width) * (1 - smooth(108, 120, width))
        base = -.32 + hill + detail * (.55 * math.sin(s_sin11 + d * .3))
        return max(base, -.32 + ramp * 7.4)
    base = -.32 - smooth(35, edge, width) * (road_z + 4.4)
    if urban:
        upper = max(.85, road_z - 1.5)
        deck = upper + (.85 - upper) * smooth(155 + shift, 225 + shift, width)
        terrace = -.32 * (1 - smooth(35, 61.5 + shift, width)) + (deck - road_z) * smooth(35, 61.5 + shift, width)
        coast = smooth(shore - 28, shore + 22, width)
        mainland = terrace * (1 - coast) - (road_z + 4.4) * coast
        base = base * (1 - urban) + mainland * urban
    return base * (1 - ramp) + 7.0 * ramp


def _smooth_arr(a, b, value):
    t = np.clip((value - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _fast_ground_height_arr(d, params, road_z):
    width = np.abs(d)
    bridge_ramp, left_height, s_sin11, edge, urban, shore, shift = params
    ramp = bridge_ramp * _smooth_arr(35.0, 54.0, width) * (1.0 - _smooth_arr(56.0, 115.0, width))
    # 左侧路堑山坡
    hill = _smooth_arr(35.0, 76.0, width) * left_height + _smooth_arr(76.0, 120.0, width) * 12.0
    detail = _smooth_arr(35.0, 44.0, width) * (1.0 - _smooth_arr(108.0, 120.0, width))
    left_val = np.maximum(-0.32 + hill + detail * (0.55 * np.sin(s_sin11 + d * 0.3)), -0.32 + ramp * 7.4)
    # 右侧海湾与城市大陆
    right_base = -0.32 - _smooth_arr(35.0, edge, width) * (road_z + 4.4)
    if urban:
        upper = max(0.85, road_z - 1.5)
        deck = upper + (0.85 - upper) * _smooth_arr(155.0 + shift, 225.0 + shift, width)
        t_w = _smooth_arr(35.0, 61.5 + shift, width)
        terrace = -0.32 * (1.0 - t_w) + (deck - road_z) * t_w
        coast = _smooth_arr(shore - 28.0, shore + 22.0, width)
        mainland = terrace * (1.0 - coast) - (road_z + 4.4) * coast
        right_base = right_base * (1.0 - urban) + mainland * urban
    right_val = right_base * (1.0 - ramp) + 7.0 * ramp
    out = np.where(d < 0.0, left_val, right_val)
    inner = -0.32 + np.sin((width - 8.5) / 10.5 * math.pi) * 0.22
    out = np.where(width <= 35.0, -0.32, out)
    return np.where(width < 19.0, inner, out)


@lru_cache(maxsize=256)
def _cached_highway_terrain_z(seed_key, height_key, base_height, d, s, terrain_seed):
    # 仅复用纯由道路参数决定的基准高程，不持有 curve 实例引用。
    index = math.floor(s / 1000)
    t = (s - index * 1000) / 1000
    from highway_segments import _mix

    bits = _mix(seed_key ^ _mix(index))
    hill = -1 if bits & 2 else 1
    b = 64 * t ** 3 * (1 - t) ** 3
    road_z = base_height + hill * height_key * b
    return road_z + ground_height(d, s, road_z, terrain_seed)


def _row_params_2d(s_col, seed):
    rows = len(s_col)
    phase = seed % 19 * .3
    s_flat = s_col[:, 0]
    bridge_ramp = np.empty(rows, dtype=np.float64)
    urban_arr = np.empty(rows, dtype=np.float64)
    shore_arr = np.zeros(rows, dtype=np.float64)
    shift_arr = np.zeros(rows, dtype=np.float64)
    for idx_r, sv in enumerate(s_flat):
        zone, loc = district(float(sv), seed)
        bridge_ramp[idx_r] = (1.0 - smooth(6, 28, abs(loc - 820))) if zone in (1, 3) else 0.0
        u_val = city_weight(float(sv), seed)
        urban_arr[idx_r] = u_val
        if u_val:
            shore_arr[idx_r] = 340 + 18 * math.sin(sv / 220 + phase) + 9 * math.sin(sv / 61)
            shift_arr[idx_r] = _city_shift(float(sv), seed)
    left_h = 13.0 + 7.0 * np.sin(s_col / 470.0 + phase) + 3.0 * np.sin(s_col / 139.0)
    edge = 74.0 + 5.0 * np.sin(s_col / 63.0 + phase) + 3.0 * np.sin(s_col / 23.0)
    return (bridge_ramp[:, None], left_h, s_col * 0.11, edge,
            urban_arr[:, None], shore_arr[:, None], shift_arr[:, None])


def _height_2d(d_mat, params, road_z):
    w_mat = np.abs(d_mat)
    br, lh, ss11, ed, ur, sh, sf = params
    ramp = br * _smooth_arr(35.0, 54.0, w_mat) * (1.0 - _smooth_arr(56.0, 115.0, w_mat))
    hill = _smooth_arr(35.0, 76.0, w_mat) * lh + _smooth_arr(76.0, 120.0, w_mat) * 12.0
    detail = _smooth_arr(35.0, 44.0, w_mat) * (1.0 - _smooth_arr(108.0, 120.0, w_mat))
    left_v = np.maximum(-0.32 + hill + detail * (0.55 * np.sin(ss11 + d_mat * 0.3)), -0.32 + ramp * 7.4)
    right_base = -0.32 - _smooth_arr(35.0, ed, w_mat) * (road_z + 4.4)
    if np.any(ur):
        upper = np.maximum(0.85, road_z - 1.5)
        deck = upper + (0.85 - upper) * _smooth_arr(155.0 + sf, 225.0 + sf, w_mat)
        t_w = _smooth_arr(35.0, 61.5 + sf, w_mat)
        terrace = -0.32 * (1.0 - t_w) + (deck - road_z) * t_w
        coast = _smooth_arr(sh - 28.0, sh + 22.0, w_mat)
        mainland = terrace * (1.0 - coast) - (road_z + 4.4) * coast
        right_base = right_base * (1.0 - ur) + mainland * ur
    right_v = right_base * (1.0 - ramp) + 7.0 * ramp
    out = np.where(d_mat < 0.0, left_v, right_v)
    inner = -0.32 + np.sin((w_mat - 8.5) / 10.5 * math.pi) * 0.22
    out = np.where(w_mat <= 35.0, -0.32, out)
    return np.where(w_mat < 19.0, inner, out)


def _curve_cols_2d(curve, start, total_rows, offset):
    samples = [curve.sample(float(start + row * 5 + offset)) for row in range(total_rows)]
    cx = np.array([c.x for c in samples], dtype=np.float64)[:, None]
    cy = np.array([c.y for c in samples], dtype=np.float64)[:, None]
    cz = np.array([c.z for c in samples], dtype=np.float64)[:, None]
    h = np.radians(np.array([c.heading for c in samples], dtype=np.float64))[:, None]
    return cx, cy, cz, np.cos(h), np.sin(h)


def terrain_point(curve, d, s, seed):
    if type(curve) is HighwayCurve:
        cache = _TERRAIN_XYZ_BY_CURVE.get(curve)
        if cache is None:
            cache = {}
            _TERRAIN_XYZ_BY_CURVE[curve] = cache
        key = (d, s, seed)
        xyz = cache.get(key)
        if xyz is None:
            p = sample(curve, s, d)
            z = _cached_highway_terrain_z(curve.seed, curve.height, curve.base_height, d, s, seed)
            xyz = (p.x, p.y, z)
            if len(cache) >= 512:
                cache.clear()
            cache[key] = xyz
        return Vec3(*xyz)
    p = sample(curve, s, d)
    if curve is not None and hasattr(curve, 'base_height') and hasattr(curve, 'advance'):
        p.z = _cached_highway_terrain_z(curve.seed, curve.height, curve.base_height, d, s, seed)
    else:
        p.z += ground_height(d, s, p.z, seed)
    return p


def sign_lateral(model, lateral, s, seed):
    """隔音屏段的小牌放在路肩；实际1.96m宽牌面与屏障保留净距。"""
    if model not in ('speed-limit', 'curve-left', 'curve-right', 'hill-warning', 'wind-warning'):
        return lateral
    zone, local = district(s, seed)
    # 屏障每段从里程锚点向前延伸4米，边界也给牌面厚度留出空间。
    return 8.8 if zone in (1, 3) and 519 <= local <= 981 else lateral


def positions(index, seed, curve=None):
    """返回绝对里程设施；相邻分段不重复拥有同一节点。"""
    start, end = index * 200, (index + 1) * 200
    items = []
    for s in range(start, end):
        zone, local = district(s, seed)
        if zone in (1, 3) and 740 <= local < 900 and s % 80 == 20:
            items.extend(("lamp", side * 9.2, s, 0 if side < 0 else 180) for side in (-1, 1))
        if s % 20 == 10:
            items.extend(("reflector", side * 8.3, s, 0) for side in (-1, 1))
        if s % 24 == 12:
            items.extend(("drain-grate", side * 7.5, s, 0) for side in (-1, 1))
        if s % 4 == 0 and zone in (1, 3) and 520 <= local < 980:
            items.append(("soundwall", 10.4, s, 0))
        if local == 340:
            items.append(("route-direction", 12.8, s, 0))
        if s % 1000 == 100:
            items.append(("speed-limit", 10.3, s, 0))
        if local == 802 and zone in (1, 3):
            items.append(("bridge-advance", 12.8, s, 0))
        # 横风牌用独立里程槽，避免区域1100m恰好与周期限速牌重合。
        if s % 1000 == 250 and zone == 0:
            items.append(("wind-warning", 10.4, s, 0))
        if curve and s % 1000 == 50:
            turn = curve.sample(s+200).heading-curve.sample(s+80).heading
            if abs(turn) >= 5:
                items.append(("curve-left" if turn > 0 else "curve-right",10.4,s,0))
        if curve and s % 1000 == 520 and curve.sample(s+100).grade < -3:
            items.append(("hill-warning",10.4,s,0))
        if local == 540:
            items.append(("gantry", 0, s, 0))
        if local == 820 and zone in (1, 3):
            items.append(("overpass", 0, s, 0))
        if local == 516 and zone in (1, 3):
            items.append(("crash-cushion", 10.4, s, 0))
        if s % 1000 == 0:
            items.append(("kilometer", 9.7, s, 0))
        if local == 1120:
            items.append(("equipment", -10.7, s, 0))
    return [(model, sign_lateral(model, d, s, seed), s, heading) for model, d, s, heading in items]


def detail_group(root, curve, index, name="expressway-detail-distance", distance=780):
    """近景资产按显示距离绘制，原物理segment的存活窗口不变。"""
    lod = LODNode(name)
    lod.setCenter(sample(curve,index*200+100)-Vec3(*anchor(curve,index)))
    # 完全淡出后才裁掉整组，分段中心与树冠外廓不能提前触发硬切换。
    lod.addSwitch(distance,0)
    return root.attachNewNode(lod).attachNewNode("near-detail")


def build_segment(root, index, seed, kit, stabilize_rail, curve=None):
    """初次加载和静态检查完成全部步骤；驾驶中由Scene逐帧消费。"""
    for _ in segment_steps(root, index, seed, kit, stabilize_rail, curve):
        pass


def rail_shadow_coordinate(curve, distance, lateral, height=0):
    """0.8m护栏沿固定太阳方向投到当前坡面，不使用玩家距离。"""
    pose = curve.sample(distance) if curve else None
    heading = math.radians(pose.heading) if pose else 0
    grade = math.radians(pose.grade) if pose else 0
    # 普通高速沿用原太阳；沿海生涯的护栏投影与同一落日方向配套。
    x, y = .44, .60
    if isinstance(curve, CareerCourse) and curve.course_id in ('coast-club', 'coast-final'):
        from environment.expressway_materials import daylight_environment
        from paths import resource_root

        _environment, metadata = daylight_environment(resource_root()/'assets/game/environment/coastal-sunset')
        sx, sy, sz = metadata['directional_sun']
        x, y = -sx/sz, -sy/sz
    forward = -x * math.sin(heading) + y * math.cos(heading)
    cross = x * math.cos(heading) + y * math.sin(heading)
    denominator = 1 + math.tan(grade) * forward
    # 太阳低于局部坡面时没有朝光面的解析交点，仍交给原太阳阴影处理。
    reach = max(0, .8-height) * cross / denominator if denominator > 1e-5 else 0.
    return lateral, reach


def _set_rail_shadow_fast(node, coordinates, faces):
    from environment.surface_mesh import rail_shadow_format

    data = node.node().modifyGeom(0).modifyVertexData()
    data.setFormat(rail_shadow_format(data.getFormat()))
    flat_idx = np.asarray(faces, dtype=np.intp).reshape(-1)
    shadow_arr = np.asarray(coordinates, dtype='<f4')[flat_idx]
    data.modifyArray(1).modifyHandle().setData(shadow_arr.tobytes())


def segment_steps(root, index, seed, kit, stabilize_rail, curve=None):
    from environment.surface_mesh import flatten_steps, set_rail_shadow_coordinates
    from scene import make_box, make_mesh

    start = index * SEGMENT_LENGTH
    origin = Vec3(*anchor(curve, index))

    def point(d, s, z=0):
        p = sample(curve, s, d) - origin
        p.z += z
        return p

    def strip_batch(name, left, right, z, color, spans):
        vertices, faces, coordinates = [], [], []
        for first, last in spans:
            rows = [first]
            rows.extend(s for s in range(math.floor(first / 5) * 5 + 5, math.ceil(last), 5) if s < last)
            rows.append(last)
            base = len(vertices)
            for s in rows:
                pose = curve.sample(s) if curve else None
                if pose is not None:
                    h_rad = math.radians(pose.heading)
                    rx, ry = math.cos(h_rad), math.sin(h_rad)
                    px, py, pz = pose.x - origin.x, pose.y - origin.y, pose.z - origin.z + z
                    g_tan = math.tan(math.radians(pose.grade))
                    # 复用单次道路采样同步计算两侧顶点与护栏投影坐标。
                    sx, sy = (.44, .60)
                    if isinstance(curve, CareerCourse) and curve.course_id in ('coast-club', 'coast-final'):
                        _, sh_left = rail_shadow_coordinate(curve, s, left, z)
                        _, sh_right = rail_shadow_coordinate(curve, s, right, z)
                    else:
                        fwd = -sx * math.sin(h_rad) + sy * math.cos(h_rad)
                        crs = sx * math.cos(h_rad) + sy * math.sin(h_rad)
                        den = 1 + g_tan * fwd
                        reach = max(0, .8 - z) * crs / den if den > 1e-5 else 0.0
                        sh_left = sh_right = reach
                    vertices.append((px + left * rx, py + left * ry, pz))
                    vertices.append((px + right * rx, py + right * ry, pz))
                    coordinates.append((left, sh_left))
                    coordinates.append((right, sh_right))
                else:
                    for d in (left, right):
                        vertices.append(tuple(point(d, s, z)))
                        coordinates.append(rail_shadow_coordinate(curve, s, d, z))
            for r in range(len(rows) - 1):
                a = base + r * 2
                faces.extend(((a, a + 1, a + 3), (a, a + 3, a + 2)))
        node = make_mesh(name, vertices, faces, Vec4(*color))
        _set_rail_shadow_fast(node, coordinates, faces)
        node.setMaterial(kit["surface-material"])
        node.setShader(kit["road-shadow-shader"])
        node.setDepthOffset(1)
        node.reparentTo(root)
        return node

    # 直接使用冻结物理路网的显示网格，道路/护栏不重新近似。
    surfaces = curve_mesh.surfaces(curve, index) if curve else surface_meshes()
    yield "surface-prepare"
    # 道路和路肩共用的边线点完全相同，只保留本段的精确投影结果。
    surface_inputs = {}
    for name, (vertices, faces) in surfaces.items():
        if name == "ground":
            continue
        rail = name.startswith("rail")
        if curve and rail:
            # 原曲线碰撞盒的三角形朝内；显示副本翻面，避免朝上的底面与路肩争深度。
            faces = [(a, c, b) for a, b, c in faces]
        color = (1, 1, 1, 1) if name == 'road' else ((.53, .59, .56, 1) if rail else (.11, .13, .14, 1))
        node = make_mesh(f"expressway-{name}", vertices, faces, Vec4(*color))
        node.setMaterial(kit["surface-material"])
        node.reparentTo(root)
        if rail:
            stabilize_rail(node)
        else:
            coordinates = []
            road_uv = []
            for vertex in vertices:
                if vertex not in surface_inputs:
                    world = Vec3(*vertex) + origin
                    distance, lateral = curve.project(tuple(world)) if curve else (world.y, world.x)
                    # 2米实拍范围；每600米周期重置，段末保留连续坐标避免插值跨越接缝。
                    surface_inputs[vertex] = (rail_shadow_coordinate(curve, distance, lateral),
                                             (lateral/2., (start % 600+distance-start)/2.))
                shadow, uv = surface_inputs[vertex]
                coordinates.append(shadow)
                road_uv.append(uv)
                if len(coordinates) % 64 == 0:
                    yield 'surface-coordinates'
            _set_rail_shadow_fast(node, coordinates, faces)
            node.setTexture(kit["aggregate"])
            node.setShader(kit["road-shadow-shader"])
            if name == 'road':
                data = node.node().modifyGeom(0).modifyVertexData()
                flat_idx = np.asarray(faces, dtype=np.intp).reshape(-1)
                uv_arr = np.asarray(road_uv, dtype='<f4')[flat_idx]
                arr0 = data.modifyArray(0).modifyHandle()
                dtype0 = np.dtype([('p', '<f4', 3), ('n', '<f4', 3), ('c', 'u1', 4), ('uv', '<f4', 2)])
                buf = np.frombuffer(arr0.getData(), dtype=dtype0).copy()
                buf['uv'] = uv_arr
                arr0.setData(buf.tobytes())
                node.setTexture(kit['road-albedo'])
                node.setShader(kit['road-asphalt-shader'])
                node.setShaderInput('asphalt_normals', kit['road-normal'])
                node.setShaderInput('asphalt_roughness', kit['road-roughness'])
        yield "surface"
    for d in (-2.25, 2.25):
        dashes = [(s, s + 4) for s in range(start, start + 200, 8)]
        for offset in range(0, len(dashes), 8):
            strip_batch("white-lane-dash", d - .07, d + .07, .035, WHITE, dashes[offset:offset + 8])
            yield "markings"
    for side in (-1, 1):
        d = side * 6.56
        strip_batch("edge-line", d - .075, d + .075, .04,
                    (.88, .62, .13, 1) if side < 0 else WHITE, ((start, start + 200),))
        d = side * 7.68
        strip_batch("drain-channel", d - .18, d + .18, .021, (.29, .31, .29, 1), ((start, start + 200),))
        rumbles = [(s, s + .25) for s in range(start, start + 200, 4)]
        d = side * 6.99
        for offset in range(0, len(rumbles), 25):
            strip_batch("shoulder-rumble", d - .14, d + .14, .029, (.24, .26, .24, 1), rumbles[offset:offset + 25])
            yield "markings"
    details = detail_group(root, curve, index)
    details.setShader(kit["detail-shader"], 1)
    signs = detail_group(root, curve, index, "expressway-sign-distance", 1200)
    signs.setShader(kit["distance-shader"], 1)
    cells = {}
    drain_local_cache = {}

    def detail_parent(s):
        # 原生合批限制在20m小块，避免整段草木的不可打断unify长帧。
        cell = math.floor((s - start) / 20)
        if cell not in cells:
            cells[cell] = details.attachNewNode(f"detail-cell-{cell}")
        return cells[cell]

    yield from landscape_steps(root, index, seed, curve, kit, detail_parent)
    for model, d, s, heading in positions(index, seed, curve):
        p = sample(curve, s, d)
        z = .025 if model == "drain-grate" else 0 if abs(d) < 8.5 else ground_height(d, s, p.z, seed)
        asset = ('ridge-gantry' if model == 'gantry' and isinstance(curve, CareerCourse)
                 and curve.course_id in ('budget-ridge-suspension', 'budget-ridge-long-waves')
                 and s == 540 else model)
        node = kit[asset].copyTo(signs if model in SIGN_MODELS else detail_parent(s))
        node.setPos(point(d, s, z))
        pose = curve.sample(s) if curve else None
        node.setH(heading + (pose.heading if pose else 0))
        if model == "drain-grate":
            # 排水盖也处于连续护栏遮蔽中，不能随实时阴影范围跳变。
            projections = {}
            for path in node.findAllMatches("**/+GeomNode"):
                # 展开的三角形反复引用同一角点；缓存模板局部索引并按刚体变换复用投影。
                mat = path.getMat(root)
                for geom_index in range(path.node().getNumGeoms()):
                    vdata = path.node().getGeom(geom_index).getVertexData()
                    key_id = int(vdata.this)
                    cached_locals = drain_local_cache.get(key_id)
                    if cached_locals is None:
                        reader = GeomVertexReader(vdata, "vertex")
                        unique_pts = []
                        index_map = {}
                        inverse = []
                        while not reader.isAtEnd():
                            local = tuple(reader.getData3f())
                            pt_idx = index_map.get(local)
                            if pt_idx is None:
                                pt_idx = len(unique_pts)
                                unique_pts.append(local)
                                index_map[local] = pt_idx
                            inverse.append(pt_idx)
                        cached_locals = (unique_pts, inverse)
                        drain_local_cache[key_id] = cached_locals
                    unique_pts, inverse = cached_locals
                    coord_table = []
                    for local in unique_pts:
                        world = mat.xformPoint(Vec3(*local)) + origin
                        key = world.x, world.y
                        if key not in projections:
                            distance, lateral = curve.project(tuple(world)) if curve else (world.y, world.x)
                            road_z = curve.sample(distance).z if curve else 0
                            projections[key] = distance, lateral, road_z
                        distance, lateral, road_z = projections[key]
                        coord_table.append(rail_shadow_coordinate(curve, distance, lateral, world.z-road_z))
                    set_rail_shadow_coordinates(path, [coord_table[i] for i in inverse], geom_index=geom_index)
            node.setShader(kit["road-shadow-shader"], 2)
            yield "drain-shadow"
        if model == "kilometer":
            kilometer_face(node, s, kit["kilometer-base"], kit["sign-digits"])
        if model == "soundwall" and pose:
            node.setP(pose.grade)
        if model == "overpass":
            # 桥台与缓坡跟随局部道路朝向，高程由当前道路决定。
            for side in (-1, 1):
                floor = min(-.32, ground_height(side * 46, s, p.z, seed))
                abutment = make_box("bridge-abutment", (10, 6, (6.6-floor)/2), Vec4(.43, .46, .42, 1))
                abutment.reparentTo(detail_parent(s))
                abutment.setPos(point(side * 46, s, (6.6+floor)/2))
                abutment.setH(pose.heading if pose else 0)
        yield "facilities"
    # 物理树的位置、高程和绝对朝向严格沿用streamed_road。
    seg_trees = segment(seed, index).trees
    for number, (d, local, scale, heading) in enumerate(seg_trees):
        tree = kit[f"tree-{(index + number) % 2}"].copyTo(detail_parent(start + local))
        tree.setPos(point(d, start + local, -.32 + .05 * scale))
        tree.setScale(scale)
        tree.setH(heading)
        if number % 2 == 1 or number == len(seg_trees) - 1:
            yield "trees"
    road_batch = root.attachNewNode("road-batch")
    for child in list(root.getChildren()):
        if child != road_batch and not isinstance(child.node(), LODNode):
            child.reparentTo(road_batch)
    road_batch.clearModelNodes()
    yield from flatten_steps(road_batch)
    yield "road-batch"
    for cell in cells.values():
        # 距离档内部保持共享网格；递归flatten会把每株完整针叶复制进独立顶点表。
        batch = cell.attachNewNode('static-details')
        for child in tuple(cell.getChildren()):
            if child != batch and child.find('**/+LODNode').isEmpty() and not isinstance(child.node(), LODNode):
                child.reparentTo(batch)
        if batch.getNumChildren():
            batch.clearModelNodes()
            yield from flatten_steps(batch)
        yield "detail-batch"
    signs.clearModelNodes()
    signs.flattenStrong()
    yield "sign-batch"
    root.setTag("visual-route", "HWY-02")


def landscape_steps(root, index, seed, curve, kit, detail_parent):
    from scene import make_mesh

    start = index * 200
    origin = Vec3(*anchor(curve, index))
    if isinstance(curve, CareerCourse):
        from environment.surface_mesh import surface_mesh

        coastal = None
        if coast_candidate(curve.course_id):
            from environment.career_coast import _segment

            coastal = _segment(curve.course_id, index, origin)
        if coastal is not None:
            vertices, faces, normals, colors = coastal
        else:
            vertices, faces = curve_mesh.surfaces(curve,index)['ground']
            accumulated = [Vec3(0, 0, 0) for _ in vertices]
            for a, b, c in faces:
                normal = (Vec3(*vertices[b])-Vec3(*vertices[a])).cross(Vec3(*vertices[c])-Vec3(*vertices[a])).normalized()
                accumulated[a] += normal
                accumulated[b] += normal
                accumulated[c] += normal
            normals = [tuple(n.normalized()) if n.lengthSquared() > 0 else (0., 0., 1.) for n in accumulated]
            colors = [(.24, .34, .08, 0)]*len(vertices)
        uv = []
        for p in vertices:
            distance, lateral = curve.project((p[0]+origin.x, p[1]+origin.y))
            uv.append((lateral, distance))
        node = surface_mesh('course-landscape', vertices, faces, normals, colors, uv)
        node.setTexture(kit['ground'])
        node.setShader(kit['route-terrain-shader'], 1)
        node.setShaderInput('expressway_rock', kit['rock'])
        node.setMaterial(kit['surface-material'])
        node.reparentTo(root)
        yield 'course-terrain'
        return
    columns = TERRAIN_COLUMNS
    beds = understory(index,seed)
    for side in (-1, 1):
        widths = columns if side < 0 else tuple(sorted(set(columns + (
            65, 75, 90, 110, 125, 140, 155, 170, 200, 215, 225, 280, 315, 355, 400))))
        cross = sorted(side * d for d in widths)
        urban_mesh = side > 0 and any(city_weight(start+local, seed) for local in (0, 100, 200))
        width = len(cross)+(3 if urban_mesh else 0)
        total_rows = 41
        total_verts = total_rows * width
        s_vec = np.arange(start, start + 201, 5, dtype=np.float64)[:, None]
        if urban_mesh:
            cross_base = np.asarray(cross, dtype=np.float64)
            d_2d = np.empty((total_rows, width), dtype=np.float64)
            for row_index in range(total_rows):
                shift = _city_shift(start + row_index * 5, seed)
                d_2d[row_index] = np.sort(
                    np.concatenate((cross_base, (61.5 + shift, 155.0 + shift, 225.0 + shift)))
                )
        else:
            d_2d = np.broadcast_to(np.asarray(cross, dtype=np.float64)[None, :], (total_rows, width))

        p0 = _row_params_2d(s_vec, seed)
        pm = _row_params_2d(s_vec - 0.1, seed)
        pp = _row_params_2d(s_vec + 0.1, seed)
        yield "terrain-row"
        if curve is not None:
            cx0, cy0, cz0, rx0, ry0 = _curve_cols_2d(curve, start, total_rows, 0.0)
            cxm, cym, czm, rxm, rym = _curve_cols_2d(curve, start, total_rows, -0.1)
            cxp, cyp, czp, rxp, ryp = _curve_cols_2d(curve, start, total_rows, 0.1)
            px = cx0 + d_2d * rx0
            py = cy0 + d_2d * ry0
            pz = cz0 + _height_2d(d_2d, p0, cz0)
            dx_x, dx_y = 0.2 * rx0, 0.2 * ry0
            dx_z = _height_2d(d_2d + 0.1, p0, cz0) - _height_2d(d_2d - 0.1, p0, cz0)
            dy_x = (cxp + d_2d * rxp) - (cxm + d_2d * rxm)
            dy_y = (cyp + d_2d * ryp) - (cym + d_2d * rym)
            dy_z = (czp + _height_2d(d_2d, pp, czp)) - (czm + _height_2d(d_2d, pm, czm))
        else:
            zeros = np.zeros((total_rows, 1), dtype=np.float64)
            px = d_2d
            py = np.broadcast_to(s_vec, (total_rows, width))
            pz = _height_2d(d_2d, p0, zeros)
            dx_x, dx_y = 0.2, 0.0
            dx_z = _height_2d(d_2d + 0.1, p0, zeros) - _height_2d(d_2d - 0.1, p0, zeros)
            dy_x, dy_y = 0.0, 0.2
            dy_z = _height_2d(d_2d, pp, zeros) - _height_2d(d_2d, pm, zeros)
        nx = dx_y * dy_z - dx_z * dy_y
        ny = dx_z * dy_x - dx_x * dy_z
        nz = dx_x * dy_y - dx_y * dy_x
        n_len = np.sqrt(nx * nx + ny * ny + nz * nz)
        safe_len = np.where(n_len > 1e-12, n_len, 1.0)
        nx /= safe_len
        ny /= safe_len
        nz /= safe_len
        yield "terrain-row"
        variation = 0.5 + 0.2 * np.sin(d_2d * 0.27 + s_vec * 0.017) + 0.17 * np.sin(d_2d * 0.61 - s_vec * 0.031)
        base_r = 0.12 + 0.20 * variation
        base_g = 0.22 + 0.17 * variation
        base_b = 0.042 + 0.058 * variation
        shade = np.zeros((total_rows, width), dtype=np.float64)
        for bx, by, br in beds:
            row_mask = np.abs(s_vec[:, 0] - by) <= br * 1.8
            if not np.any(row_mask):
                continue
            dist = ((d_2d[row_mask] - bx) / br) ** 2 + ((s_vec[row_mask] - by) / (br * 1.8)) ** 2
            shade[row_mask] = np.maximum(shade[row_mask], np.maximum(0.0, 1.0 - dist) ** 2 * 0.55)
        inv_shade = 1.0 - shade
        vertices_arr = np.stack((px - origin.x, py - origin.y, pz - origin.z), axis=-1).astype(np.float32)
        normals_arr = np.stack((nx, ny, nz), axis=-1).astype(np.float32)
        alpha_arr = _smooth_arr(0.03, 0.19, 1.0 - nz) if side < 0 else np.zeros((total_rows, width), dtype=np.float64)
        colors_arr = np.stack((base_r * inv_shade + 0.17 * shade,
                               base_g * inv_shade + 0.22 * shade,
                               base_b * inv_shade + 0.075 * shade,
                               alpha_arr), axis=-1)
        uv_arr = np.stack((d_2d, np.broadcast_to(s_vec - start + (start % 600), (total_rows, width))), axis=-1).astype(np.float32)
        r_idx = np.arange(40, dtype='<u4')[:, None] * width + np.arange(width - 1, dtype='<u4')[None, :]
        tri1 = np.stack((r_idx, r_idx + 1, r_idx + width + 1), axis=-1).reshape(-1, 3)
        tri2 = np.stack((r_idx, r_idx + width + 1, r_idx + width), axis=-1).reshape(-1, 3)
        faces = np.empty((40 * (width - 1) * 2, 3), dtype='<u4')
        faces[0::2] = tri1
        faces[1::2] = tri2
        from environment.surface_mesh import surface_mesh

        node = surface_mesh(
            "route-landscape",
            vertices_arr.reshape(total_verts, 3),
            faces,
            normals_arr.reshape(total_verts, 3),
            colors_arr.reshape(total_verts, 4),
            uv_arr.reshape(total_verts, 2),
        )
        node.setTexture(kit["ground"])
        node.setShader(kit["route-terrain-shader"], 1)
        node.setShaderInput("expressway_rock", kit["rock"])
        node.setMaterial(kit["surface-material"])
        node.reparentTo(root)
        yield "terrain-mesh"
    yield from vegetation_steps(root,index,seed,curve,kit,detail_parent)
    if index % 3 != 0:
        s, d = start + 94, -42
        rock = kit["strata-shelf"].copyTo(detail_parent(s))
        rock.setPos(terrain_point(curve, d, s, seed) - origin - Vec3(0, 0, .4))
        rock.setScale(1.2, 1.8, 1.1)
        rock.setH((curve.sample(s).heading if curve else 0) + 15)
        yield "rocks"
    # 每段都持有自己的海面和背景截面，随原segment回收，不堆积远景。
    water_vertices, faces = [], []
    for local in range(0, 201, 5):
        s = start + local
        for d in (48, 120, 300, 650):
            p = sample(curve, s, d)
            p.z = -3
            water_vertices.append(tuple(p - origin))
    for row in range(40):
        for col in range(3):
            a = row * 4 + col
            faces.extend(((a, a + 1, a + 5), (a, a + 5, a + 4)))
    water = make_mesh("route-bay", water_vertices, faces, Vec4(.035, .25, .34, 1))
    data = water.node().modifyGeom(0).modifyVertexData()
    tw = GeomVertexWriter(data, "texcoord")
    for face in faces:
        for i in face:
            tw.setData2f((48, 120, 300, 650)[i % 4], start % 600 + (i // 4) * 5)
    water.setShader(kit["route-water-shader"], 1)
    water.reparentTo(root)
    yield "water"
    from environment.expressway_mountains import mountain_steps

    yield from mountain_steps(root, index, seed, curve, kit, detail_parent)
    from environment.expressway_city import city_steps

    yield from city_steps(root, index, seed, curve, kit)
