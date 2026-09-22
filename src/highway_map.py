"""A finite three-lane road used as the first step toward streamed highways."""

import random
from dataclasses import dataclass

HIGHWAY_LENGTH = 1400.0
TRAFFIC_EXIT = HIGHWAY_LENGTH + 5
ROAD_WIDTH = 13.5
LANE_WIDTH = 4.5
SHOULDER_WIDTH = 17.0
SPAWN = (0.0, 8.0, 0.55)


@dataclass(frozen=True)
class TrafficSpawn:
    lane: int
    distance: float
    speed: float


def on_road(x, y):
    return abs(x) <= ROAD_WIDTH / 2 and -20 <= y <= HIGHWAY_LENGTH + 20


def lane_x(lane):
    return (lane - 1) * LANE_WIDTH


def collision_boxes():
    # Flat slabs avoid triangle-edge bumps under sliding traffic bodies.
    length = HIGHWAY_LENGTH + 40
    center_y = HIGHWAY_LENGTH / 2
    shoulder = (SHOULDER_WIDTH - ROAD_WIDTH) / 2
    result = {
        "highway-road": ((ROAD_WIDTH / 2, length / 2, 0.1), (0, center_y, -0.1)),
        "highway-ground": ((120, length / 2, 0.2), (0, center_y, -0.52)),
    }
    for side, name in ((-1, "left"), (1, "right")):
        x = side * (ROAD_WIDTH / 2 + shoulder / 2)
        result[f"{name}-shoulder"] = ((shoulder / 2, length / 2, 0.1), (x, center_y, -0.1))
        result[f"highway-rail-{side}"] = ((0.12, length / 2, 0.4), (side * 8, center_y, 0.4))
    return result


def meshes():
    triangles = [
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
    ]
    result = {}
    for name, ((x, y, z), (cx, cy, cz)) in collision_boxes().items():
        vertices = [
            (cx - x, cy - y, cz - z),
            (cx + x, cy - y, cz - z),
            (cx + x, cy + y, cz - z),
            (cx - x, cy + y, cz - z),
            (cx - x, cy - y, cz + z),
            (cx + x, cy - y, cz + z),
            (cx + x, cy + y, cz + z),
            (cx - x, cy + y, cz + z),
        ]
        result[name] = vertices, triangles
    return result


def traffic_spawns(seed):
    # Deterministic placement; later streaming can replace this list by chunks.
    rng = random.Random(seed)
    return tuple(
        TrafficSpawn(
            rng.randrange(3), 100 + i * 145 + rng.uniform(-20, 20), 14 + rng.uniform(-2, 4)
        )
        for i in range(8)
    )
