"""Small, display-independent state types shared by vehicle simulation code."""

import math
from dataclasses import dataclass, field

from vehicle_brakes import BrakeState
from vehicle_config import CAR
from vehicle_dynamics import DynamicsState
from vehicle_stability import StabilityState
from vehicle_traction import TractionState

FIXED_DT = 1 / 120


@dataclass(frozen=True)
class Control:
    steering: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    direction: int = 1

    def __post_init__(self):
        if not (-1 <= self.steering <= 1 and 0 <= self.throttle <= 1 and 0 <= self.brake <= 1):
            raise ValueError("Control values outside steering/throttle/brake ranges")
        if self.direction not in (-1, 1):
            raise ValueError("Control direction must select D or R")


@dataclass(frozen=True)
class VehicleCommand:
    """执行器请求：转向角为度，踏板为0～1，方向为−1/0/1；绕过输入辅助。"""

    steering: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    direction: int = 0
    wheel_brakes: tuple[float, float, float, float] | None = None

    def __post_init__(self):
        if self.wheel_brakes is not None and (
            len(self.wheel_brakes) != 4 or any(not 0 <= value <= 1 for value in self.wheel_brakes)
        ):
            raise ValueError("分轮制动请求须为四个0～1比例")


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
    force_grip: float = 0.0
    sample_grip: float = 0.0
    force_longitudinal_stiffness: float = 0.0
    force_lateral_stiffness: float = 0.0
    deformation_x: float = 0.0
    deformation_y: float = 0.0
    force_patch_kappa: float | None = None
    force_patch_alpha: float | None = None
    elastic_energy: float = 0.0
    material_dissipation: float = 0.0
    road_dissipation: float = 0.0
    elastic_numerical_dissipation: float = 0.0
    frame_dissipation: float = 0.0
    deformation_rate_x: float = 0.0
    deformation_rate_y: float = 0.0
    mechanical_axis: tuple = (0.0, 0.0, 0.0)
    rolling_radius: float | None = None
    gyro_angular_impulse: tuple = (0.0, 0.0, 0.0)
    steering_angular_impulse: tuple = (0.0, 0.0, 0.0)
    steering_work: float = 0.0
    longitudinal_angular_impulse: tuple = (0.0, 0.0, 0.0)
    lateral_angular_impulse: tuple = (0.0, 0.0, 0.0)


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
    brake_states: tuple[BrakeState, ...] = ()
    abs_enabled: bool = False
    tcs_enabled: bool = False
    traction_state: TractionState = field(default_factory=TractionState)
    esc_enabled: bool = False
    stability_state: StabilityState = field(default_factory=StabilityState)


def forward(heading):
    """Panda heading rotates local +Y toward -X; positive steering means right."""
    angle = math.radians(heading)
    return -math.sin(angle), math.cos(angle), 0.0


def heading_for(x, y):
    return math.degrees(math.atan2(-x, y))
