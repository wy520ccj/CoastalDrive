"""Vehicle dimensions are metres; steering angles are degrees."""

import math
from dataclasses import dataclass, field

from vehicle_brakes import BrakeConfig
from vehicle_stability import StabilityConfig
from vehicle_traction import TractionConfig


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
    finite_drivetrain: bool = True  # 两模式共用真实曲轴/有限离合；false用于冻结旧机制A/B。
    front_drive_share: float = 0.0  # 0后驱、1前驱；中间值为开放中差的固定几何份额。
    differential_damping: tuple = (0., 0., 0.)  # 前轴/后轴/中差粘性系数，N·m·s/rad；默认开放。
    differential_capacity: tuple = (0., 0., 0.)  # 对应有限耦合容量，N·m；容量为0关闭端口。
    engine_inertia: float = .02  # 正常游戏起步响应标定的设计惯量，kg·m²；困难参考车取0.2，非实测。
    engine_axis: tuple = (0., 1., 0.)  # 车身局部曲轴正转方向。
    input_shaft_enabled: bool = True  # false冻结八维传动，仅供同机制旧/新对照。
    input_shaft_inertia: float = .005  # 游戏输入轴设计惯量kg·m²；参考车取.04，均非实测。
    input_shaft_axis: tuple = (0., 1., 0.)  # 壳体局部输入轴正转方向。
    synchronizer_capacity: float = 80.  # 输入轴侧有限同步锥容量N·m，设计值。
    engine_idle_response: float = .15
    engine_idle_torque_limit: float = 65.
    engine_redline_rpm: float = 6500.
    clutch_capacity: float = 300.  # Nm；有限干式离合容量。
    clutch_release_time: float = .08
    clutch_engage_time: float = .16
    clutch_launch_response: float = .30  # 起步曲轴反馈设计值；兼顾升速与早期有限传矩。
    max_speed: float = 160 / 3.6
    reverse_speed: float = 22 / 3.6
    reverse_force: float = 2200.0
    reverse_gear_ratio: float = 3.0
    game_speed_limits: bool = True
    brake_torque: float = 3643.2  # Total wheel braking torque, Nm.
    front_brake_share: float = 0.60
    braking: BrakeConfig = field(default_factory=BrakeConfig)
    traction: TractionConfig = field(default_factory=TractionConfig)
    stability: StabilityConfig = field(default_factory=StabilityConfig)
    steering_degrees: float = 26.0
    steering_rate: float = 50.0
    steering_response: float = 7.0
    steering_return: float = 10.0
    wheel_radius: float = 0.33
    wheel_inertia: float = 1.8  # 单轮轴向转动惯量，kg·m²。
    longitudinal_stiffness: float = 60000.0  # 静态单轮载荷下，N/单位滑转率。
    lateral_stiffness: float = 50000.0  # 静态单轮载荷下，N/rad。
    rear_lateral_stiffness: float = 50000.0  # 后轮可独立定义侧偏刚度，N/rad。
    tire_peak_load_exponent: float = .90  # 峰值力随轮荷次线性增长；1恢复原线性模型。
    longitudinal_load_exponent: float = .90
    lateral_load_exponent: float = .85
    tire_compliance: bool = True
    wheel_rotor_transport: bool = True  # 机械轮轴、有效力臂及同末状态轴承反力；false冻结旧机制。
    tire_contact_stiffness: float = 150000.0  # 二维各向同性接触区弹性，N/m。
    tire_contact_damping: float = 1000.0  # N·s/m。
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
    centered_collision_support: bool = True  # 沿CG投影切分原生Box，完整覆盖名义外廓；默认四块。
    # 车身/轮连接点以车辆设计地面为基准；创建刚体时转换到质心坐标。
    body_center_height: float = 0.84
    wheel_connection_height: float = 0.67
    center_of_mass_height: float = 0.42
    front_weight_share: float = 0.5
    body_inertia: tuple[float, float, float] | None = None
    angular_damping: float = 0.2
    suspension_travel: float = 0.2
    suspension_force_limit: float = 6000.0

    def __post_init__(self):
        if not math.isfinite(self.input_shaft_inertia) or self.input_shaft_inertia <= 0:
            raise ValueError("输入轴惯量须为有限正值")
        if not math.isfinite(self.synchronizer_capacity) or self.synchronizer_capacity < 0:
            raise ValueError("同步器容量须为有限非负值")
        if (len(self.input_shaft_axis) != 3 or any(not math.isfinite(v) for v in self.input_shaft_axis)
                or abs(sum(v * v for v in self.input_shaft_axis) - 1.) > 1e-12):
            raise ValueError("输入轴方向须为三维单位向量")
        if not 0 <= self.front_drive_share <= 1:
            raise ValueError("前轴驱动份额须在0到1之间")
        if self.front_drive_share != 0 and not self.finite_drivetrain:
            raise ValueError("前驱/四驱需要有限机械传动，旧对照分支仅支持后驱")
        if len(self.differential_damping) != 3 or len(self.differential_capacity) != 3:
            raise ValueError("限滑参数依次为前轴、后轴、中差的三项")
        if any(not math.isfinite(v) or v < 0 for v in (*self.differential_damping, *self.differential_capacity)):
            raise ValueError("限滑系数/容量须为有限非负值")
        enabled = tuple(c > 0 and limit > 0 for c, limit in zip(self.differential_damping, self.differential_capacity))
        if any(enabled) and not self.finite_drivetrain:
            raise ValueError("有限限滑需要有限机械传动")
        if enabled[0] and self.front_drive_share == 0 or enabled[1] and self.front_drive_share == 1:
            raise ValueError("未驱动轴不配置传动限滑")
        if enabled[2] and self.front_drive_share in (0, 1):
            raise ValueError("中差限滑仅用于四驱")

    @property
    def drive_weights(self):
        front = self.front_drive_share / 2
        rear = (1 - self.front_drive_share) / 2
        return front, front, rear, rear

    @property
    def driven_wheels(self):
        return tuple(i for i, weight in enumerate(self.drive_weights) if weight > 0)


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
