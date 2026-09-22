"""Small track catalog. Rules choose a mode; tracks only describe road geometry."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import coastal_map


class TrackId(Enum):
    COASTAL_LOOP = "coastal"
    HIGHWAY_PREVIEW = "highway"
    ENDLESS_HIGHWAY = "endless"
    TEST_FIELD = "test"


@dataclass(frozen=True)
class Lane:
    index: int
    center: float
    direction: int
    left: int | None = None
    right: int | None = None


@dataclass(frozen=True)
class Circuit:
    score_id: str
    length: float
    half_width: float
    road_limit: float
    point_at: Callable
    project: Callable
    checkpoints: tuple[float, ...]


COASTAL_CIRCUIT = Circuit(
    "coastal-v2",
    coastal_map.map_length(),
    coastal_map.ROAD_WIDTH / 2,
    coastal_map.SHOULDER_WIDTH / 2,
    coastal_map.point_at,
    coastal_map.project,
    tuple(coastal_map.map_length() * fraction for fraction in (0.2, 0.4, 0.6, 0.8)),
)


@dataclass(frozen=True)
class TrackDefinition:
    id: TrackId
    name: str
    closed: bool
    lane_width: float
    lanes: tuple[Lane, ...]
    seeded_traffic: bool
    circuit: Circuit | None = None


COASTAL_LOOP = TrackDefinition(
    TrackId.COASTAL_LOOP,
    "滨海环路",
    True,
    4.3,
    (Lane(0, -2.15, 1, right=1), Lane(1, 2.15, 1, left=0)),
    False,
    COASTAL_CIRCUIT,
)
HIGHWAY_PREVIEW = TrackDefinition(
    TrackId.HIGHWAY_PREVIEW,
    "多车道高速原型",
    False,
    4.5,
    (Lane(0, -4.5, 1, right=1), Lane(1, 0.0, 1, left=0, right=2), Lane(2, 4.5, 1, left=1)),
    True,
)
TEST_FIELD = TrackDefinition(TrackId.TEST_FIELD, "动力学测试场", False, 0.0, (), False)
ENDLESS_HIGHWAY = TrackDefinition(
    TrackId.ENDLESS_HIGHWAY, "无限高速", False, 4.5, HIGHWAY_PREVIEW.lanes, True
)

TRACKS = {
    track.id.value: track for track in (COASTAL_LOOP, HIGHWAY_PREVIEW, ENDLESS_HIGHWAY, TEST_FIELD)
}


def get_track(track):
    if isinstance(track, TrackId):
        track = track.value
    return TRACKS[track]
