"""车辆展示模型、车身细节与物理轮心的显示装配。"""

from itertools import pairwise

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Material,
    Vec3,
    Vec4,
)

from vehicle_config import WHEEL_HUBS

WHEEL_NAMES = ("wheel-front-left", "wheel-front-right", "wheel-back-left", "wheel-back-right")


def _box(parent, name, center, size, color, roughness=0.42, metallic=0.0, emission=None):
    """建一个带平面法线的小型显示部件。尺寸用原车身的本地坐标。"""
    cx, cy, cz = center
    sx, sy, sz = (value / 2 for value in size)
    corners = (
        (cx - sx, cy - sy, cz - sz),
        (cx + sx, cy - sy, cz - sz),
        (cx + sx, cy + sy, cz - sz),
        (cx - sx, cy + sy, cz - sz),
        (cx - sx, cy - sy, cz + sz),
        (cx + sx, cy - sy, cz + sz),
        (cx + sx, cy + sy, cz + sz),
        (cx - sx, cy + sy, cz + sz),
    )
    faces = (
        ((0, 3, 2, 1), (0, 0, -1)),
        ((4, 5, 6, 7), (0, 0, 1)),
        ((0, 1, 5, 4), (0, -1, 0)),
        ((1, 2, 6, 5), (1, 0, 0)),
        ((2, 3, 7, 6), (0, 1, 0)),
        ((3, 0, 4, 7), (-1, 0, 0)),
    )
    data = GeomVertexData(name, GeomVertexFormat.getV3n3(), Geom.UHStatic)
    vertex = GeomVertexWriter(data, "vertex")
    normal = GeomVertexWriter(data, "normal")
    triangles = GeomTriangles(Geom.UHStatic)
    for indices, direction in faces:
        first = data.getNumRows()
        for index in indices:
            vertex.addData3f(*corners[index])
            normal.addData3f(*direction)
        triangles.addVertices(first, first + 1, first + 2)
        triangles.addVertices(first, first + 2, first + 3)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    part = parent.attachNewNode(node)
    material = Material()
    material.setName(name)
    material.setBaseColor(Vec4(*color, 1))
    material.setRoughness(roughness)
    material.setMetallic(metallic)
    if emission is not None:
        material.setEmission(Vec4(*emission, 1))
    part.setMaterial(material, 1)
    return part


def decorate_vehicle(model_id, model):
    """给原有车身加灯、格栅和车身分缝，不改变车体尺寸或轮胎节点。"""
    bounds = model.find("**/body").getTightBounds()
    if bounds is None:
        return
    low, high = bounds
    half_width = max(abs(low.x), abs(high.x))
    front_y = low.y + 0.035
    rear_y = high.y - 0.035
    body_z = high.z
    dark = (0.025, 0.045, 0.06)
    chrome = (0.48, 0.58, 0.62)
    glass = (0.035, 0.16, 0.24)

    # 前脸与灯组按本体宽度定位，窄车和宽车共用相同做法。
    _box(model, "front-grille", (0, front_y + 0.03, 0.37), (half_width * 0.62, 0.035, 0.15), dark)
    _box(
        model,
        "front-splitter",
        (0, front_y + 0.055, 0.27),
        (half_width * 1.45, 0.055, 0.035),
        dark,
        0.3,
        0.45,
    )
    for side in (-1, 1):
        _box(
            model,
            "headlamp",
            (side * half_width * 0.67, front_y + 0.018, 0.55),
            (half_width * 0.43, 0.028, 0.105),
            (0.88, 0.78, 0.54),
            0.2,
            0.05,
            (0.18, 0.13, 0.055),
        )
        _box(
            model,
            "front-indicator",
            (side * half_width * 0.87, front_y + 0.02, 0.46),
            (0.055, 0.03, 0.05),
            (0.95, 0.28, 0.025),
            0.22,
            0.0,
            (0.12, 0.025, 0.0),
        )
        _box(
            model,
            "tail-lamp",
            (side * half_width * 0.70, rear_y - 0.018, 0.50),
            (half_width * 0.40, 0.035, 0.115),
            (0.70, 0.035, 0.028),
            0.24,
            0.0,
            (0.10, 0.004, 0.002),
        )
        _box(
            model,
            "mirror",
            (side * (half_width - 0.055), -0.31, body_z * 0.69),
            (0.10, 0.17, 0.07),
            glass,
            0.2,
            0.35,
        )
        _box(
            model,
            "door-handle",
            (side * (half_width - 0.02), 0.24, body_z * 0.54),
            (0.026, 0.12, 0.026),
            chrome,
            0.28,
            0.65,
        )
        _box(
            model,
            "door-seam",
            (side * (half_width - 0.012), 0.33, body_z * 0.56),
            (0.018, 0.012, body_z * 0.43),
            (0.07, 0.055, 0.045),
            0.8,
        )

    plate_width = min(0.34, half_width * 0.42)
    for y, direction in ((front_y + 0.038, -1), (rear_y - 0.038, 1)):
        _box(
            model,
            "license-plate",
            (0, y, 0.35),
            (plate_width, 0.018, 0.065),
            (0.72, 0.80, 0.78),
            0.65,
        )
        _box(
            model,
            "bumper-trim",
            (0, y + direction * 0.012, 0.30),
            (half_width * 1.40, 0.035, 0.035),
            chrome,
            0.3,
            0.55,
        )

    # 运动轿跑带有短尾翼；轿车则有一条后备厢饰条。
    if model_id == "sedan":
        _box(
            model,
            "sedan-trunk-trim",
            (0, rear_y - 0.16, body_z * 0.70),
            (half_width * 1.2, 0.035, 0.025),
            chrome,
            0.3,
            0.5,
        )
    return model


