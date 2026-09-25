"""Stylized, display-only forms for the coastal route."""

import math

from panda3d.core import Shader, Vec3, Vec4

from coastal_map import SEA_LEVEL, map_length, offset_point, point_at, strip_mesh

STONE_PALETTE = (
    Vec4(0.80, 0.68, 0.52, 1),
    Vec4(0.70, 0.57, 0.43, 1),
    Vec4(0.88, 0.76, 0.60, 1),
    Vec4(0.57, 0.49, 0.41, 1),
)


def add_coastal_backdrop(parent, make_mesh, make_box, make_cylinder, make_cone):
    """Add scenic layers beyond the road-side props; none participate in physics."""

    # A shallow turquoise band gives the cliff edge a readable shoreline.

    vertices, triangles = strip_mesh(16.0, 23.0, -2.94, -2.94)

    shallows = make_mesh("coastal-shallows", vertices, triangles, Vec4(0.08, 0.48, 0.57, 1))

    shallows.setTransparency(True)

    shallows.setAlphaScale(0.44)

    shallows.setDepthWrite(False)

    shallows.setLightOff(1)

    shallows.reparentTo(parent)

    # Broken low-poly islets sit beyond the route and leave open gaps to the horizon.

    for index in range(5):
        progress = (index + 0.35) / 5

        point = point_at(map_length() * progress)

        position = offset_point(point, 105 + (index % 3) * 22, SEA_LEVEL)

        _add_ridge(parent, make_mesh, position, 32 + (index % 3) * 9, 9 + (index * 7 % 8), index)

    # Cooler, taller profiles are far enough away to read as a distant coast.

    for index in range(10):
        progress = (index + 0.7) / 10

        point = point_at(map_length() * progress)

        position = offset_point(point, 360 + (index % 2) * 70, -11)

        _add_ridge(
            parent,
            make_mesh,
            position,
            115 + (index % 3) * 25,
            52 + (index * 11 % 24),
            index + 20,
            distant=True,
        )

    add_coastal_detail(parent, make_mesh, make_cylinder)
    for distance in range(20, int(map_length()), 48):
        p = point_at(distance)
        add_streetlight(parent, make_box, offset_point(p, 7.9), p.heading)
    _add_lighthouse(parent, make_mesh, make_box, make_cylinder, make_cone)

    _add_village(parent, make_mesh, make_box)

    add_city(parent, make_box, (-35, 230))


def _add_ridge(parent, make_mesh, position, radius, height, seed, distant=False):
    """连续多峰山体；细分坡面保持山脊与山脚连接。"""

    import random

    rng = random.Random(seed)

    peaks = [
        (rng.uniform(-0.6, 0.6), rng.uniform(-0.35, 0.35), rng.uniform(0.6, 1.0)) for _ in range(6)
    ]

    count = 48

    vertices = []

    heights = []

    for j in range(count + 1):
        v = j / count * 2 - 1

        for i in range(count + 1):
            u = i / count * 2 - 1

            edge = max(0, (1 - u * u) * (1 - v * v))

            h = max(
                weight * math.exp(-((u - px) ** 2 * 7 + (v - py) ** 2 * 9))
                for px, py, weight in peaks
            )

            h *= edge * (1 + 0.035 * math.sin(u * 39 + v * 17 + seed) + 0.02 * math.cos(v * 53))

            heights.append(h)

            vertices.append(
                (position[0] + u * radius * 1.7, position[1] + v * radius, -3 + height * h)
            )

    groups = [[] for _ in range(5)]

    for j in range(count):
        for i in range(count):
            a = j * (count + 1) + i
            b = a + 1
            c = a + count + 1
            d = c + 1

            tone = min(4, max(0, int(heights[a] * 5 + math.sin(i * 0.4 + j * 0.7) * 0.55)))

            groups[tone].extend([(a, b, d), (a, d, c)])

    palette = (
        (
            (0.29, 0.43, 0.54),
            (0.34, 0.48, 0.57),
            (0.39, 0.53, 0.61),
            (0.45, 0.58, 0.64),
            (0.38, 0.48, 0.56),
        )
        if distant
        else (
            (0.28, 0.37, 0.23),
            (0.36, 0.44, 0.25),
            (0.44, 0.47, 0.29),
            (0.52, 0.49, 0.34),
            (0.40, 0.42, 0.28),
        )
    )

    for index, faces in enumerate(groups):
        node = make_mesh(f"coastal-ridge-{seed}-{index}", vertices, faces, Vec4(*palette[index], 1))
        node.setShader(Shader.make(Shader.SL_GLSL, RIDGE_VERTEX, RIDGE_FRAGMENT), 10)

        node.reparentTo(parent)


