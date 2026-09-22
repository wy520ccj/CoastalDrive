"""Shared display/collision geometry in coordinates relative to a segment anchor."""

from highway_segments import SEGMENT_LENGTH, segment

MESH_STEP = 5


def anchor(curve, index):
    p = curve.sample(index * SEGMENT_LENGTH)
    return p.x, p.y, p.z


def point(curve, index, local_s, lateral, height=0):
    p = curve.sample(index * SEGMENT_LENGTH + local_s, lateral)
    x, y, z = anchor(curve, index)
    return p.x - x, p.y - y, p.z - z + height


def strip(curve, index, left, right, height=0, *, start=0, end=SEGMENT_LENGTH):
    vertices, triangles = [], []
    rows = list(range(start, end, MESH_STEP)) + [end]
    for s in rows:
        vertices.extend((point(curve, index, s, left, height), point(curve, index, s, right, height)))
    for row in range(len(rows) - 1):
        b = 2 * row
        triangles.extend(((b, b + 1, b + 3), (b, b + 3, b + 2)))
    return vertices, triangles


def rail(curve, index, lateral):
    vertices, triangles = [], []
    for s in range(0, SEGMENT_LENGTH + 1, MESH_STEP):
        vertices.extend(point(curve, index, s, d, z) for d, z in (
            (lateral - 0.12, 0), (lateral + 0.12, 0),
            (lateral + 0.12, 0.8), (lateral - 0.12, 0.8),
        ))
    for row in range(SEGMENT_LENGTH // MESH_STEP):
        for corner in range(4):
            a, b = row * 4 + corner, row * 4 + (corner + 1) % 4
            triangles.extend(((a, b, b + 4), (a, b + 4, a + 4)))
    last = len(vertices) - 4
    triangles.extend(((0, 2, 1), (0, 3, 2), (last, last + 1, last + 2), (last, last + 2, last + 3)))
    return vertices, triangles


def surfaces(curve, index):
    return {
        "road": strip(curve, index, -6.75, 6.75),
        "shoulder-left": strip(curve, index, -8.5, -6.75),
        "shoulder-right": strip(curve, index, 6.75, 8.5),
        "ground": strip(curve, index, -120, 120, -0.32),
        "rail-left": rail(curve, index, -8),
        "rail-right": rail(curve, index, 8),
    }


def markings(curve, index):
    return [strip(curve, index, x - 0.06, x + 0.06, 0.035, start=s, end=s + 4)
            for x in (-2.25, 2.25) for s in range(0, SEGMENT_LENGTH, 8)]


def trees(curve, seed, index):
    for lateral, s, scale, heading in segment(seed, index).trees:
        yield point(curve, index, s, lateral, -0.32 + 0.05 * scale), scale, heading