def _surface(parent, name, vertices, faces, color, roughness=0.4, metallic=0.0):
    data = GeomVertexData(name, GeomVertexFormat.getV3n3(), Geom.UHStatic)
    writer, normals = GeomVertexWriter(data, "vertex"), GeomVertexWriter(data, "normal")
    tris = GeomTriangles(Geom.UHStatic)
    for face in faces:
        points = [Vec3(*vertices[i]) for i in face]
        normal = (points[1] - points[0]).cross(points[2] - points[0])
        normal.normalize()
        start = data.getNumRows()
        for point in points:
            writer.addData3f(point)
            normals.addData3f(normal)
        for i in range(1, len(points) - 1):
            tris.addVertices(start, start + i, start + i + 1)
    geom = Geom(data)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    result = parent.attachNewNode(node)
    mat = Material(name)
    mat.setBaseColor(Vec4(*color, 1))
    mat.setRoughness(roughness)
    mat.setMetallic(metallic)
    result.setMaterial(mat, 1)
    result.setTwoSided(True)
    return result


def _ring(parent, name, x1, x2, outer, inner, color, metallic=0.0):
    import math

    vertices = []
    for x, radius in ((x1, outer), (x2, outer), (x2, inner), (x1, inner)):
        vertices.extend(
            (x, math.sin(i * math.tau / 32) * radius, math.cos(i * math.tau / 32) * radius)
            for i in range(32)
        )
    faces = []
    for row in range(4):
        for i in range(32):
            j = (i + 1) % 32
            faces.append(
                (row * 32 + i, row * 32 + j, ((row + 1) % 4) * 32 + j, ((row + 1) % 4) * 32 + i)
            )
    return _surface(parent, name, vertices, faces, color, 0.68 if not metallic else 0.24, metallic)