def add_city(parent, make_box, center=(0, 240), seed=41):
    """窗格、楼顶和分层楼群均为三维几何。"""

    import random

    rng = random.Random(seed)

    root = parent.attachNewNode("coastal-city")

    for i in range(42):
        x = center[0] + rng.uniform(-85, 85)
        y = center[1] + rng.uniform(-30, 30)

        w = rng.uniform(2, 4)
        h = rng.uniform(8, 29)

        body = make_box(
            "city-tower", (w, w * 0.65, h / 2), Vec4(0.73 + rng.random() * 0.15, 0.72, 0.61, 1)
        )

        body.setPos(x, y, h / 2 - 2)
        body.reparentTo(root)

        for z in range(2, int(h) - 2, 3):
            for dx in (-w * 0.55, w * 0.55):
                win = make_box("city-window", (0.45, 0.035, 0.75), Vec4(0.24, 0.40, 0.47, 1))

                win.setPos(x + dx, y - w * 0.65 - 0.04, z)
                win.reparentTo(root)

        roof = make_box("city-roof", (w + 0.12, w * 0.65 + 0.12, 0.18), Vec4(0.48, 0.54, 0.52, 1))

        roof.setPos(x, y, h - 2)
        roof.reparentTo(root)

    root.flattenStrong()


def _add_lighthouse(parent, make_mesh, make_box, make_cylinder, make_cone):

    point = point_at(map_length() * 0.16)

    x, y, _ = offset_point(point, 44, SEA_LEVEL)

    base_z = 0.15

    rock = make_cone(
        "lighthouse-rock", Vec3(x, y, SEA_LEVEL), 8.5, 4.2, Vec4(0.66, 0.56, 0.45, 1), 7
    )

    rock.reparentTo(parent)

    tower = make_cylinder(
        "coastal-lighthouse", Vec3(x, y, base_z + 2.1), 1.35, 8.4, Vec4(0.91, 0.86, 0.72, 1), 8
    )

    tower.reparentTo(parent)

    band = make_cylinder(
        "lighthouse-band", Vec3(x, y, base_z + 3.0), 1.39, 0.65, Vec4(0.86, 0.29, 0.18, 1), 8
    )

    band.reparentTo(parent)

    cap = make_cone(
        "lighthouse-roof", Vec3(x, y, base_z + 10.5), 1.8, 1.5, Vec4(0.79, 0.23, 0.16, 1), 8
    )

    cap.reparentTo(parent)

    lamp = make_box("lighthouse-lantern", (0.95, 0.95, 0.62), Vec4(1.0, 0.73, 0.32, 1))

    lamp.setPos(x, y, base_z + 9.55)

    lamp.reparentTo(parent)


def _add_village(parent, make_mesh, make_box):

    point = point_at(map_length() * 0.36)

    center = offset_point(point, -58)

    tangent = Vec3(-math.sin(math.radians(point.heading)), math.cos(math.radians(point.heading)), 0)

    colors = (Vec4(0.94, 0.86, 0.70, 1), Vec4(0.84, 0.80, 0.68, 1), Vec4(0.97, 0.90, 0.77, 1))

    for index in range(8):
        lane = index // 4

        along = (index % 4) * 8 - 12

        x = center[0] + tangent.x * along + math.cos(math.radians(point.heading)) * (lane * 11)

        y = center[1] + tangent.y * along + math.sin(math.radians(point.heading)) * (lane * 11)

        height = 2.3 + (index % 3) * 0.35

        wall = make_box(f"coast-house-wall-{index}", (2.7, 2.1, height / 2), colors[index % 3])

        wall.setPos(x, y, point.z + height / 2)

        wall.reparentTo(parent)

        roof_vertices = [
            (x - 3.0, y - 2.4, point.z + height),
            (x + 3.0, y - 2.4, point.z + height),
            (x + 3.0, y + 2.4, point.z + height),
            (x - 3.0, y + 2.4, point.z + height),
            (x, y - 2.4, point.z + height + 1.8),
            (x, y + 2.4, point.z + height + 1.8),
        ]

        make_mesh(
            f"coast-house-roof-{index}",
            roof_vertices,
            [(0, 1, 4), (1, 2, 5), (2, 3, 5), (3, 0, 4), (4, 1, 5), (4, 5, 3)],
            Vec4(0.72, 0.30, 0.20, 1),
        ).reparentTo(parent)

        window = make_box(
            f"coast-house-window-{index}", (0.43, 0.08, 0.42), Vec4(0.18, 0.39, 0.48, 1)
        )

        window.setPos(x, y - 2.16, point.z + 1.35)

        window.reparentTo(parent)


