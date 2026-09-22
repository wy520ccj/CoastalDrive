"""Road layout and meshes shared by the renderer and Bullet. Distances are metres."""

import math
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise

ROAD_WIDTH = 8.6
SHOULDER_WIDTH = 12.8
RAIL_OFFSET = 6.0
MAP_POINT_COUNT = 256
SEA_LEVEL = -3.0


@dataclass(frozen=True)
class MapPoint:
    x: float
    y: float
    z: float
    heading: float
    grade: float


def _make_points():
    # Start straight, high northern bend, western S-bend, then the low sea bend.
    anchors = [
        (95, 0, 0),
        (95, 30, 0),
        (95, 60, 0.8),
        (70, 103, 3.5),
        (20, 121, 6),
        (-35, 112, 8),
        (-80, 80, 7),
        (-92, 35, 5.5),
        (-69, -8, 4),
        (-87, -48, 3),
        (-72, -88, 2),
        (-28, -113, 1),
        (22, -120, 0.5),
        (71, -96, 0),
        (95, -60, 0),
        (95, -30, 0),
    ]
    samples = []
    for i in range(len(anchors)):
        a, b, c, d = [anchors[j % len(anchors)] for j in (i - 1, i, i + 1, i + 2)]
        for k in range(32):
            t = k / 32
            samples.append(
                tuple(
                    0.5
                    * (
                        2 * q
                        + (-p + r) * t
                        + (2 * p - 5 * q + 4 * r - s) * t * t
                        + (-p + 3 * q - 3 * r + s) * t * t * t
                    )
                    for p, q, r, s in zip(a, b, c, d)
                )
            )
    samples.append(samples[0])
    distances = [0.0]
    for a, b in pairwise(samples):
        distances.append(distances[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    raw = []
    for i in range(MAP_POINT_COUNT):
        distance = i * distances[-1] / MAP_POINT_COUNT
        j = bisect_right(distances, distance) - 1
        t = (distance - distances[j]) / (distances[j + 1] - distances[j])
        raw.append(tuple(a + (b - a) * t for a, b in zip(samples[j], samples[j + 1])))
    points = []
    for i, (x, y, z) in enumerate(raw):
        before, after = raw[i - 1], raw[(i + 1) % len(raw)]
        dx, dy = after[0] - before[0], after[1] - before[1]
        points.append(
            MapPoint(
                x,
                y,
                z,
                math.degrees(math.atan2(-dx, dy)),
                math.degrees(math.atan2(after[2] - before[2], math.hypot(dx, dy))),
            )
        )
    return tuple(points)


MAP_POINTS = _make_points()


def segment(index):
    a = MAP_POINTS[index % MAP_POINT_COUNT]
    b = MAP_POINTS[(index + 1) % MAP_POINT_COUNT]
    return a, b, math.hypot(b.x - a.x, b.y - a.y)


LENGTHS = tuple(segment(i)[2] for i in range(MAP_POINT_COUNT))
DISTANCES = (0.0, *[sum(LENGTHS[: i + 1]) for i in range(MAP_POINT_COUNT)])


def map_length():
    return DISTANCES[-1]


def blend(a, b, t):
    heading = a.heading + ((b.heading - a.heading + 180) % 360 - 180) * t
    return MapPoint(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        a.z + (b.z - a.z) * t,
        heading,
        a.grade + (b.grade - a.grade) * t,
    )


def point_at(distance):
    distance %= map_length()
    i = bisect_right(DISTANCES, distance) - 1
    return blend(
        MAP_POINTS[i], MAP_POINTS[(i + 1) % MAP_POINT_COUNT], (distance - DISTANCES[i]) / LENGTHS[i]
    )


def project(x, y):
    """Nearest centreline point, lateral distance and distance along the loop."""
    best = float("inf")
    best_i, best_t = 0, 0.0
    for i, a in enumerate(MAP_POINTS):
        b = MAP_POINTS[(i + 1) % MAP_POINT_COUNT]
        dx, dy = b.x - a.x, b.y - a.y
        t = max(0, min(1, ((x - a.x) * dx + (y - a.y) * dy) / (dx * dx + dy * dy)))
        distance = (x - a.x - t * dx) ** 2 + (y - a.y - t * dy) ** 2
        if distance < best:
            best, best_i, best_t = distance, i, t
    a, b, _ = segment(best_i)
    return blend(a, b, best_t), math.sqrt(best), DISTANCES[best_i] + LENGTHS[best_i] * best_t


def nearest_point(x, y):
    point, distance, _ = project(x, y)
    return point, distance


def road_height(x, y):
    point, distance = nearest_point(x, y)
    return point.z if distance <= SHOULDER_WIDTH / 2 else SEA_LEVEL


ROAD_SEGMENTS = tuple(
    (
        a.x,
        a.y,
        b.x - a.x,
        b.y - a.y,
        length * length,
        min(a.x, b.x) - ROAD_WIDTH / 2,
        max(a.x, b.x) + ROAD_WIDTH / 2,
        min(a.y, b.y) - ROAD_WIDTH / 2,
        max(a.y, b.y) + ROAD_WIDTH / 2,
    )
    for a, b, length in (segment(i) for i in range(MAP_POINT_COUNT))
)


def on_road(x, y):
    for ax, ay, dx, dy, length_sq, left, right, bottom, top in ROAD_SEGMENTS:
        if left <= x <= right and bottom <= y <= top:
            t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / length_sq))
            if (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2 <= (ROAD_WIDTH / 2) ** 2:
                return True
    return False


def coast_side(point):
    angle = math.radians(point.heading)
    return math.cos(angle), math.sin(angle), 0.0


def offset_point(point, offset, height=0):
    nx, ny, _ = coast_side(point)
    return point.x + nx * offset, point.y + ny * offset, point.z + height


def strip_mesh(inner, outer, inner_height=0, outer_height=0):
    vertices = []
    for point in MAP_POINTS:
        vertices.extend(
            (offset_point(point, inner, inner_height), offset_point(point, outer, outer_height))
        )
    triangles = []
    for i in range(MAP_POINT_COUNT):
        a, b = i * 2, ((i + 1) % MAP_POINT_COUNT) * 2
        triangles.extend(((a, a + 1, b + 1), (a, b + 1, b)))
    return vertices, triangles


def rail_mesh(side):
    vertices, triangles = [], []
    for offset in (side * RAIL_OFFSET - 0.12, side * RAIL_OFFSET + 0.12):
        for p in MAP_POINTS:
            vertices.extend((offset_point(p, offset), offset_point(p, offset, 0.8)))
    n = MAP_POINT_COUNT * 2
    for i in range(MAP_POINT_COUNT):
        a, b = i * 2, ((i + 1) % MAP_POINT_COUNT) * 2
        for quad in (
            (a, b, b + 1, a + 1),
            (a + n, a + 1 + n, b + 1 + n, b + n),
            (a + 1, b + 1, b + 1 + n, a + 1 + n),
        ):
            x, y, z, w = quad
            triangles.extend(((x, z, y), (x, w, z)))
    return vertices, triangles


def island_mesh():
    vertices = [(0, 0, 10)] + [offset_point(p, -SHOULDER_WIDTH / 2) for p in MAP_POINTS]
    triangles = [(0, i + 1, (i + 1) % MAP_POINT_COUNT + 1) for i in range(MAP_POINT_COUNT)]
    return vertices, triangles


@lru_cache(maxsize=1)
def map_meshes():
    """Visible solid surfaces. Both worlds consume these exact triangles."""
    return {
        "road": strip_mesh(-ROAD_WIDTH / 2, ROAD_WIDTH / 2),
        "inner-shoulder": strip_mesh(-SHOULDER_WIDTH / 2, -ROAD_WIDTH / 2),
        "outer-shoulder": strip_mesh(ROAD_WIDTH / 2, SHOULDER_WIDTH / 2),
        "island": island_mesh(),
        "cliff": strip_mesh(SHOULDER_WIDTH / 2, 16, 0, -14),
        "inner-rail": rail_mesh(-1),
        "outer-rail": rail_mesh(1),
    }
