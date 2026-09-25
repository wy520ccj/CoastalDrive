"""Deterministic, local-coordinate chunks for the streamed highway."""

import random
from dataclasses import dataclass
from math import floor

SEGMENT_LENGTH = 200
KEEP_RADIUS = 1200
REBASE_DISTANCE = 2000

_ROAD_HALF_WIDTH = 13.5 / 2
_SHOULDER_EDGE = 8.5
_GROUND_EDGE = 120.0
_TREE_COUNT = 8
_VERSION = 1


@dataclass(frozen=True)
class Segment:
    """A highway segment and its decorative trees in segment-local coordinates."""

    index: int
    trees: tuple[tuple[float, float, float, float], ...]


def _mix(value: int) -> int:
    """A stable 64-bit integer mixer (kept independent of Python's hash seed)."""
    value &= (1 << 64) - 1
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & ((1 << 64) - 1)
    return (value ^ (value >> 31)) & ((1 << 64) - 1)


def segment(seed: int, index: int) -> Segment:
    """Return a deterministic segment for any integer seed and signed index."""
    mixed = _mix(int(seed) ^ _mix(int(index) ^ _VERSION))
    rng = random.Random(mixed)
    trees = []
    for _ in range(_TREE_COUNT):
        side = -1 if rng.randrange(2) == 0 else 1
        x = side * rng.uniform(20.0, 34.0)
        y = rng.uniform(4.0, SEGMENT_LENGTH - 4.0)
        scale = rng.uniform(2.2, 3.2)
        heading = rng.uniform(0.0, 360.0)
        trees.append((x, y, scale, heading))
    return Segment(int(index), tuple(trees))


def segment_index(global_y: float) -> int:
    """Map a world y coordinate to its containing segment."""
    return floor(global_y / SEGMENT_LENGTH)


def indices_around(global_y: float, radius: float = KEEP_RADIUS) -> range:
    """Return all segments intersecting the inclusive y keep window."""
    if radius < 0:
        raise ValueError("radius must be non-negative")
    first = segment_index(global_y - radius)
    last = segment_index(global_y + radius)
    return range(first, last + 1)


def _strip_mesh(x_left: float, x_right: float, z: float = 0.0):
    vertices = []
    triangles = []
    for row in range(SEGMENT_LENGTH // 40 + 1):
        y = row * 40.0
        vertices.extend(((x_left, y, z), (x_right, y, z)))
    for row in range(SEGMENT_LENGTH // 40):
        base = row * 2
        triangles.extend(((base, base + 1, base + 3), (base, base + 3, base + 2)))
    return vertices, triangles


def _box_mesh(cx: float, half_x: float, bottom: float, top: float):
    vertices = [
        (cx - half_x, 0.0, bottom),
        (cx + half_x, 0.0, bottom),
        (cx + half_x, SEGMENT_LENGTH, bottom),
        (cx - half_x, SEGMENT_LENGTH, bottom),
        (cx - half_x, 0.0, top),
        (cx + half_x, 0.0, top),
        (cx + half_x, SEGMENT_LENGTH, top),
        (cx - half_x, SEGMENT_LENGTH, top),
    ]
    faces = (
        (0, 2, 1),
        (0, 3, 2),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
        (4, 5, 6),
        (4, 6, 7),
    )
    return vertices, faces


def surface_meshes() -> dict[
    str, tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]
]:
    """Build one local segment of short, ray-friendly highway meshes."""
    meshes = {
        "road": _strip_mesh(-_ROAD_HALF_WIDTH, _ROAD_HALF_WIDTH),
        "shoulder-left": _strip_mesh(-_SHOULDER_EDGE, -_ROAD_HALF_WIDTH),
        "shoulder-right": _strip_mesh(_ROAD_HALF_WIDTH, _SHOULDER_EDGE),
        "ground": _strip_mesh(-_GROUND_EDGE, _GROUND_EDGE, -0.32),
        "rail-left": _box_mesh(-8.0, 0.12, 0.0, 0.8),
        "rail-right": _box_mesh(8.0, 0.12, 0.0, 0.8),
    }
    return meshes