def add_coastal_detail(parent, make_mesh, make_cylinder):
    """补充海面碎光和内陆常绿树丛；全部是纯视觉节点。"""
    import random

    rng = random.Random(20260924)
    root = parent.attachNewNode("coastal-detail")
    for index in range(100):
        p = point_at(map_length() * rng.random())
        x, y, z = offset_point(p, -rng.uniform(15, 48))
        height = rng.uniform(3.5, 8)
        make_cylinder(
            "broadleaf-trunk", Vec3(x, y, z), 0.16, height * 0.7, Vec4(0.24, 0.20, 0.10, 1), 6
        ).reparentTo(root)
        for crown in range(3):
            cx = x + rng.uniform(-1, 1)
            cy = y + rng.uniform(-1, 1)
            cz = z + height - crown * 0.9
            radius = rng.uniform(1.4, 2.4)
            verts = [(cx, cy, cz + radius * 0.75), (cx, cy, cz - radius * 0.65)]
            for k in range(8):
                a = k * math.tau / 8
                verts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius, cz))
            faces = []
            for k in range(8):
                a = k + 2
                b = (k + 1) % 8 + 2
                faces.extend([(0, a, b), (1, b, a)])
            make_mesh(
                "broadleaf-crown",
                verts,
                faces,
                Vec4(0.12 + crown * 0.035, 0.28 + crown * 0.025, 0.065, 1),
            ).reparentTo(root)
    verts = []
    faces = []
    for i in range(1100):
        x = rng.uniform(132, 760)
        y = rng.uniform(-300, 650)
        width = rng.uniform(0.7, 4.5)
        length = rng.uniform(0.10, 0.45)
        a = len(verts)
        verts.extend(
            [
                (x - width, y, -2.96),
                (x + width, y, -2.96),
                (x + width * 0.7, y + length, -2.96),
                (x - width * 0.7, y + length, -2.96),
            ]
        )
        faces.extend([(a, a + 1, a + 2), (a, a + 2, a + 3)])
    n = make_mesh("sea-sun-glints", verts, faces, Vec4(0.60, 0.78, 0.69, 1))
    n.setLightOff(1)
    n.reparentTo(root)
    root.flattenStrong()


RIDGE_VERTEX = """#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec4 p3d_Color;
out vec3 position;
out vec3 color;
void main(){gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex;position=p3d_Vertex.xyz;color=p3d_Color.rgb;}
"""
RIDGE_FRAGMENT = """#version 130
in vec3 position;
in vec3 color;
out vec4 fragColor;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
void main(){float rock=noise(position.xy*.21+position.z*.06);float strata=sin(position.z*1.4+noise(position.xy*.05)*9.);
vec3 c=color*(.94+rock*.08+strata*.012);
fragColor=vec4(c*c,1.);}
"""


def add_streetlight(parent, make_box, position, heading=0):
    root = parent.attachNewNode("streetlight")
    root.setPos(*position)
    root.setH(heading)
    pole = make_box("streetlight-pole", (0.075, 0.075, 3.7), Vec4(0.25, 0.30, 0.31, 1))
    pole.setZ(3.7)
    pole.reparentTo(root)
    arm = make_box("streetlight-arm", (1.15, 0.07, 0.07), Vec4(0.30, 0.33, 0.32, 1))
    arm.setPos(-1.1, 0, 7.35)
    arm.reparentTo(root)
    case = make_box("streetlight-case", (0.48, 0.18, 0.09), Vec4(0.25, 0.28, 0.26, 1))
    case.setPos(-2, 0, 7.30)
    case.reparentTo(root)
    lamp = make_box("streetlight-lamp", (0.42, 0.15, 0.025), Vec4(1, 0.80, 0.31, 1))
    lamp.setPos(-2, 0, 7.19)
    lamp.setLightOff(1)
    lamp.reparentTo(root)
