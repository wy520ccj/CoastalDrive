"""直线高速0–800m视觉样板；只消费既有segment，不拥有物理或流送状态。"""

import math
from itertools import pairwise

import gltf
from panda3d.core import (
    Filename,
    GeomVertexWriter,
    Material,
    MaterialAttrib,
    NodePath,
    Texture,
    Vec3,
    Vec4,
)

from environment.expressway_signs import SIGN_NAMES, image, kilometer_face
from highway_segments import SEGMENT_LENGTH, segment, surface_meshes
from paths import resource_root

START = 0
END = 800
KIT_NAMES = ("lamp", "reflector", "gantry", "advance-sign", "soundwall",
             "crash-cushion", "drain-grate", "kilometer", "equipment", "overpass",
             "broadleaf-crown", "shrub-bank")
LANDSCAPE_NAMES = ("broadleaf-a", "broadleaf-b", "fine-crown", "fine-shrubs", "strata-shelf")
GRASS = (0.25, 0.34, 0.13, 1)
ROCK = (0.49, 0.46, 0.34, 1)
SOIL = (0.36, 0.30, 0.18, 1)
WHITE = (0.88, 0.87, 0.75, 1)


def stabilize_sun(sun_path, position, origin_y):
    """正交阴影按世界空间的光平面纹素对齐，消除随车移动产生的采样游走。"""
    # 先用固定向量定朝向，避免大坐标相减让旋转矩阵每帧产生舍入扰动。
    offset = Vec3(-55, -75, 125)
    sun_path.setPos(offset)
    sun_path.lookAt(0, 0, 0)
    sun_path.setPos(position + offset)
    rotation = sun_path.getQuat()
    inverse = rotation.conjugate()
    light_position = inverse.xform(sun_path.getPos() + Vec3(0, origin_y, 0))
    lens = sun_path.node().getLens()
    resolution = sun_path.node().getShadowBufferSize()
    for axis, step in ((0, lens.getFilmSize().x / resolution.x),
                       (2, lens.getFilmSize().y / resolution.y)):
        light_position[axis] = round(light_position[axis] / step) * step
    sun_path.setPos(rotation.xform(light_position) - Vec3(0, origin_y, 0))


def includes(index, curve):
    return curve is None and 0 <= index < END // SEGMENT_LENGTH


def load_kit(loader, parent, old_trees):
    """每个Scene加载一次；资源跟随已有Scene父节点释放。"""
    folder = resource_root() / "assets/game/expressway"
    kit = {}
    for name in KIT_NAMES + SIGN_NAMES:
        path = folder / f"{name}.bam"
        if not path.is_file():
            raise FileNotFoundError(f"缺少高速视觉模块：{path}")
        kit[name] = loader.loadModel(Filename.fromOsSpecific(str(path)))
        kit[name].reparentTo(parent)
    kit["aggregate"] = loader.loadTexture(Filename.fromOsSpecific(str(folder / "aggregate.png")))
    kit["aggregate"].setWrapU(Texture.WMRepeat)
    kit["aggregate"].setWrapV(Texture.WMRepeat)
    kit["aggregate"].setMinfilter(Texture.FTLinearMipmapLinear)
    kit["aggregate"].setAnisotropicDegree(8)
    kit["sky"] = loader.loadTexture(Filename.fromOsSpecific(str(folder / "expressway-sky.png")))
    from environment.expressway_materials import (
        distance_shader,
        road_shadow_shader,
        route_water_shader,
        surface_textures,
        terrain_shader,
    )

    kit.update(surface_textures())
    kit["terrain-shader"] = terrain_shader()
    kit["road-shadow-shader"] = road_shadow_shader()
    kit["route-water-shader"] = route_water_shader()
    kit["distance-shader"] = distance_shader()
    kit["detail-shader"] = distance_shader(details=True)
    kit["kilometer-base"] = image("kilometer-base")
    kit["sign-digits"] = image("digits")
    kit["mountain-shader"] = terrain_shader("route-mountain.frag")
    kit["route-terrain-shader"] = terrain_shader("route-terrain.frag")
    for name in LANDSCAPE_NAMES:
        path = folder / f"{name}.glb"
        if not path.is_file():
            raise FileNotFoundError(f"缺少高速Blender资产：{path}")
        kit[name] = NodePath(gltf.load_model(Filename.fromOsSpecific(str(path))))
        kit[name].reparentTo(parent)
    for variant, source in enumerate(old_trees):
        # 深拷贝几何节点后只移除叶片，保留碰撞树干的网格和导入变换。
        tree = source.copyTo(parent)
        for path in tree.findAllMatches("**/+GeomNode"):
            node = path.node()
            for i in reversed(range(node.getNumGeoms())):
                mat = node.getGeomState(i).getAttrib(MaterialAttrib).getMaterial()
                if mat.getName() == "leafsDark":
                    node.removeGeom(i)
        _, trunk_top = tree.getTightBounds()
        crown = kit["fine-crown"].copyTo(tree)
        crown.setScale(0.58, 0.62, 0.65)
        crown_low, _ = crown.getTightBounds(tree)
        crown.setZ(trunk_top.z - 0.12 - crown_low.z)
        kit[f"tree-{variant}"] = tree
    # 工程模块使用顶点色；共享同一个白色粗糙材质，避免每根杆件拆成绘制调用。
    surface = Material("expressway-surface")
    surface.setBaseColor((1,1,1,1))
    surface.setRoughness(.9)
    surface.setMetallic(0)
    kit["surface-material"] = surface
    for name in KIT_NAMES + SIGN_NAMES:
        kit[name].setMaterial(surface,1)
    return kit


