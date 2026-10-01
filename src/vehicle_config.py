"""Vehicle dimensions are metres; steering angles are degrees."""

from dataclasses import dataclass, field

from vehicle_brakes import BrakeConfig


@dataclass(frozen=True)
class VehicleConfig:
    mass: float = 1200.0
    # 游戏发动机曲线；引入四轮转动惯量后整体提高5.5%，保留既有动力性目标。
    torque_curve: tuple = (
        (900, 116.05),
        (1800, 174.075),
        (3200, 211),
        (4500, 200.45),
        (6000, 158.25),
        (6500, 0),
    )
    gear_ratios: tuple = (3.25, 2.05, 1.45, 1.10, 0.88)
    final_drive: float = 3.7
    drivetrain_efficiency: float = 0.88
    idle_rpm: float = 900.0
    shift_time: float = 0.28
    torque_response: float = 0.12
    engine_braking: float = 24.0  # Approximate closed-throttle torque at the crank, Nm.
    max_speed: float = 160 / 3.6
    reverse_speed: float = 22 / 3.6
    reverse_force: float = 2200.0
    reverse_gear_ratio: float = 3.0
    game_speed_limits: bool = True
    brake_torque: float = 3643.2  # Total wheel braking torque, Nm.
    front_brake_share: float = 0.60
    braking: BrakeConfig = field(default_factory=BrakeConfig)
    steering_degrees: float = 26.0
    steering_rate: float = 50.0
    steering_response: float = 7.0
    steering_return: float = 10.0
    wheel_radius: float = 0.33
    wheel_inertia: float = 1.8  # 单轮轴向转动惯量，kg·m²。
    longitudinal_stiffness: float = 60000.0  # 静态单轮载荷下，N/单位滑转率。
    lateral_stiffness: float = 50000.0  # 静态单轮载荷下，N/rad。
    rear_lateral_stiffness: float = 50000.0  # 后轮可独立定义侧偏刚度，N/rad。
    tire_shape: float = 1.9
    tire_curvature: float = 0.97
    slip_speed: float = 1.0  # 低速滑移分母的模型尺度，m/s。
    static_contact_speed: float = .25  # 低速无滑移接触的切换尺度，m/s。
    tire_substeps: int = 2
    suspension_stiffness: float = 40.0
    suspension_compression: float = 4.4
    suspension_relaxation: float = 2.3
    air_density: float = 1.225  # kg/m³
    drag_coefficient: float = 0.32
    frontal_area: float = 2.142857142857143  # m²; preserves the previous Cd*A product.
    rolling_coefficient: float = 160 / (1200 * 9.81)
    grass_rolling_coefficient: float = 900 / (1200 * 9.81)
    road_friction: float = 1.1
    grass_friction: float = 0.45
    wheelbase: float = 2.2
    track_width: float = 1.68
    # 同时覆盖当前车型的车身和外露车轮，玩家与交通车共用这组尺寸。
    collision_half_width: float = 1.05
    collision_half_length: float = 2.15
    collision_half_height: float = 0.42
    # 车身/轮连接点以车辆设计地面为基准；创建刚体时转换到质心坐标。
    body_center_height: float = 0.84
    wheel_connection_height: float = 0.67
    center_of_mass_height: float = 0.42
    front_weight_share: float = 0.5
    body_inertia: tuple[float, float, float] | None = None
    angular_damping: float = 0.2
    suspension_travel: float = 0.2
    suspension_force_limit: float = 6000.0


CAR = VehicleConfig()


def wheel_hubs(config=CAR):
    """前轴静态份额定义质心纵向位置；高度改变真实轮连接点力臂。"""
    return tuple(
        (side * config.track_width / 2,
         config.wheelbase * ((1 if axle == 1 else 0) - config.front_weight_share),
         config.wheel_connection_height - config.center_of_mass_height)
        for axle in (1, -1) for side in (-1, 1)
    )


def body_center(config=CAR):
    return (0.0, config.wheelbase * (.5 - config.front_weight_share),
            config.body_center_height - config.center_of_mass_height)


WHEEL_HUBS = wheel_hubs()
