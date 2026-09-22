"""Road-load estimates in SI units; Bullet already applies gravity and suspension."""

import math
from dataclasses import dataclass

from vehicle_config import CAR


@dataclass(frozen=True)
class DynamicsState:
    aerodynamic_force: float = 0.0
    rolling_force: float = 0.0
    grade_force: float = 0.0
    front_load: float = 0.0
    rear_load: float = 0.0
    yaw_rate: float = 0.0
    sideslip: float = 0.0
    traction_limited: bool = False


def aerodynamic_force(speed, config=CAR):
    return 0.5 * config.air_density * config.drag_coefficient * config.frontal_area * speed * speed


def axle_loads(acceleration, pitch, config=CAR):
    angle = math.radians(pitch)
    normal = config.mass * 9.81 * max(0, math.cos(angle))
    transfer = (
        config.mass
        * config.center_of_mass_height
        / config.wheelbase
        * (acceleration + 9.81 * math.sin(angle))
    )
    front = max(0, min(normal, normal * config.front_weight_share - transfer))
    return front, normal - front