def smooth(a, b, value):
    t = max(0, min(1, (value - a) / (b - a)))
    return t * t * (3 - 2 * t)


def terrain_height(x, s):
    """树木所在20–34m平台不抬高；新地形只在既有护栏外。"""
    d = abs(x)
    envelope = smooth(0, 65, s) * (1 - smooth(735, 800, s))
    if d < 19:
        return -0.32 + envelope * math.sin((d - 8.5) / 10.5 * math.pi) * (
            0.30 + 0.2 * math.sin(s / 25))
    if x < 0:
        # 内侧路堑越过保留的林带上升，远端成为山脚。
        cut = smooth(150, 250, s) * (1 - smooth(490, 590, s))
        hill = smooth(35, 72, d) * (9 + 18 * cut)
        hill += smooth(72, 120, d) * (8 + 5 * math.sin(s / 83))
        hill *= 0.85 + 0.15 * math.sin(s / 39)
        hill += smooth(35, 45, d) * (1 - smooth(108, 120, d)) * (
            0.65 * math.sin(s * .15 + d * .31) + 0.35 * math.sin(s * .31 - d * .42))
        return -0.32 + envelope * hill
    # 湾侧填方下放至海面；工程段的桥台与道路平顺相接。
    shoreline_edge = 73 + 5 * math.sin(s * 0.027) + 3 * math.sin(s * 0.067)
    descent = smooth(36, shoreline_edge, d) * 4.5
    return -0.32 - envelope * descent


def terrain_color(x, s):
    """草土石用连续权重过渡；低频斑块提供大尺度色差，细节交给纹理。"""
    def mix(a, b, t):
        return tuple(u * (1 - t) + v * t for u, v in zip(a, b))

    variation = (0.5 + 0.20 * math.sin(x * 0.27 + s * 0.17)
                 + 0.17 * math.sin(x * 0.61 - s * 0.31))
    grass = mix((0.12, 0.22, 0.042), (0.32, 0.39, 0.10), variation)
    slope = abs(terrain_height(x + 0.25, s) - terrain_height(x - 0.25, s)) * 2
    rock_weight = smooth(0.30, 0.69, slope) if x < 0 else 0
    strata = 0.5 + 0.5 * math.sin(terrain_height(x, s) * 2.1 + math.sin(s * 0.035))
    rock = mix((0.34, 0.30, 0.22), (0.61, 0.53, 0.36), strata)
    bare = (1 - smooth(9, 14.5, abs(x))) * 0.8
    color = mix(grass, (0.38, 0.30, 0.16), bare)
    color = mix(color, rock, rock_weight)
    if x > 0:
        height = terrain_height(x, s)
        shore = 1 - smooth(-2.4, -1.2, height)
        color = mix(color, (0.53, 0.45, 0.29), shore)
        wet = 1 - smooth(-3.4, -2.7, height)
        color = mix(color, (0.18, 0.24, 0.18), wet)
    return (*color, 1)


