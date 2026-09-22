"""Shared test-field geometry for physics and rendering."""

from dataclasses import dataclass

TRACK_X = 95.0
TRACK_Y = 115.0
SPAWN = (TRACK_X, 0.0, 0.55)
TEST_SPAWN = (180.0, 0.0, 0.55)


@dataclass(frozen=True)
class Obstacle:
    name: str
    center: tuple[float, float, float]
    half_size: tuple[float, float, float]
    pitch: float = 0.0


# A separate straight, braking wall, slalom blocks, and a shallow ramp.
OBSTACLES = (
    Obstacle("end-wall", (95, 720, 1), (7, 0.6, 1)),
    Obstacle("slalom-1", (115, 35, 0.65), (1.5, 1.5, 0.65)),
    Obstacle("slalom-2", (121, 60, 0.65), (1.5, 1.5, 0.65)),
    Obstacle("slalom-3", (115, 85, 0.65), (1.5, 1.5, 0.65)),
    Obstacle("ramp", (70, 45, 0.30), (3, 6, 0.20), 4.0),
)


def on_asphalt(x, y):
    if 88 <= x <= 102 and -20 <= y <= 725:
        return True
    if 170 <= x <= 190 and -100 <= y <= 1200:
        return True
    return 62 <= x <= 130 and -20 <= y <= 105
