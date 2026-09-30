"""道路载荷采用 SI 单位；重力与悬架仍由 Bullet 施加。"""

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
    road_grade: float | None = None


def contact_grade(heading, normals):
    """支撑法线给出车头方向的道路坡度；无接触时坡度没有定义。"""
    if not normals:
        return None
    nx, ny, nz = (sum(n[axis] for n in normals) for axis in range(3))
    angle = math.radians(heading)
    along = nx * -math.sin(angle) + ny * math.cos(angle)
    return math.degrees(math.atan2(-along, nz))


def aerodynamic_force(speed, config=CAR):
    return 0.5 * config.air_density * config.drag_coefficient * config.frontal_area * speed * speed


def axle_loads(acceleration, grade, config=CAR):
    angle = math.radians(grade)
    normal = config.mass * 9.81 * max(0, math.cos(angle))
    transfer = (
        config.mass
        * config.center_of_mass_height
        / config.wheelbase
        * (acceleration + 9.81 * math.sin(angle))
    )
    front = max(0, min(normal, normal * config.front_weight_share - transfer))
    return front, normal - front