def terrain_columns(side):
    cross = (8.5, 11, 14, 17, 19, 20, 23, 26, 29, 32, 35, *range(38, 120, 3), 120)
    return sorted(side * x for x in cross)


def support_height(x, s):
    """从实际规则网格三角面取接地点，避免解析坡面与低模三角面之间的缝隙。"""
    columns = terrain_columns(-1 if x < 0 else 1)
    left, right = next((a, b) for a, b in pairwise(columns) if a <= x <= b)
    y0 = math.floor(s / 4) * 4
    u, v = (x - left) / (right - left), (s - y0) / 4
    a, b, c, d = (terrain_height(px, py) for px, py in
                  ((left, y0), (right, y0), (right, y0 + 4), (left, y0 + 4)))
    return a * (1 - u) + b * (u - v) + c * v if u >= v else a * (1 - v) + c * u + d * (v - u)


def placements(index):
    """工程设施都用全局里程定位，分段回收重建不改变顺序。"""
    start, end = index * SEGMENT_LENGTH, (index + 1) * SEGMENT_LENGTH
    items = []

    def add(model, x, s, z=0, heading=0):
        if START <= s < END and start <= s < end:
            if abs(x) > 8.5:
                z = -0.32 if model == "soundwall" else terrain_height(x, s)
            items.append((model, x, s - start, z, heading))

    for s in range(20, END, 40):
        for side in (-1, 1):
            add("lamp", side * 9.2, s, 0, 0 if side == -1 else 180)
    for s in range(10, END, 20):
        for side in (-1, 1):
            add("reflector", side * 8.3, s)
    for s in range(12, END, 24):
        for side in (-1, 1):
            add("drain-grate", side * 7.5, s, 0.025)
    for s in range(248, 496, 4):
        add("soundwall", 10.4, s)
    add("advance-sign", 12.8, 110)
    add("gantry", 0, 300)
    add("overpass", 0, 410)
    add("crash-cushion", 10.4, 245)
    add("equipment", -10.7, 340)
    add("kilometer", 9.0, 5)
    return items


def add_strip(parent, name, left, right, z, color, start=0, end=200, texture=None):
    from scene import make_mesh

    vertices = [(left, start, z), (right, start, z), (right, end, z), (left, end, z)]
    node = make_mesh(name, vertices, [(0, 1, 2), (0, 2, 3)], Vec4(*color))
    node.reparentTo(parent)
    if texture is not None:
        node.setTexture(texture)
    return node