def load_vehicle(parent, model_id):
    """按真实轮心建楔形轿跑与三厢车；车漆与机械部件独立。"""
    import math

    root = parent.attachNewNode(model_id)
    body = root.attachNewNode("body")
    paint = (0.95, 0.20, 0.025)
    dark = (0.018, 0.025, 0.031)
    silver = (0.55, 0.60, 0.64)
    glass = (0.025, 0.085, 0.12)
    sedan = model_id == "sedan"
    # 连续钣金截面与真实轮拱，避免把车体堆成盒子。
    ys = sorted(
        set(
            [-2.10, -1.85, -0.5, 0.0, 0.5, 1.85, 2.10]
            + [hub + i * 0.04 for hub in (-1.1, 1.1) for i in range(-10, 11)]
        )
    )

    def section(y):
        width = 0.88 - max(abs(y) - 1.75, 0) * 0.22
        top = 0.38 if sedan else 0.32
        top -= max(y - 0.7, 0) * 0.055
        bottom = -0.29
        for hub in (-1.1, 1.1):
            d = abs(y - hub)
            if d < 0.40:
                bottom = max(bottom, -0.12 + math.sqrt(0.40**2 - d**2))
        return width, top, bottom

    for a, b in pairwise(ys):
        wa, za, ba = section(a)
        wb, zb, bb = section(b)
        vertices = [
            (-wa + 0.07, a, za),
            (wa - 0.07, a, za),
            (-wb + 0.07, b, zb),
            (wb - 0.07, b, zb),
            (-wa, a, ba),
            (wa, a, ba),
            (-wb, b, bb),
            (wb, b, bb),
        ]
        _surface(
            body, "paint", vertices, [(0, 1, 3, 2), (4, 0, 2, 6), (1, 5, 7, 3)], paint, 0.26, 0.22
        )
    for y in (-2.1, 2.1):
        w, z, _ = section(y)
        _surface(
            body,
            "paint",
            [(-w, y, -0.29), (w, y, -0.29), (w, y, z), (-w, y, z)],
            [(0, 1, 2, 3)],
            paint,
            0.26,
            0.22,
        )
    # 低矮车顶、倾斜风挡和分开的三角后窗。
    front, rear, roof_front, roof_rear, roof_z = (
        (0.7, -1.35, 0.22, -0.55, 0.78) if not sedan else (0.78, -1.1, 0.32, -0.58, 0.93)
    )
    verts = [
        (-0.79, front, 0.32),
        (0.79, front, 0.32),
        (-0.79, rear, 0.35),
        (0.79, rear, 0.35),
        (-0.63, roof_front, roof_z),
        (0.63, roof_front, roof_z),
        (-0.63, roof_rear, roof_z),
        (0.63, roof_rear, roof_z),
    ]
    _surface(body, "paint", verts, [(4, 5, 7, 6), (0, 4, 6, 2), (5, 1, 3, 7)], paint, 0.26, 0.22)
    for ids in ((0, 1, 5, 4), (2, 6, 7, 3)):
        center = sum((Vec3(*verts[i]) for i in ids), Vec3()) / 4
        inset = [tuple(center + (Vec3(*verts[i]) - center) * 0.91) for i in ids]
        _surface(body, "windscreen", inset, [(0, 1, 2, 3)], glass, 0.16, 0.32)
    for side in (-1, 1):
        # 侧窗贴合斜侧柱，中央细 B 柱保持车漆色。
        for low_y, high_y, roof_a, roof_b in (
            (front - 0.11, -0.36, roof_front - 0.08, -0.36),
            (-0.43, rear + 0.14, -0.43, roof_rear + 0.08),
        ):
            _surface(
                body,
                "side-glass",
                [
                    (side * 0.793, low_y, 0.40),
                    (side * 0.793, high_y, 0.40),
                    (side * 0.642, roof_b, roof_z - 0.075),
                    (side * 0.642, roof_a, roof_z - 0.075),
                ],
                [(0, 1, 2, 3)],
                glass,
                0.15,
                0.3,
            )
        _box(body, "mirror", (side * 0.887, 0.53, 0.45), (0.125, 0.23, 0.12), paint, 0.26, 0.22)
        _box(body, "door-seam", (side * 0.886, -0.42, 0.08), (0.008, 0.012, 0.37), dark)
        _box(body, "door-handle", (side * 0.891, -0.24, 0.25), (0.014, 0.17, 0.045), dark)
        _box(body, "paint", (side * 0.82, 0, -0.255), (0.13, 1.22, 0.09), paint, 0.26, 0.22)
        _box(
            body,
            "headlamp",
            (side * 0.57, 2.11, 0.10),
            (0.43, 0.025, 0.12),
            (0.93, 0.88, 0.68),
            0.17,
            0.15,
            (0.25, 0.22, 0.13),
        )
        _box(
            body,
            "tail-lamp",
            (side * 0.56, -2.11, 0.12),
            (0.48, 0.025, 0.13),
            (0.65, 0.008, 0.006),
            0.2,
            0.1,
            (0.13, 0.001, 0.001),
        )
        _box(body, "bumper-intake", (side * 0.57, 2.128, -0.13), (0.30, 0.027, 0.10), dark)
        _box(
            body,
            "belt-line",
            (side * 0.87, 0, 0.09),
            (0.012, 1.38, 0.018),
            (0.29, 0.08, 0.015),
            0.45,
        )
        _box(
            body,
            "sill-highlight",
            (side * 0.889, 0, -0.215),
            (0.012, 1.20, 0.022),
            (1.0, 0.38, 0.08),
            0.24,
            0.2,
        )
        _box(
            body, "indicator", (side * 0.78, 2.113, 0.10), (0.08, 0.03, 0.115), (1, 0.3, 0.01), 0.2
        )
        _box(body, "exhaust", (side * 0.57, -2.125, -0.26), (0.18, 0.04, 0.075), silver, 0.2, 0.8)
        # 弹出灯盖及轮拱唇边。
        lid = _box(
            body,
            "headlight-cover",
            (side * 0.55, 1.68, 0.273),
            (0.41, 0.34, 0.018),
            paint,
            0.26,
            0.22,
        )
        lid.setP(-3)
        for hub in (-1.1, 1.1):
            for i in range(16):
                a, b = i * math.pi / 16, (i + 1) * math.pi / 16
                v = [
                    (side * 0.889, hub + math.cos(t) * r, -0.12 + math.sin(t) * r)
                    for r, t in ((0.40, a), (0.40, b), (0.43, b), (0.43, a))
                ]
                _surface(body, "paint", v, [(0, 1, 2, 3)], paint, 0.26, 0.22)
    for y in (-2.119, 2.119):
        _box(body, "bumper-trim", (0, y, -0.23), (1.64, 0.025, 0.045), dark)
        _box(body, "license-plate", (0, y, 0.005), (0.31, 0.029, 0.09), (0.65, 0.72, 0.74), 0.7)
    _box(body, "front-grille", (0, 2.125, -0.115), (0.73, 0.02, 0.16), dark)
    for z in (-0.17, -0.12, -0.07):
        _box(body, "grille-slat", (0, 2.139, z), (0.72, 0.009, 0.012), (0.13, 0.16, 0.18), 0.4, 0.4)
    if not sedan:
        for x in (-0.61, 0.61):
            _box(body, "paint", (x, -1.80, 0.42), (0.06, 0.16, 0.21), paint, 0.26, 0.22)
        _box(body, "paint", (0, -1.82, 0.53), (1.72, 0.25, 0.06), paint, 0.26, 0.22)
    wheels = []
    for name, hub in zip(WHEEL_NAMES, WHEEL_HUBS):
        pivot = parent.attachNewNode(name)
        pivot.setPos(hub[0], hub[1], -0.12)
        _ring(pivot, "tyre", -0.12, 0.12, 0.33, 0.245, dark)
        side = -1 if hub[0] < 0 else 1
        _ring(pivot, "alloy-rim", side * 0.121, side * 0.133, 0.255, 0.206, silver, 0.8)
        _ring(pivot, "brake-disc", side * 0.075, side * 0.08, 0.196, 0.055, (0.24, 0.27, 0.29), 0.7)
        _ring(pivot, "wheel-hub", side * 0.125, side * 0.145, 0.067, 0, silver, 0.8)
        for i in range(5):
            angle = i * math.tau / 5
            v = []
            for radius, delta in ((0.055, -0.35), (0.22, -0.11), (0.22, 0.11), (0.055, 0.35)):
                v.append(
                    (
                        side * 0.137,
                        math.sin(angle + delta) * radius,
                        math.cos(angle + delta) * radius,
                    )
                )
            _surface(pivot, "alloy-spoke", v, [(0, 1, 2, 3)], silver, 0.22, 0.8)
        wheels.append(pivot)
    return root, wheels
