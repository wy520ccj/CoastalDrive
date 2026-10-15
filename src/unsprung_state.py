"""独立轮心的完成步只读观测；不保存第二套积分姿态。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnsprungState:
    sprung_mass: float
    sprung_center_reference: tuple
    sprung_position: tuple
    sprung_velocity: tuple
    wheel_masses: tuple
    wheel_positions: tuple
    wheel_velocities: tuple
    displacement: tuple
    relative_velocity: tuple
    radial_deflection: tuple
    force_radial_deflection: tuple
    normal_force: tuple
    total_center_position: tuple
    total_center_velocity: tuple
    mechanical_energy: float
    native_velocity_defect: tuple
    force_tick: int
    sprung_acceleration: tuple | None = None
    total_center_acceleration: tuple | None = None
    wheel_accelerations: tuple | None = None