def build_terrain(root, index, kit):
    from scene import make_mesh

    start = index * SEGMENT_LENGTH
    # 地貌与连续色权重使用同一张网格，不再用硬边分色的长条带。
    for side in (-1, 1):
        vertices, faces, colors, normals = [], [], [], []
        columns = terrain_columns(side)
        for local_s in range(0, 201, 4):
            s = start + local_s
            for x in columns:
                vertices.append((x, local_s, terrain_height(x, s)))
                colors.append(terrain_color(x, s))
                dx = (terrain_height(x + 0.1, s) - terrain_height(x - 0.1, s)) / 0.2
                dy = (terrain_height(x, s + 0.1) - terrain_height(x, s - 0.1)) / 0.2
                normals.append(Vec3(-dx, -dy, 1).normalized())
        width = len(columns)
        for row in range(50):
            for col in range(width - 1):
                j = row * width + col
                faces.extend(((j, j + 1, j + width + 1), (j, j + width + 1, j + width)))
        node = make_mesh("expressway-landscape", vertices, faces, Vec4(1))
        data = node.node().modifyGeom(0).modifyVertexData()
        color_writer = GeomVertexWriter(data, "color")
        normal_writer = GeomVertexWriter(data, "normal")
        uv_writer = GeomVertexWriter(data, "texcoord")
        for face in faces:
            for i in face:
                color_writer.setData4f(*colors[i])
                normal_writer.setData3f(normals[i])
                # UV携带全局米制坐标，origin重定位不会拖动地表纹理。
                uv_writer.setData2f(vertices[i][0], start + vertices[i][1])
        node.setTexture(kit["ground"])
        node.setShader(kit["terrain-shader"], 1)
        node.setShaderInput("expressway_rock", kit["rock"])
        node.reparentTo(root)
    # 分段式连续灌木带：工程段较密，海湾段留出看海开口。
    beds = ((45, 228, -15), (250, 395, -17), (445, 610, -16), (650, 748, -15),
            (70, 205, 16), (265, 388, 18), (465, 550, 17), (635, 726, 17))
    for first, last, cx in beds:
        for n, s in enumerate(range(first, last, 9)):
            if start <= s < start + 200:
                x = cx + 1.7 * math.sin(n * 1.9)
                bush = kit["fine-shrubs"].copyTo(root)
                bush.setPos(x, s - start, support_height(x, s) - .16)
                bush.setScale(.72 + n % 3 * .1, 1.15, .85 + n % 4 * .08)
                bush.setH(70 + n % 3 * 17)
    # 两层山脚林缘形成成片轮廓；右侧只保留三组，释放海湾视线。
    groves = ((60, 225, -39), (245, 370, -40), (440, 610, -40), (640, 735, -40),
              (65, 190, -57), (250, 365, -66), (475, 600, -60),
              (105, 178, 40), (510, 554, 40), (660, 705, 41))
    for first, last, cx in groves:
        for n, s in enumerate(range(first, last, 17)):
            x = cx + 3.5 * math.sin(n * 2.2)
            if start <= s < start + 200:
                tree = kit["broadleaf-a" if n % 2 else "broadleaf-b"].copyTo(root)
                scale = .92 + n % 4 * .17
                tree.setScale(scale)
                tree.setPos(x, s - start, support_height(x, s) - .10)
                tree.setH(n * 71)
    # 护栏外成片短草与坡脚碎岩，尺度低于灌木，不靠加高树木填空。
    grass_vertices, grass_faces = [], []
    grass_beds = [(s, side * (11.6 + (s // 20) % 3 * .55))
                  for s in range(38, 756, 20) for side in (-1, 1)]
    grass_beds += [(65, -15), (135, 17), (195, -36), (260, -36),
                   (350, -36), (465, -36), (575, -36), (645, -15), (720, 18)]
    for cs, cx in grass_beds:
        for n in range(95):
            s = cs + math.sin(n * 2.4) * (7 + n % 7)
            x = cx + math.cos(n * 2.4) * (.4 + (n % 4) * .25)
            if not start <= s < start + 200:
                continue
            z = support_height(x, s) - 0.035
            size = 0.25 + 0.10 * (n % 4)
            for angle in (n * 0.8, n * 0.8 + 1.9):
                dx, dy = math.cos(angle) * 0.07, math.sin(angle) * 0.07
                base = len(grass_vertices)
                grass_vertices.extend(((x - dx, s - start - dy, z),
                                       (x + dx, s - start + dy, z),
                                       (x + dx * 0.8, s - start + dy, z + size)))
                grass_faces.append((base, base + 1, base + 2))
    grass = make_mesh("expressway-grass-clumps", grass_vertices, grass_faces,
                      Vec4(0.30, 0.37, 0.078, 1))
    grass.setTwoSided(True)
    grass.reparentTo(root)
    for cs, cx, length in ((108, -39, 6), (212, -42, 8), (276, -39, 7),
                           (348, -46, 9), (477, -39, 6), (565, -43, 7),
                           (125, 55, 5), (540, 58, 6), (690, 56, 5)):
        if not start <= cs < start + 200:
            continue
        for n, (dx, ds, size) in enumerate(((0, 0, 1), (4, -6, .55), (3, 5, .7))):
            x, s = cx + dx, cs + ds
            rock = kit["strata-shelf"].copyTo(root)
            rock.setScale(size, length / 4 * size, size)
            rock.setPos(x, s - start, support_height(x, s) - .35 * size)
            rock.setH(20 + n * 37)
    # 桥面两端用土坡承接，桥梁不是空中横放的独立板。
    if index == 2:
        for side in (-1, 1):
            x1, x2 = sorted((side * 35, side * 75))
            outer1, outer2 = sorted((side * 23, side * 105))
            vertices = [(x1, 5, 7.1), (x2, 5, 7.1), (x2, 15, 7.1), (x1, 15, 7.1),
                        (outer1, -25, terrain_height(outer1, 375)),
                        (outer2, -25, terrain_height(outer2, 375)),
                        (outer2, 45, terrain_height(outer2, 445)),
                        (outer1, 45, terrain_height(outer1, 445))]
            make_mesh("bridge-approach", vertices,
                      [(0, 1, 2), (0, 2, 3), (4, 5, 1), (4, 1, 0),
                       (3, 2, 6), (3, 6, 7), (1, 5, 6), (1, 6, 2),
                       (4, 0, 3), (4, 3, 7)], Vec4(*GRASS)).reparentTo(root)


def build_vista(root):
    from scene import make_box, make_mesh

    # 只由第三段持有这组背景，卸载/重定位仍沿用segment根节点。
    for layer, (x, width, height, color) in enumerate((
        (-215, 145, 62, (0.10, 0.24, 0.23, 1)),
        (-370, 190, 98, (0.20, 0.33, 0.38, 1)),
        (275, 85, 27, (0.12, 0.29, 0.27, 1)),
        (470, 160, 63, (0.19, 0.32, 0.38, 1)),
        (720, 220, 112, (0.29, 0.40, 0.48, 1)),
    )):
        vertices, faces, colors = [], [], []
        for row, y in enumerate(range(-420, 841, 20)):
            ridge = height * (0.66 + 0.17 * math.sin(y * 0.013 + layer)
                              + 0.10 * math.sin(y * 0.037 + layer * 2)
                              + 0.035 * math.sin(y * 0.10))
            for col in range(9):
                u = col / 8
                profile = math.sin(u * math.pi) ** 1.35
                z = -4 + ridge * profile
                vertices.append((x - width + 2 * width * u, y, z))
                tint = 0.72 + 0.28 * profile + 0.07 * math.sin(y * 0.034 + col)
                colors.append(tuple(c * tint for c in color[:3]) + (1,))
        for row in range(63):
            for col in range(8):
                j = row * 9 + col
                faces.extend(((j, j + 1, j + 10), (j, j + 10, j + 9)))
        ridge = make_mesh("distant-ridge", vertices, faces, Vec4(*color))
        ridge.reparentTo(root)
        data = ridge.node().modifyGeom(0).modifyVertexData()
        writer = GeomVertexWriter(data, "color")
        normal_writer = GeomVertexWriter(data, "normal")
        # 平滑法线压住大三角明暗，层次来自多个真实山脊而非一面高墙。
        normals = [Vec3(0) for _ in vertices]
        for a, b, c in faces:
            normal = (Vec3(*vertices[b]) - Vec3(*vertices[a])).cross(
                Vec3(*vertices[c]) - Vec3(*vertices[a]))
            for i in (a, b, c):
                normals[i] += normal
        for face in faces:
            for i in face:
                writer.setData4f(*colors[i])
                normal_writer.setData3f(normals[i].normalized())
    for number, (x, s, width, height) in enumerate((
        (82, 990, 17, 29), (109, 1005, 16, 47), (135, 1030, 21, 34),
        (163, 1045, 15, 57), (190, 1065, 24, 27), (215, 1078, 18, 43),
        (245, 1095, 22, 34), (272, 1115, 14, 51), (305, 1132, 26, 24),
    )):
        node = make_box("bay-city", (width / 2, 11, height / 2),
                        Vec4(0.37 + number % 3 * 0.04, 0.48, 0.46, 1))
        node.setPos(x, s - 400, height / 2 - 1)
        node.reparentTo(root)
        cap = make_box("roofline", (width / 2 + 0.4, 11.4, 0.65), Vec4(0.51, 0.56, 0.51, 1))
        cap.setPos(x, s - 400, height - 0.4)
        cap.reparentTo(root)
        for floor in range(5, height - 2, 5):
            glazing = make_box("city-glazing-band", (width / 2 - 1.5, 0.035, 0.85),
                               Vec4(0.23, 0.37, 0.39, 1))
            glazing.setPos(x, s - 411.06, floor)
            # 远距离窗带接近立面，使用深度偏移避免透视精度不足时竞争深度。
            glazing.setDepthOffset(2)
            glazing.reparentTo(root)
    # 海湾保留低频水平线，轻量栈桥为城市提供共同岸线。
    add_strip(root, "bay-shore", 70, 330, -0.28, (0.52, 0.51, 0.39, 1), 570, 760)


def build_segment(root, index, seed, kit, stabilize_rail):
    from scene import make_box, make_mesh

    for name, (vertices, triangles) in surface_meshes().items():
        if name == "ground":
            continue
        rail = name.startswith("rail")
        color = (0.53, 0.59, 0.56, 1) if rail else (0.11, 0.13, 0.14, 1)
        node = make_mesh(f"expressway-{name}", vertices, triangles, Vec4(*color))
        node.reparentTo(root)
        if rail:
            stabilize_rail(node)
        else:
            node.setTexture(kit["aggregate"])
    # 三条同向车道采用白色分道虚线；左侧黄色实线只标道路边缘。
    for x in (-2.25, 2.25):
        for s in range(0, 200, 8):
            add_strip(root, "white-lane-dash", x - 0.07, x + 0.07, 0.027, WHITE, s, s + 4)
    for side in (-1, 1):
        x = side * 6.56
        add_strip(root, "edge-line", x - 0.075, x + 0.075, 0.030,
                  (0.88, 0.62, 0.13, 1) if side == -1 else WHITE)
        add_strip(root, "drain-channel", side * 7.68 - 0.18, side * 7.68 + 0.18,
                  0.012, (0.29, 0.31, 0.29, 1))
        for s in range(0, 200, 4):
            add_strip(root, "shoulder-rumble", side * 6.99 - 0.14, side * 6.99 + 0.14,
                      0.018, (0.24, 0.26, 0.24, 1), s, s + 0.25)
        for s in range(0, 200, 12):
            add_strip(root, "shoulder-joint", side * 7.2 - 0.38, side * 7.2 + 0.38,
                      0.020, (0.065, 0.077, 0.074, 1), s, s + 0.025)
    # 铺装色差直接写在道路唯一底面，避免毫米级重复大面竞争深度。
    build_terrain(root, index, kit)
    for model, x, y, z, heading in placements(index):
        node = kit[model].copyTo(root)
        node.setPos(x, y, z)
        node.setH(heading)
        if model == "kilometer":
            kilometer_face(node, index*SEGMENT_LENGTH+y, kit["kilometer-base"], kit["sign-digits"])
        if model in ("overpass", "gantry"):
            for side in (-1, 1):
                px = side * (11.8 if model == "overpass" else 9.5)
                footing = make_box("pier-footing", (0.85, 3.4 if model == "overpass" else 0.8, 0.3),
                                   Vec4(0.48, 0.51, 0.49, 1))
                footing.setPos(px, y, -0.16)
                footing.reparentTo(root)
    for number, (x, y, scale, heading) in enumerate(segment(seed, index).trees):
        tree = kit[f"tree-{(index + number) % 2}"].copyTo(root)
        tree.setPos(x, y, -0.32 + 0.05 * scale)
        tree.setScale(scale)
        tree.setH(heading)
    if index == 2:
        build_vista(root)
    root.setTag("visual-slice", "HWY-01")
    root.flattenStrong()
