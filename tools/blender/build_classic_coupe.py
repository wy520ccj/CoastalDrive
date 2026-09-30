"""在Blender中构造可编辑经典双门车网格并导出；运行游戏只读取GLB。"""

import json
import math
import struct
from itertools import pairwise
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/game/vehicles"
ART = ROOT / "art/vehicles"
for folder in (OUT, ART):
    folder.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1


def material(name, color, roughness, metallic=0, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    if emission:
        shader.inputs["Emission Color"].default_value = (*color, 1)
        shader.inputs["Emission Strength"].default_value = emission
    return mat


PAINT = material("Body Paint", (0.52, 0.0061, 0.0039), 0.32, 0)
GLASS = material("Blue Grey Glass", (0.004, 0.008, 0.012), 0.15, 0)
PLASTIC = material("Satin Black Plastic", (0.019, 0.025, 0.029), 0.65)
RUBBER = material("Tire Rubber", (0.008, 0.010, 0.012), 0.94)
METAL = material("Brushed Wheel Metal", (0.62, 0.65, 0.68), 0.16, 0.98)
DARK_METAL = material("Graphite Metal", (0.072, 0.085, 0.091), 0.44, 0.62)
IVORY = material("Whitewall Rubber", (0.48, 0.42, 0.32), 0.83)
REVERSE = material("Reversing Glass", (0.27, 0.32, 0.34), 0.25, 0.05)
RED = material("Tail Light", (0.24, 0.001, 0.002), 0.25, 0, 0.025)
WHITE = material("Head Light", (0.32, 0.38, 0.39), 0.18, 0.3, 0)
AMBER = material("Amber Lens", (0.95, 0.26, 0.018), 0.24, 0, 0.25)


def empty(name, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    return obj


root = empty("classic-coupe-v1")
paint = empty("paint", root)


def mesh(name, vertices, faces, mat, parent=root, smooth=False, bevel=0):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(data)
    bm.free()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    data.materials.append(mat)
    for poly in data.polygons:
        poly.use_smooth = smooth
    if bevel:
        bpy.context.view_layer.objects.active = obj
        modifier = obj.modifiers.new("Small panel edge radii", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        normal = obj.modifiers.new("Panel normals", "WEIGHTED_NORMAL")
        bpy.ops.object.modifier_apply(modifier=normal.name)
    return obj


def panel(name, points, mat, parent=root, depth=0):
    # 挤出薄面板用于灯罩、格栅和钣金附件，尺寸由设计控制点定义。
    if not depth:
        return mesh(name, points, [tuple(range(len(points)))], mat, parent)
    normal = (
        (Vector(points[1]) - Vector(points[0]))
        .cross(Vector(points[2]) - Vector(points[0]))
        .normalized()
    )
    vertices = list(points) + [tuple(Vector(p) - normal * depth) for p in points]
    n = len(points)
    faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    faces.extend((i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n))
    return mesh(name, vertices, faces, mat, parent, bevel=min(0.007, depth / 3))


def line(name, points, mat, radius=0.006, parent=root):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 8
    curve.bevel_depth = radius
    curve.bevel_resolution = 0
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for target, p in zip(spline.points, points):
        target.co = (*p, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    return obj


def interpolate(points, y):
    for (a, v), (b, w) in pairwise(points):
        if a <= y <= b:
            return v + (w - v) * (y - a) / (b - a)
    raise ValueError(y)


def profile(points, y):
    """纵向控制点之间平滑过渡，防止翼子板高光出现折线。"""
    for i, ((a, v), (b, w)) in enumerate(pairwise(points)):
        if a <= y <= b:
            t = (y - a) / (b - a)
            prev = points[max(0, i - 1)]
            after = points[min(len(points) - 1, i + 2)]
            m0 = (w - prev[1]) / (b - prev[0])
            m1 = (after[1] - v) / (after[0] - a)
            return (
                (2 * t**3 - 3 * t**2 + 1) * v
                + (t**3 - 2 * t**2 + t) * (b - a) * m0
                + (-2 * t**3 + 3 * t**2) * w
                + (t**3 - t**2) * (b - a) * m1
            )
    raise ValueError(y)


# 经典美式双门比例：平直机盖、后移座舱、饱满翼子板和短尾厢。
widths = [
    (-2.095, 0.83),
    (-1.8, 0.91),
    (-1.10, 0.956),
    (-0.35, 0.918),
    (0.40, 0.914),
    (1.10, 0.954),
    (1.70, 0.928),
    (2.075, 0.867),
]
heights = [
    (-2.095, 0.43),
    (-1.70, 0.51),
    (-1.10, 0.51),
    (-0.35, 0.49),
    (0.40, 0.495),
    (1.10, 0.49),
    (1.70, 0.49),
    (2.075, 0.445),
]
ys = sorted(
    set(
        [-2.095 + i * (4.17 / 80) for i in range(81)]
        + [y for y, _ in widths]
        + [h + 0.402 * math.cos(math.pi * i / 20) for h in (-1.1, 1.1) for i in range(21)]
    )
)
verts = []
for y in ys:
    w, h = profile(widths, y), profile(heights, y)
    base_low = profile(
        [
            (-2.095, -0.20),
            (-1.78, -0.235),
            (-0.6, -0.265),
            (0.6, -0.265),
            (1.75, -0.215),
            (2.075, -0.19),
        ],
        y,
    )
    low = base_low
    for hub in (-1.1, 1.1):
        if abs(y - hub) <= 0.402:
            low = max(low, -0.12 + math.sqrt(max(0, 0.402**2 - (y - hub) ** 2)))
    half = [
        (0, h + 0.012),
        (0.52 * w, h + 0.005),
        (0.76 * w, h + 0.018),
        (0.89 * w, h),
        (0.973 * w, h - 0.055),
        (w, h - 0.115),
        (0.995 * w, max(low + 0.050, 0.16)),
        (0.979 * w, low + 0.022),
        (0.91 * w, low),
        (0.72 * w, low - 0.01),
        (0.69 * w, base_low - 0.01),
        (0, base_low - 0.01),
    ]
    ring = half + [(-x, z) for x, z in reversed(half[1:-1])]
    verts.extend((x, y, z) for x, z in ring)
count = len(ring)
faces = [tuple(reversed(range(count)))]
for i in range(len(ys) - 1):
    faces.extend(
        (
            i * count + j,
            i * count + (j + 1) % count,
            (i + 1) * count + (j + 1) % count,
            (i + 1) * count + j,
        )
        for j in range(count)
    )
faces.append(tuple((len(ys) - 1) * count + j for j in range(count)))
mesh("Continuous flanks and wheel arches", verts, faces, PAINT, paint, True)

# 深色轮罩遮蔽车身内腔，轮胎与轮拱之间保留实际悬架活动空间。
for side in (-1, 1):
    for hub in (-1.1, 1.1):
        arc = [
            (hub + 0.384 * math.cos(math.pi * i / 24), -0.12 + 0.384 * math.sin(math.pi * i / 24))
            for i in range(25)
        ]
        vertices = [(side * x, y, z) for x in (0.66, 0.919) for y, z in arc]
        faces = [(i, i + 1, 25 + i + 1, 25 + i) for i in range(24)]
        mesh("Recessed wheelhouse roof", vertices, faces, PLASTIC, smooth=True)
        panel(
            "Wheelhouse inner wall",
            [(side * 0.66, y, z) for y, z in arc]
            + [(side * 0.66, hub - 0.384, -0.29), (side * 0.66, hub + 0.384, -0.29)],
            PLASTIC,
        )

# 车顶和玻璃共用同一张参数曲面；细窗框顺着玻璃边缘闭合。
cab = [
    (-1.38, 0.52, 0.78, 0.80),
    (-0.91, 0.95, 0.653, 0.825),
    (-0.72, 1.01, 0.627, 0.828),
    (-0.03, 1.015, 0.624, 0.832),
    (0.15, 0.965, 0.646, 0.831),
    (0.65, 0.51, 0.79, 0.824),
]
stations = sorted(set([c[0] for c in cab] + [-1.38 + i * 2.03 / 56 for i in range(57)]))


def cabin_point(y, u, side=0, offset=0):
    top = profile([(c[0], c[1]) for c in cab], y)
    r = profile([(c[0], c[2]) for c in cab], y)
    b = profile([(c[0], c[3]) for c in cab], y)
    if side:
        return side * (b + (r - b) * u + offset), y, 0.49 + (top - 0.036 - 0.49) * u
    return r * u, y, top - 0.036 * abs(u) ** 2 + offset


verts = []
for y in stations:
    verts.extend(
        [cabin_point(y, 0, -1), cabin_point(y, 1, -1)]
        + [cabin_point(y, -1 + 2 * i / 12) for i in range(1, 12)]
        + [cabin_point(y, 1, 1), cabin_point(y, 0, 1)]
    )
count = 15
faces = [tuple(reversed(range(count)))]
for j in range(len(stations) - 1):
    faces.extend(
        (j * count + i, j * count + i + 1, (j + 1) * count + i + 1, (j + 1) * count + i)
        for i in range(count - 1)
    )
faces.append(tuple((len(stations) - 1) * count + i for i in range(count)))
mesh("Rounded hardtop cabin", verts, faces, PAINT, paint, True)


def window(name, polygon, side=0):
    # 先细分参数平面，再投影到舱体，避免大三角形弦面切进曲面。
    points = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        points.extend(
            (a[0] + (b[0] - a[0]) * i / 4, a[1] + (b[1] - a[1]) * i / 4) for i in range(4)
        )
    bm = bmesh.new()
    boundary = [bm.verts.new((y, u, 0)) for y, u in polygon]
    bm.faces.new(boundary)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=7, use_grid_fill=True)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    vertices = [cabin_point(v.co.x, v.co.y, side, 0.014) for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    if side < 0:
        faces = [tuple(reversed(f)) for f in faces]
    mesh(name, vertices, faces, GLASS, smooth=True)
    seal = [cabin_point(y, u, side, 0.012) for y, u in points]
    line(name + " rubber seal", seal + [seal[0]], PLASTIC, 0.014)
    chrome = [cabin_point(y, u, side, 0.02) for y, u in points]
    line(name + " polished surround", chrome + [chrome[0]], METAL, 0.008)


window("Windshield", [(0.20, -0.90), (0.20, 0.90), (0.592, 0.95), (0.592, -0.95)])
window("Rear window", [(-1.315, -0.94), (-1.315, 0.94), (-0.949, 0.89), (-0.949, -0.89)])
for side in (-1, 1):
    window("Door glass", [(-0.41, 0.12), (0.552, 0.16), (0.129, 0.89), (-0.41, 0.89)], side)
    window(
        "Rear quarter glass", [(-1.235, 0.12), (-0.478, 0.12), (-0.478, 0.89), (-0.884, 0.88)], side
    )
    line(
        "Vent window divider",
        [cabin_point(y, u, side, 0.025) for y, u in ((0.26, 0.13), (0.119, 0.88))],
        METAL,
        0.009,
    )
    line("Roof rain gutter", [cabin_point(y, 1, side, 0.019) for y in stations[3:-3]], METAL, 0.006)
    # 两扇门与侧后方凹入式装饰，顺车身表面建立门缝和镀铬腰线。
    door = [(-0.47, 0.425), (-0.49, -0.15), (0.39, -0.15), (0.44, 0.425)]

    def flank(y, z):
        w, h = profile(widths, y), profile(heights, y)
        cross = [
            (-0.265, 0.91 * w),
            (-0.243, 0.979 * w),
            (0.16, 0.995 * w),
            (h - 0.115, w),
            (h - 0.055, 0.973 * w),
            (h, 0.89 * w),
        ]
        return interpolate(cross, z) + 0.004

    door_points = []
    for a, b in pairwise(door):
        for i in range(14):
            y, z = a[0] + (b[0] - a[0]) * i / 13, a[1] + (b[1] - a[1]) * i / 13
            door_points.append((side * flank(y, z), y, z))
    line("Door panel gap", door_points, PLASTIC, 0.0025)
    sill = []
    for y in (-0.66, -0.5, 0, 0.5, 0.66):
        sill.append((side * profile(widths, y) * 0.98, y, -0.225))
    line("Polished rocker trim", sill, METAL, 0.012)
    line(
        "Body shoulder pinstripe",
        [(side * (profile(widths, y) * 0.981), y, profile(heights, y) - 0.083) for y in ys[5:-5]],
        METAL,
        0.0035,
    )
    # 回缩门把手与锁芯。
    line(
        "Door handle recess",
        [(side * 0.923, -0.36, 0.321), (side * 0.923, -0.15, 0.321)],
        PLASTIC,
        0.005,
    )
    line(
        "Door chrome handle",
        [
            (side * 0.924, -0.355, 0.331),
            (side * 0.938, -0.326, 0.336),
            (side * 0.938, -0.185, 0.336),
            (side * 0.924, -0.155, 0.331),
        ],
        METAL,
        0.005,
    )
    # C形侧面装饰，作为经典轿跑特征；附着于平直后侧板。
    vent_yz = [(-0.55, 0.285), (-0.655, 0.27), (-0.653, 0.105), (-0.55, 0.09)]
    vent = [(side * flank(y, z), y, z) for y, z in vent_yz]
    panel("Shallow side scallop", vent, DARK_METAL, depth=0.002)
    line("Side scallop C trim", vent, METAL, 0.004)
    # 小圆镜，镜臂附着门前缘；整体仍位于既有碰撞宽度内。
    line("Mirror pedestal", [(side * flank(0.47, 0.44), 0.47, 0.44), (side * 0.952, 0.44, 0.54)], METAL, 0.009)


def lathe(name, profile_points, mat, parent=root, sides=32):
    verts = [
        (x, math.sin(i * math.tau / sides) * r, math.cos(i * math.tau / sides) * r)
        for x, r in profile_points
        for i in range(sides)
    ]
    faces = [
        (
            j * sides + i,
            j * sides + (i + 1) % sides,
            (j + 1) * sides + (i + 1) % sides,
            (j + 1) * sides + i,
        )
        for j in range(len(profile_points) - 1)
        for i in range(sides)
    ]
    return mesh(name, verts, faces, mat, parent, True)


for side in (-1, 1):
    mirror = empty("Round door mirror", root)
    mirror.location = (side * 0.955, 0.435, 0.561)
    mirror.rotation_euler.z = math.pi / 2
    lathe(
        "Polished mirror capsule",
        [(-0.010, 0), (-0.010, 0.035), (0, 0.039), (0.013, 0.036), (0.015, 0)],
        METAL,
        mirror,
        24,
    )
    lathe("Mirror face", [(-0.012, 0), (-0.012, 0.031)], GLASS, mirror, 24)

# 格栅、灯组与钣金端面一体组织，横向镀铬线条形成经典前脸。
grille = [
    (-0.56, 2.081, 0.155),
    (0.56, 2.081, 0.155),
    (0.625, 2.081, 0.397),
    (-0.625, 2.081, 0.397),
]
panel("Deep grille recess", grille, PLASTIC, depth=0.012)
line("Grille polished frame", grille + [grille[0]], METAL, 0.014)
for z in (0.194, 0.237, 0.280, 0.323, 0.367):
    line("Grille horizontal ribs", [(-0.54, 2.101, z), (0.54, 2.101, z)], DARK_METAL, 0.004)
line("Grille centre trim", [(-0.545, 2.109, 0.277), (0.545, 2.109, 0.277)], METAL, 0.006)
for side in (-1, 1):
    headlamp = empty("Round headlamp", root)
    headlamp.location = (side * 0.747, 2.077, 0.303)
    headlamp.rotation_euler.z = math.pi / 2
    headlamp.scale = (0.78, 0.78, 0.78)
    lathe(
        "Headlamp dark socket",
        [(-0.022, 0.117), (-0.010, 0.148), (0.009, 0.148), (0.016, 0.126)],
        PLASTIC,
        headlamp,
        40,
    )
    lathe(
        "Headlamp rolled chrome rim",
        [(0.010, 0.122), (0.021, 0.132), (0.014, 0.144), (0.001, 0.144)],
        METAL,
        headlamp,
        40,
    )
    lathe(
        "Headlamp convex lens",
        [(0.015, 0.119), (0.027, 0.101), (0.034, 0.070), (0.039, 0)],
        WHITE,
        headlamp,
        32,
    )
    for yoff in (-0.068, -0.034, 0, 0.034, 0.068):
        height = math.sqrt(0.107**2 - yoff**2)
        line(
            "Lens vertical fluting",
            [(0.038, yoff, -height), (0.038, yoff, height)],
            METAL,
            0.0012,
            headlamp,
        )
    marker = empty("Lower running lamp", root)
    marker.location = (side * 0.61, 2.087, -0.111)
    marker.rotation_euler.z = math.pi / 2
    lathe(
        "Running lamp chrome ring",
        [(0, 0.046), (0.018, 0.048), (0.018, 0.035), (0, 0.035)],
        METAL,
        marker,
        24,
    )
    lathe("Running lamp lens", [(0.014, 0.034), (0.021, 0)], AMBER, marker, 20)

# 保险杠沿车身转角回收；椭圆截面保持闭合，不再使用会露出尖角的开放折板。
for end in (-1, 1):
    width = 0.885 if end < 0 else 0.905
    half = [(0, 2.112), (0.45, 2.112), (0.70, 2.11)]
    half += [
        (0.70 + (width - 0.70) * math.sin(t), 2.11 - 0.12 * (1 - math.cos(t)))
        for t in [math.pi * i / 24 for i in range(1, 13)]
    ]
    path = [(-x, end * y) for x, y in reversed(half[1:])] + [(x, end * y) for x, y in half]
    vertices = []
    for i, (x, y) in enumerate(path):
        prev = Vector(path[max(0, i - 1)])
        nxt = Vector(path[min(len(path) - 1, i + 1)])
        tangent = (nxt - prev).normalized()
        normal = Vector((-tangent.y, tangent.x))
        for j in range(8):
            a = math.tau * j / 8
            vertices.append(
                (
                    x + normal.x * 0.016 * math.cos(a),
                    y + normal.y * 0.016 * math.cos(a),
                    0.018 + 0.033 * math.sin(a),
                )
            )
    faces = [tuple(reversed(range(8)))]
    faces += [
        (i * 8 + j, i * 8 + (j + 1) % 8, (i + 1) * 8 + (j + 1) % 8, (i + 1) * 8 + j)
        for i in range(len(path) - 1)
        for j in range(8)
    ]
    faces.append(tuple((len(path) - 1) * 8 + j for j in range(8)))
    mesh("Body fitted rounded chrome bumper", vertices, faces, METAL, smooth=True)

# 尾灯缩入翼子板端面。三枚灯片各自镶窄边框，取消大块黑框和悬空装饰杆。
for side in (-1, 1):
    border = [
        (side * 0.405, -2.098, 0.19),
        (side * 0.735, -2.098, 0.19),
        (side * 0.735, -2.098, 0.344),
        (side * 0.405, -2.098, 0.344),
    ]
    panel("Inset rear lamp recess", border, DARK_METAL, depth=0.004)
    for x in (0.458, 0.57, 0.682):
        lens = [
            (side * (x - 0.032), -2.105, 0.203),
            (side * (x + 0.032), -2.105, 0.203),
            (side * (x + 0.032), -2.105, 0.332),
            (side * (x - 0.032), -2.105, 0.332),
        ]
        panel("Vertical red tail lens", lens, RED, depth=0.006)
        line("Tail lens narrow surround", lens + [lens[0]], METAL, 0.003)
    reverse = empty("Recessed reversing lamp", root)
    reverse.location = (side * 0.535, -2.096, -0.104)
    reverse.rotation_euler.z = -math.pi / 2
    lathe(
        "Reversing socket",
        [(0, 0.027), (0.004, 0.03), (0.006, 0.024), (0, 0.024)],
        DARK_METAL,
        reverse,
        24,
    )
    lathe("Reversing glass", [(0.005, 0.023), (0.007, 0)], REVERSE, reverse, 24)
plate = [
    (-0.21, -2.101, 0.096),
    (0.21, -2.101, 0.096),
    (0.21, -2.101, 0.222),
    (-0.21, -2.101, 0.222),
]
panel("Inset rear number plate", plate, PLASTIC, depth=0.004)
line("Plate narrow surround", plate + [plate[0]], METAL, 0.0025)
for side in (-1, 1):
    line(
        "Hood panel gap",
        [
            (side * 0.595, y, profile(heights, y) + 0.02)
            for y in (0.70, 0.85, 1.0, 1.2, 1.4, 1.6, 1.8, 1.96)
        ],
        PLASTIC,
        0.0025,
    )
    line(
        "Boot shut line",
        [(side * 0.67, y, profile(heights, y) + 0.019) for y in (-1.43, -1.55, -1.7, -1.84, -1.97)],
        PLASTIC,
        0.0025,
    )
    line(
        "Windshield wiper",
        [
            cabin_point(y, u, 0, 0.028)
            for y, u in ((0.574, side * 0.82), (0.566, side * 0.5), (0.558, side * 0.13))
        ],
        PLASTIC,
        0.004,
    )

# 自有小型字标，避免把参考图品牌变成项目车型身份。
for text, loc, size, rot in (("COASTAL", (-0.16, -2.100, 0.341), 0.043, (math.pi / 2, 0, 0)),):
    curve = bpy.data.curves.new("Coastal script", "FONT")
    curve.body = text
    curve.size = size
    curve.extrude = 0.001
    curve.space_character = 1.16
    obj = bpy.data.objects.new("Coastal marque", curve)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rot
    obj.parent = root
    obj.data.materials.append(METAL)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")

# 米制圆肩窄胎和实心镀铬轮盖；径向尺寸不改，满舵宽度收在既有外廓内。
tire = [
    (-0.095, 0.198),
    (-0.096, 0.236),
    (-0.088, 0.266),
    (-0.061, 0.305),
    (-0.033, 0.33),
    (0.033, 0.33),
    (0.061, 0.305),
    (0.088, 0.266),
    (0.096, 0.236),
    (0.095, 0.198),
    (-0.095, 0.198),
]
for axle, y in (("front", 1.1), ("back", -1.1)):
    for name, side in (("left", -1), ("right", 1)):
        wheel = empty(f"wheel-{axle}-{name}", root)
        wheel.location = (side * 0.84, y, -0.12)
        lathe("Classic rounded rubber tire", tire, RUBBER, wheel, 32)
        for sign in (-1, 1):
            lathe(
                "Whitewall narrow band",
                [(sign * 0.096, 0.238), (sign * 0.096, 0.247), (sign * 0.091, 0.261)],
                IVORY,
                wheel,
                32,
            )
            lathe(
                "Wheel steel dish",
                [
                    (sign * 0.07, 0),
                    (sign * 0.07, 0.182),
                    (sign * 0.09, 0.205),
                    (sign * 0.102, 0.215),
                    (sign * 0.102, 0.228),
                ],
                DARK_METAL,
                wheel,
                32,
            )
            lathe(
                "Polished wheel trim",
                [
                    (sign * 0.10, 0.213),
                    (sign * 0.112, 0.219),
                    (sign * 0.108, 0.231),
                    (sign * 0.098, 0.234),
                ],
                METAL,
                wheel,
                32,
            )
            lathe(
                "Domed chrome hubcap",
                [
                    (sign * 0.075, 0.181),
                    (sign * 0.094, 0.167),
                    (sign * 0.112, 0.124),
                    (sign * 0.118, 0.045),
                    (sign * 0.119, 0),
                ],
                METAL,
                wheel,
                32,
            )
            lathe(
                "Hubcap fine concentric ring",
                [(sign * 0.099, 0.15), (sign * 0.103, 0.153), (sign * 0.102, 0.157)],
                DARK_METAL,
                wheel,
                32,
            )
            for slot in range(20):
                a = slot * math.tau / 20
                points = [
                    (sign * 0.106, math.sin(a + da) * r, math.cos(a + da) * r)
                    for da, r in ((-0.040, 0.184), (0.040, 0.184), (0.040, 0.207), (-0.040, 0.207))
                ]
                panel("Wheel cooling slot", points, PLASTIC, wheel)
        for j in range(20):
            a = j * math.tau / 20
            line(
                "Tire tread",
                [
                    (-0.032, math.sin(a) * 0.331, math.cos(a) * 0.331),
                    (0.032, math.sin(a + 0.04) * 0.331, math.cos(a + 0.04) * 0.331),
                ],
                PLASTIC,
                0.001,
                wheel,
            )
panel(
    "Simple chassis undertray",
    [(-0.65, -1.85, -0.32), (0.65, -1.85, -0.32), (0.65, 1.85, -0.32), (-0.65, 1.85, -0.32)],
    PLASTIC,
)
exhaust = empty("Tucked tail pipe", root)
exhaust.location = (-0.56, -2.025, -0.205)
exhaust.rotation_euler.z = math.pi / 2
lathe(
    "Tail pipe rolled lip",
    [(-0.08, 0.018), (-0.08, 0.023), (0.10, 0.023), (0.10, 0.018), (-0.08, 0.018)],
    DARK_METAL,
    exhaust,
    24,
)
lathe("Tail pipe dark opening", [(-0.079, 0), (-0.079, 0.018)], PLASTIC, exhaust, 24)

# 保存部件可独立编辑的源文件，再合并运行网格以控制提交批次。
bpy.ops.object.select_all(action="DESELECT")
root.select_set(True)
bpy.context.view_layer.objects.active = root
bpy.context.scene.world.color = (0.15, 0.19, 0.24)
bpy.ops.wm.save_as_mainfile(filepath=str(ART / "classic_coupe_v1.blend"))
groups = {}
for obj in list(bpy.data.objects):
    if obj.type != "MESH":
        continue
    ancestor = obj.parent
    while ancestor != root and not ancestor.name.startswith("wheel-"):
        ancestor = ancestor.parent
    target = ancestor if ancestor != root else paint if obj.data.materials[0] == PAINT else root
    groups.setdefault((target, obj.data.materials[0]), []).append(obj)
for (target, mat), objects in groups.items():
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    transform = obj.matrix_world.copy()
    obj.parent = target
    obj.matrix_world = transform
    obj.name = mat.name + " surfaces"
path = OUT / "classic_coupe_v1.glb"
bpy.ops.export_scene.gltf(
    filepath=str(path), export_format="GLB", export_yup=True, export_apply=True
)
data = path.read_bytes()
length = struct.unpack_from("<I", data, 12)[0]
gltf = json.loads(data[20 : 20 + length])
triangles = sum(
    gltf["accessors"][p["indices"]]["count"] // 3 for m in gltf["meshes"] for p in m["primitives"]
)
manifest = {
    "asset": "classic_coupe_v1",
    "source": "original CoastalDrive Blender geometry; user supplied classic American coupe photo is design reference only",
    "units": "metres; Blender and Panda3D Z-up, +Y forward",
    "blender": bpy.app.version_string,
    "triangles": triangles,
    "triangle_budget": 32000,
    "wheel_radius_m": 0.33,
    "wheel_centres_body_m": [
        [-0.84, 1.1, -0.12],
        [0.84, 1.1, -0.12],
        [-0.84, -1.1, -0.12],
        [0.84, -1.1, -0.12],
    ],
    "materials": [m.name for m in bpy.data.materials],
    "editable_source": "art/vehicles/classic_coupe_v1.blend",
}
(OUT / "classic-coupe-manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print("CLASSIC_COUPE_EXPORTED", triangles)
