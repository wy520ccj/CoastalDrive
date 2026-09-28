"""直线高速0–800m视觉样板；只消费既有segment，不拥有物理或流送状态。"""

import math
from itertools import pairwise

from panda3d.core import Filename, MaterialAttrib, Texture, Vec4

from highway_segments import SEGMENT_LENGTH, segment, surface_meshes
from paths import resource_root

START = 0
END = 800
KIT_NAMES = ("lamp", "reflector", "gantry", "advance-sign", "soundwall",
             "crash-cushion", "drain-grate", "kilometer", "equipment", "overpass",
             "broadleaf-crown", "shrub-bank")
GRASS = (0.25, 0.34, 0.13, 1)
ROCK = (0.49, 0.46, 0.34, 1)
SOIL = (0.36, 0.30, 0.18, 1)
WHITE = (0.88, 0.87, 0.75, 1)


def includes(index, curve):
    return curve is None and 0 <= index < END // SEGMENT_LENGTH


def load_kit(loader, parent, old_trees):
    """每个Scene加载一次；资源跟随已有Scene父节点释放。"""
    folder = resource_root() / "assets/game/expressway"
    kit = {}
    for name in KIT_NAMES:
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
        crown = kit["broadleaf-crown"].copyTo(tree)
        crown.setScale(0.58, 0.62, 0.65)
        crown_low, _ = crown.getTightBounds(tree)
        crown.setZ(trunk_top.z - 0.12 - crown_low.z)
        kit[f"tree-{variant}"] = tree
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
        return -0.32 + envelope * hill
    # 湾侧填方下放至海面；工程段的桥台与道路平顺相接。
    descent = smooth(36, 95, d) * 3.9
    return -0.32 - envelope * descent


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
    # 分层而非整块绿色平面；全局高度使相邻segment共享完全一致的边界。
    cross = (8.5, 11, 19, 20, 35, 44, 55, 72, 95, 120)
    for side in (-1, 1):
        for band, (a, b) in enumerate(pairwise(cross)):
            vertices, faces = [], []
            left, right = sorted((side * a, side * b))
            for local_s in range(0, 201, 10):
                for x in (left, right):
                    vertices.append((x, local_s, terrain_height(x, start + local_s)))
            for row in range(20):
                j = row * 2
                faces.extend(((j, j + 1, j + 3), (j, j + 3, j + 2)))
            cut = side < 0 and 35 <= a < 72 and index in (1, 2)
            color = ROCK if cut else SOIL if band == 0 or (side > 0 and band > 5) else GRASS
            node = make_mesh("cut-rock" if cut else "embankment", vertices, faces, Vec4(*color))
            node.setTexture(kit["aggregate"])
            node.reparentTo(root)
    # 连续灌木群布置在林带边缘，不在坡面上随机撒独立树。
    for center_s, center_x in ((65, -16), (135, 18), (195, -37), (260, -38),
                               (350, -37), (465, -38), (575, -37), (645, -17), (720, 20)):
        for n, (ds, dx) in enumerate(((-9, 2), (-4, -1), (0, 1), (5, -2), (10, 0))):
            s, x = center_s + ds, center_x + dx
            if start <= s < start + 200:
                bush = kit["shrub-bank"].copyTo(root)
                bush.setPos(x, s - start, terrain_height(x, s) - 0.25)
                bush.setScale(1.0 + n * 0.17, 1.8, 1.3)
                bush.setH(n * 37)
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
        (-215, 145, 62, (0.22, 0.35, 0.34, 1)),
        (-340, 210, 98, (0.33, 0.47, 0.48, 1)),
        (435, 135, 58, (0.39, 0.52, 0.53, 1)),
    )):
        vertices, faces = [], []
        for row, y in enumerate(range(-340, 601, 80)):
            ridge = height * (0.67 + 0.21 * math.sin(row * 1.75 + layer))
            vertices.extend(((x - width, y, -3), (x, y, ridge), (x + width, y, -3)))
        for row in range(11):
            for col in range(2):
                j = row * 3 + col
                faces.extend(((j, j + 1, j + 4), (j, j + 4, j + 3)))
        make_mesh("distant-ridge", vertices, faces, Vec4(*color)).reparentTo(root)
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
    for x in (-4.5, 0, 4.5):
        add_strip(root, "asphalt-laying-tone", x - 1.9, x + 1.9, 0.006,
                  (0.115, 0.133, 0.140, 1), texture=kit["aggregate"])
    build_terrain(root, index, kit)
    for model, x, y, z, heading in placements(index):
        node = kit[model].copyTo(root)
        node.setPos(x, y, z)
        node.setH(heading)
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
