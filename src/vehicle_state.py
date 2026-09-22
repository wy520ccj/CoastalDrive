"""Small, display-independent state types shared by vehicle simulation code."""

import math
from dataclasses import dataclass, field

from vehicle_config import CAR
from vehicle_dynamics import DynamicsState

FIXED_DT = 1 / 120


@dataclass(frozen=True)
class Control:
    steering: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0

    def __post_init__(self):
        if not (-1 <= self.steering <= 1 and 0 <= self.throttle <= 1 and 0 <= self.brake <= 1):
            raise ValueError("Control values outside steering/throttle/brake ranges")


@dataclass(frozen=True)
class WheelState:
    position: tuple[float, float, float]
    orientation: tuple[float, float, float, float]


@dataclass(frozen=True)
class CarState:
    position: tuple[float, float, float]
    heading: float = 0.0
    speed: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    wheels: tuple[WheelState, ...] = ()
    surface: str = "asphalt"
    steering: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    rpm: float = CAR.idle_rpm
    gear: int = 1
    acceleration: float = 0.0
    lateral_acceleration: float = 0.0
    dynamics: DynamicsState = field(default_factory=DynamicsState)
    active: bool = True
    generation: int = 0
    signal: int = 0
    velocity: tuple[float, float, float] | None = None


def forward(heading):
    """Panda heading rotates local +Y toward -X; positive steering means right."""
    angle = math.radians(heading)
    return -math.sin(angle), math.cos(angle), 0.0


def heading_for(x, y):
    return math.degrees(math.atan2(-x, y))
