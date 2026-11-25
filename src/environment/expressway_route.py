"""全程高速表现；消费现有道路采样与分段，不管理物理或streaming。"""

import math

from panda3d.core import GeomVertexReader, GeomVertexWriter, LODNode, Vec3, Vec4

import curve_mesh
from career_courses import CareerCourse
from environment.career_coast import _enabled as coast_candidate
from environment.expressway import WHITE, smooth
from environment.expressway_signs import SIGN_MODELS, kilometer_face
from environment.expressway_vegetation import (
    TERRAIN_COLUMNS,
    cover_color,
    understory,
    vegetation_steps,
)
from highway_segments import SEGMENT_LENGTH, segment, surface_meshes


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


def terrain_point(curve, d, s, seed):
    p = sample(curve, s, d)
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


def detail_group(root, curve, index, name="expressway-detail-distance", distance=700):
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


def segment_steps(root, index, seed, kit, stabilize_rail, curve=None):
    from environment.surface_mesh import flatten_steps, set_rail_shadow_coordinates
    from scene import make_box, make_mesh

    start = index * SEGMENT_LENGTH
    origin = Vec3(*anchor(curve, index))

    def point(d, s, z=0):
        p = sample(curve, s, d) - origin
        p.z += z
        return p

    def strip(name, left, right, z, color, first, last):
        rows = [first]
        rows.extend(s for s in range(math.floor(first / 5) * 5 + 5, math.ceil(last), 5) if s < last)
        rows.append(last)
        vertices = [tuple(point(d, s, z)) for s in rows for d in (left, right)]
        faces = [(r * 2, r * 2 + 1, r * 2 + 3) for r in range(len(rows) - 1)]
        faces += [(r * 2, r * 2 + 3, r * 2 + 2) for r in range(len(rows) - 1)]
        node = make_mesh(name, vertices, faces, Vec4(*color))
        coordinates = [rail_shadow_coordinate(curve, s, d, z) for s in rows for d in (left, right)]
        set_rail_shadow_coordinates(node, coordinates, faces)
        node.setMaterial(kit["surface-material"])
        node.setShader(kit["road-shadow-shader"])
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
                if len(coordinates) % 8 == 0:
                    yield 'surface-coordinates'
            set_rail_shadow_coordinates(node, coordinates, faces)
            node.setTexture(kit["aggregate"])
            node.setShader(kit["road-shadow-shader"])
            if name == 'road':
                data = node.node().modifyGeom(0).modifyVertexData()
                writer = GeomVertexWriter(data, 'texcoord')
                for face in faces:
                    for number in face:
                        writer.addData2f(*road_uv[number])
                node.setTexture(kit['road-albedo'])
                node.setShader(kit['road-asphalt-shader'])
                node.setShaderInput('asphalt_normals', kit['road-normal'])
                node.setShaderInput('asphalt_roughness', kit['road-roughness'])
        yield "surface"
    for s in range(start, start + 200, 8):
        for d in (-2.25, 2.25):
            strip("white-lane-dash", d - .07, d + .07, .035, WHITE, s, s + 4)
        yield "markings"
    for side in (-1, 1):
        d = side * 6.56
        strip("edge-line", d - .075, d + .075, .04,
              (.88, .62, .13, 1) if side < 0 else WHITE, start, start + 200)
        d = side * 7.68
        strip("drain-channel", d - .18, d + .18, .021, (.29, .31, .29, 1), start, start + 200)
        for s in range(start, start + 200, 4):
            d = side * 6.99
            strip("shoulder-rumble", d - .14, d + .14, .029, (.24, .26, .24, 1), s, s + .25)
            yield "markings"
    details = detail_group(root, curve, index)
    details.setShader(kit["detail-shader"], 1)
    signs = detail_group(root, curve, index, "expressway-sign-distance", 1200)
    signs.setShader(kit["distance-shader"], 1)
    cells = {}

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
                # 展开的三角形反复引用同一角点；每个局部角点只投影一次，原坐标不变。
                local_coordinates = {}
                for geom_index in range(path.node().getNumGeoms()):
                    reader = GeomVertexReader(path.node().getGeom(geom_index).getVertexData(), "vertex")
                    coordinates = []
                    while not reader.isAtEnd():
                        local = tuple(reader.getData3f())
                        if local not in local_coordinates:
                            world = root.getRelativePoint(path, local) + origin
                            key = world.x, world.y
                            if key not in projections:
                                distance, lateral = curve.project(tuple(world)) if curve else (world.y, world.x)
                                road_z = curve.sample(distance).z if curve else 0
                                projections[key] = distance, lateral, road_z
                            distance, lateral, road_z = projections[key]
                            local_coordinates[local] = rail_shadow_coordinate(curve, distance, lateral, world.z-road_z)
                        coordinates.append(local_coordinates[local])
                    set_rail_shadow_coordinates(path, coordinates, geom_index=geom_index)
                    # 每组格栅36个顶点完成后交还预算，避免整盖累计成一帧长操作。
                    yield "drain-shadow"
            node.setShader(kit["road-shadow-shader"], 2)
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
    for number, (d, local, scale, heading) in enumerate(segment(seed, index).trees):
        tree = kit[f"tree-{(index + number) % 2}"].copyTo(detail_parent(start + local))
        tree.setPos(point(d, start + local, -.32 + .05 * scale))
        tree.setScale(scale)
        tree.setH(heading)
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
        batch.clearModelNodes()
        batch.flattenStrong()
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
            normals = []
            for a, b, c in faces:
                normal = (Vec3(*vertices[b])-Vec3(*vertices[a])).cross(Vec3(*vertices[c])-Vec3(*vertices[a])).normalized()
                normals.extend((normal,normal,normal))
            colors = [(.24, .34, .08, 0)]*len(vertices)
        uv = [(p[0]+origin.x, p[1]+origin.y) for p in vertices]
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
        vertices, normals, colors, uv = [], [], [], []
        for local in range(0, 201, 5):
            s = start + local
            shift = _city_shift(s, seed)
            row_cross = sorted((*cross, 61.5+shift, 155+shift, 225+shift)) if urban_mesh else cross
            # 只跳过原算法必然不影响本行的群落，顶点颜色与原顺序保持一致。
            row_beds = [bed for bed in beds if abs(s-bed[1]) <= bed[2]*1.8]
            for d in row_cross:
                p = terrain_point(curve, d, s, seed)
                dx = terrain_point(curve, d + .1, s, seed) - terrain_point(curve, d - .1, s, seed)
                dy = terrain_point(curve, d, s + .1, seed) - terrain_point(curve, d, s - .1, seed)
                normal = dx.cross(dy).normalized()
                vertices.append(tuple(p - origin))
                normals.append(normal)
                variation = .5 + .2 * math.sin(d * .27 + s * .017) + .17 * math.sin(d * .61 - s * .031)
                base = (.12 + .20 * variation, .22 + .17 * variation, .042 + .058 * variation)
                colors.append((*cover_color(d,s,base,row_beds),
                               smooth(.03, .19, 1 - normal.z) if side < 0 else 0))
                # 有限局部UV保持远里程精度；5/3m周期在600m处同时重复。
                uv.append((d, start % 600 + local))
            yield "terrain-row"
        faces = []
        for row in range(40):
            for col in range(width - 1):
                a = row * width + col
                faces.extend(((a, a + 1, a + width + 1), (a, a + width + 1, a + width)))
        from environment.surface_mesh import surface_mesh

        node = surface_mesh("route-landscape", vertices, faces, normals, colors, uv)
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
            p = sample(curve, s) + Vec3(d, 0, 0)
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
