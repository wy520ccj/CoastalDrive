"""全程高速表现；消费现有道路采样与分段，不管理物理或streaming。"""

import math

from panda3d.core import GeomVertexReader, GeomVertexWriter, LODNode, Vec3, Vec4

import curve_mesh
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
    return base * (1-ramp) + 7.0 * ramp


def terrain_point(curve, d, s, seed):
    p = sample(curve, s, d)
    p.z += ground_height(d, s, p.z, seed)
    return p


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
    return items


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
    # 太阳偏移(-55,-75,125)，光线每下降1m向东/北移动0.44/0.60m。
    forward = -.44 * math.sin(heading) + .60 * math.cos(heading)
    cross = .44 * math.cos(heading) + .60 * math.sin(heading)
    reach = max(0, .8-height) * cross / (1 + math.tan(grade) * forward)
    return lateral, reach


def segment_steps(root, index, seed, kit, stabilize_rail, curve=None):
    from environment.surface_mesh import set_rail_shadow_coordinates
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
    for name, (vertices, faces) in surfaces.items():
        if name == "ground":
            continue
        rail = name.startswith("rail")
        if curve and rail:
            # 原曲线碰撞盒的三角形朝内；显示副本翻面，避免朝上的底面与路肩争深度。
            faces = [(a, c, b) for a, b, c in faces]
        node = make_mesh(f"expressway-{name}", vertices, faces,
                         Vec4(*((.53, .59, .56, 1) if rail else (.11, .13, .14, 1))))
        node.setMaterial(kit["surface-material"])
        node.reparentTo(root)
        if rail:
            stabilize_rail(node)
        else:
            coordinates = []
            for vertex in vertices:
                world = Vec3(*vertex) + origin
                distance, lateral = curve.project(tuple(world)) if curve else (world.y, world.x)
                coordinates.append(rail_shadow_coordinate(curve, distance, lateral))
            set_rail_shadow_coordinates(node, coordinates, faces)
            node.setTexture(kit["aggregate"])
            node.setShader(kit["road-shadow-shader"])
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
        node = kit[model].copyTo(signs if model in SIGN_MODELS else detail_parent(s))
        node.setPos(point(d, s, z))
        pose = curve.sample(s) if curve else None
        node.setH(heading + (pose.heading if pose else 0))
        if model == "drain-grate":
            # 排水盖也处于连续护栏遮蔽中，不能随实时阴影范围跳变。
            projections = {}
            for path in node.findAllMatches("**/+GeomNode"):
                for geom_index in range(path.node().getNumGeoms()):
                    reader = GeomVertexReader(path.node().getGeom(geom_index).getVertexData(), "vertex")
                    coordinates = []
                    while not reader.isAtEnd():
                        world = root.getRelativePoint(path, reader.getData3f()) + origin
                        key = world.x, world.y
                        if key not in projections:
                            distance, lateral = curve.project(tuple(world)) if curve else (world.y, world.x)
                            road_z = curve.sample(distance).z if curve else 0
                            projections[key] = distance, lateral, road_z
                        distance, lateral, road_z = projections[key]
                        coordinates.append(rail_shadow_coordinate(curve, distance, lateral, world.z-road_z))
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
    road_batch.flattenStrong()
    yield "road-batch"
    for cell in cells.values():
        cell.clearModelNodes()
        cell.flattenStrong()
        yield "detail-batch"
    signs.clearModelNodes()
    signs.flattenStrong()
    yield "sign-batch"
    root.setTag("visual-route", "HWY-02")


def landscape_steps(root, index, seed, curve, kit, detail_parent):
    from scene import make_box, make_mesh

    start = index * 200
    origin = Vec3(*anchor(curve, index))
    columns = TERRAIN_COLUMNS
    beds = understory(index,seed)
    for side in (-1, 1):
        cross = sorted(side * d for d in columns)
        vertices, normals, colors, uv = [], [], [], []
        for local in range(0, 201, 5):
            s = start + local
            # 只跳过原算法必然不影响本行的群落，顶点颜色与原顺序保持一致。
            row_beds = [bed for bed in beds if abs(s-bed[1]) <= bed[2]*1.8]
            for d in cross:
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
        width = len(cross)
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
    zone, _ = district(start + 100, seed)
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
    if zone in (2, 3) and index % 3 == 1:
        # 城市拥有岸基，不让高楼直接立在水面上。
        center = sample(curve, start + 100, 235) - origin
        island = make_box("city-quay", (58, 115, 2.3), Vec4(.28, .34, .29, 1))
        island.reparentTo(root)
        island.setPos(center.x, center.y, -origin.z - 2)
        island.setH(curve.sample(start + 100).heading if curve else 0)
        for n in range(4):
            s = start + 25 + n * 42
            p = sample(curve, s, 220 + n * 13) - origin
            height = 18 + ((index * 7 + n * 13) % 33)
            tower = make_box("route-city", (8 + n, 10, height / 2), Vec4(.34, .43, .45, 1))
            tower.reparentTo(root)
            tower.setPos(p.x, p.y, height / 2 - origin.z)
            for level in range(4, height, 5):
                band = make_box("city-window-band", (8.1+n, 10.1, .65), Vec4(.20, .32, .37, 1))
                band.reparentTo(root)
                band.setPos(p.x, p.y, level-origin.z)
            crown = make_box("city-roof", (5+n, 7, 1.5), Vec4(.40, .47, .46, 1))
            crown.reparentTo(root)
            crown.setPos(p.x, p.y, height+1.5-origin.z)
            yield "city"
