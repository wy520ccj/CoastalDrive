"""海岸示范段的视觉地貌；只读取稳定地图，不创建物理表面。"""

import math
from functools import lru_cache

from coastal_map import DISTANCES, MAP_POINTS, SEA_LEVEL, island_mesh, offset_point, project

# 人工指定林地坡与岩坡中心（沿路米数、内侧米数、隆起米数、纵向半径、横向半径）。
RIDGES = ((108, 29, 6, 36, 18), (149, 34, 9, 25, 20), (295, 28, 3, 28, 15))
ROCK_BEDS = ((102, 12.5, 9, 5), (146, 13.5, 10, 6), (293, 12, 12, 5))
# 灯塔位于北侧礁岬，从海湾转弯后持续可见；不再复制巨型圆台岛。
REEF_CENTER = (-52.0, 193.0)
REEF_RADII = (28.0, 19.0)
LIGHTHOUSE_POSITION = (-52.0, 193.0, 4.35)


def smooth(a, b, x):
    t = max(0, min(1, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def slice_weight(s):
    return smooth(0, 18, s) * (1 - smooth(335, 360, s))


def base_height(x, y):
    vertices, triangles = island_mesh()
    for ia, ib, ic in triangles:
        a, b, c = vertices[ia], vertices[ib], vertices[ic]
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
        v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
        if u >= -1e-7 and v >= -1e-7 and u + v <= 1 + 1e-7:
            return u * a[2] + v * b[2] + (1 - u - v) * c[2]
    raise ValueError(f"地貌采样点在岛外：{x}, {y}")


@lru_cache(maxsize=1)
def existing_roots():
    from world_props import props_for

    return tuple((p.x, p.y) for p in props_for("coastal") if p.kind == "tree")


def relief(x, y, s, d):
    height = sum(
        h * math.exp(-(((s - cs) / rs) ** 2) - ((d - cd) / rd) ** 2) for cs, cd, h, rs, rd in RIDGES
    )
    height += 0.22 * (math.sin(x * 0.47 + y * 0.13) + math.sin(y * 0.29 - x * 0.22))
    # 原有可碰撞树干周围保持原地面，避免埋没可见碰撞物。
    root_distance = min(math.hypot(x - rx, y - ry) for rx, ry in existing_roots())
    return max(0, height) * smooth(8, 16, d) * slice_weight(s) * smooth(0.7, 4, root_distance)


def ground_height(x, y):
    mesh = landscape_meshes()[0]
    for triangle in mesh["faces"]:
        points = [mesh["vertices"][i] for i in triangle]
        weights = triangle_weights(x, y, points)
        if weights is not None:
            return sum(w * p[2] for w, p in zip(weights, points))
    raise ValueError(f"采样点在视觉岛面之外：{x}, {y}")


def mix(a, b, t):
    return tuple(x * (1 - t) + y * t for x, y in zip(a, b))


def ground_color(x, y, s, d):
    variation = 0.5 + 0.25 * math.sin(x * 0.29 + y * 0.37) + 0.25 * math.sin(x * 0.71 - y * 0.23)
    grass = mix((0.13, 0.22, 0.038), (0.26, 0.34, 0.082), variation)
    bare = max(
        math.exp(-(((s - cs) / rs) ** 2) - ((d - cd) / rd) ** 2) for cs, cd, rs, rd in ROCK_BEDS
    )
    roots = min(math.hypot(x - rx, y - ry) for rx, ry in existing_roots())
    soil = max(bare * 0.85, (1 - smooth(0, 3, roots)) * 0.7, (1 - smooth(6.4, 10, d)) * 0.55)
    colored = mix(grass, (0.37, 0.29, 0.15), soil)
    slope = sum(
        h * math.exp(-(((s - cs) / rs) ** 2) - ((d - cd) / rd) ** 2) * abs(2 * (d - cd) / rd**2)
        for cs, cd, h, rs, rd in RIDGES
    )
    exposed = smooth(0.35, 0.75, slope) * (0.6 + 0.4 * variation)
    colored = mix(colored, (0.43, 0.38, 0.26), max(exposed, bare * 0.45))
    return (*mix((0.18, 0.29, 0.065), colored, slice_weight(s)), 1)


def shore_point(s, lateral_fraction):
    from coastal_map import point_at

    p = point_at(s)
    weight = slice_weight(s)
    # 林地弯外侧露出窄岩岸，海湾处形成低矮宽岩台。
    width = 18 + 10 * math.exp(-(((s - 208) / 46) ** 2)) + 5 * math.sin(s * 0.035) ** 2
    distance = 6.4 + lateral_fraction * (9.6 * (1 - weight) + width * weight)
    x, y, _ = offset_point(p, distance)
    old = p.z - 14 * (distance - 6.4) / 9.6
    # 外侧原有碰撞岩石在8.5米处，近路的岸坡保持原斜率，不能把它们埋成隐形障碍。
    knee = p.z - 14 * (10 - 6.4) / 9.6
    beyond = max(0, (distance - 10) / (6.4 + width - 10))
    level = (
        p.z - 14 * (distance - 6.4) / 9.6
        if distance <= 10
        else knee * (1 - beyond)
        - 7 * beyond
        + 0.5 * math.sin(beyond * math.pi) * math.sin(s * 0.15)
    )
    return (x, y, old * (1 - weight) + level * weight)


def reef_radius(angle):
    return 1 + 0.12 * math.sin(angle * 3 + 0.4) + 0.07 * math.sin(angle * 7)


def shoreline_segments():
    """从最终岸坡和礁石三角网格求海平面交线，供离线烘焙。"""
    segments = []
    for mesh in landscape_meshes()[1:]:
        for face in mesh["faces"]:
            points = [mesh["vertices"][i] for i in face]
            intersections = []
            for a, b in zip(points, points[1:] + points[:1]):
                if (a[2] - SEA_LEVEL) * (b[2] - SEA_LEVEL) < 0:
                    t = (SEA_LEVEL - a[2]) / (b[2] - a[2])
                    intersections.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
            if len(intersections) == 2:
                segments.append(tuple(intersections))
    return tuple(segments)


def triangle_weights(x, y, points):
    a, b, c = points
    if not min(a[0], b[0], c[0]) - 1e-7 <= x <= max(a[0], b[0], c[0]) + 1e-7:
        return None
    if not min(a[1], b[1], c[1]) - 1e-7 <= y <= max(a[1], b[1], c[1]) + 1e-7:
        return None
    det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(det) < 1e-10:
        return None
    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
    if min(u, v, 1 - u - v) < -1e-7:
        return None
    return u, v, 1 - u - v


@lru_cache(maxsize=1)
def landscape_meshes():
    result = []
    vertices = []
    colors = []
    faces = []
    # 细分原岛面扇形，原有边界逐点保留；只有示范段内侧产生隆起。
    rings = 32
    count = len(MAP_POINTS)
    for ring in range(rings + 1):
        t = ring / rings
        for i, p in enumerate(MAP_POINTS):
            ex, ey, ez = offset_point(p, -6.4)
            x, y = ex * t, ey * t
            _, d, s = project(x, y)
            z = 10 * (1 - t) + ez * t + relief(x, y, s, d)
            vertices.append((x, y, z))
            colors.append(ground_color(x, y, s, d))
    for r in range(rings):
        for i in range(count):
            a = r * count + i
            b = r * count + (i + 1) % count
            c = b + count
            d = a + count
            faces.append((a, d, c))
            if r > 0:
                faces.append((a, c, b))
    # 将现有树干坐标纳入网格顶点，准确保留它们的原地面接触点。
    for x, y in existing_roots():
        for face_index, face in enumerate(faces):
            weights = triangle_weights(x, y, [vertices[i] for i in face])
            if weights is not None and min(weights) > 1e-6:
                _, d, s = project(x, y)
                new = len(vertices)
                vertices.append((x, y, base_height(x, y)))
                colors.append(ground_color(x, y, s, d))
                a, b, c = faces.pop(face_index)
                faces.extend(((a, b, new), (b, c, new), (c, a, new)))
                break
    result.append({"name": "inland", "vertices": vertices, "faces": faces, "colors": colors})
    vertices = []
    colors = []
    faces = []
    # 每个原道路节点取同一外侧起点，避免与护栏/路肩之间裂开。
    for i, p in enumerate(MAP_POINTS):
        for j in range(13):
            x, y, z = shore_point(DISTANCES[i], j / 12)
            wet = 1 - smooth(SEA_LEVEL + 0.2, SEA_LEVEL + 2, z)
            tone = 0.5 + 0.25 * math.sin(x * 0.21 + z * 2.4) + 0.2 * math.sin(y * 0.49 + z)
            rock = mix((0.32, 0.28, 0.20), (0.64, 0.54, 0.36), tone)
            col = mix(rock, (0.105, 0.17, 0.15), wet * 0.8)
            vertices.append((x, y, z))
            colors.append((*col, 1))
    for i in range(count):
        for j in range(12):
            a = i * 13 + j
            b = ((i + 1) % count) * 13 + j
            faces.extend(((a, b, a + 1), (a + 1, b, b + 1)))
    result.append({"name": "coast", "vertices": vertices, "faces": faces, "colors": colors})
    vertices = []
    colors = []
    faces = []
    # 不规则礁岬，从海底连续抬升至灯塔的平整岩台。
    levels = ((1.22, -6), (1, -2.8), (0.94, -0.8), (0.78, 3.5), (0.34, 4.4), (0, 4.4))
    sides = 64
    for r, z in levels:
        for i in range(sides):
            a = math.tau * i / sides
            radius = r * reef_radius(a)
            x = REEF_CENTER[0] + math.cos(a) * REEF_RADII[0] * radius
            y = REEF_CENTER[1] + math.sin(a) * REEF_RADII[1] * radius
            height = z + (math.sin(a * 5) * 0.5 if r > 0.34 else 0)
            vertices.append((x, y, height))
            wet = 1 - smooth(-2.6, -0.2, height)
            color = mix((0.55, 0.45, 0.29), (0.12, 0.19, 0.16), wet)
            if r <= 0.34:
                color = (0.28, 0.31, 0.10)
            colors.append((*color, 1))
    for row in range(len(levels) - 1):
        for i in range(sides):
            a = row * sides + i
            b = row * sides + (i + 1) % sides
            faces.append((a, b, a + sides))
            if row < len(levels) - 2:
                faces.append((b, b + sides, a + sides))
    result.append(
        {"name": "lighthouse-reef", "vertices": vertices, "faces": faces, "colors": colors}
    )
    return result
