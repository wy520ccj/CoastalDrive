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
class VehicleCommand:
    """执行器请求：转向角为度，踏板为0～1，方向为−1/0/1；绕过输入辅助。"""

    steering: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    direction: int = 0


@dataclass(frozen=True)
class WheelState:
    position: tuple[float, float, float]
    orientation: tuple[float, float, float, float]


@dataclass(frozen=True)
class WheelContactState:
    in_contact: bool
    contact_point: tuple[float, float, float] | None
    contact_normal: tuple[float, float, float] | None
    suspension_force: float
    normal_load: float
    suspension_length: float
    compression: float
    skid: float | None
    surface: str | None


@dataclass(frozen=True)
class WheelDynamicsState:
    """采样轮速/滑移与施力阶段分别记账；force_contact_tick指向采用的轮荷。"""

    omega: float = 0.0
    rotation: float = 0.0
    relative_omega: float = 0.0
    longitudinal_speed: float = 0.0
    lateral_speed: float = 0.0
    kappa: float | None = None
    alpha: float | None = None
    fx: float = 0.0
    fy: float = 0.0
    drive_torque: float = 0.0
    brake_capacity: float = 0.0
    brake_torque: float = 0.0
    normal_load: float = 0.0
    road_support: bool = False
    steering: float = 0.0
    force_contact_tick: int = 0
    force_residual: float = 0.0
    force_kappa: float | None = None
    force_alpha: float | None = None
    sample_support: bool = False
    sample_tick: int = 0
    force_mode: str = "uninitialized"
    longitudinal_impulse: float = 0.0
    lateral_impulse: float = 0.0
    brake_angular_impulse: float = 0.0


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
    hazards: bool = False
    wheel_contacts: tuple[WheelContactState, ...] = ()
    contact_tick: int = 0
    wheel_dynamics: tuple[WheelDynamicsState, ...] = ()


def forward(heading):
    """Panda heading rotates local +Y toward -X; positive steering means right."""
    angle = math.radians(heading)
    return -math.sin(angle), math.cos(angle), 0.0


def heading_for(x, y):
    return math.degrees(math.atan2(-x, y))
