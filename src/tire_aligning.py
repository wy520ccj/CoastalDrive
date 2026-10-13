"""均匀压力刷毛的受力中心；实际接触力仍由同一隐式本构求解。"""

import math
from dataclasses import replace

from rotor_dynamics import cross, dot
from tire_properties import tire_grip, tire_stiffness
from wheel_dynamics import Mobility


def brush_trail(half_length, kappa, alpha, grip, cx, cy, speed, minimum_speed):
    """前缘零变形、沿接触长度线性增长；滑动段在局部库仑限值饱和。"""
    if grip <= 0. or abs(speed) < minimum_speed:
        return 0.
    trial = math.hypot(cx * kappa, cy * math.tan(alpha))
    adhesion = 1. / max(1., 2. * trial / grip)
    trail = half_length * adhesion * (3. - 2. * adhesion) / (3. * (2. - adhesion))
    return math.copysign(trail, speed)


def aligning_frame(frame, previous, config, inverse_inertia, steering_velocity):
    """冻结上个子步的刷毛分布几何；重新计算共轭速度/力矩与对称Mobility。"""
    if not config.tire_aligning_enabled:
        return frame
    # 初始化滚动试验没有已求解滑移；这时按零滑移的黏着分布起步。
    kappa = 0. if previous.force_patch_kappa is None else previous.force_patch_kappa
    alpha = 0. if previous.force_patch_alpha is None else previous.force_patch_alpha
    # 悬架候选的load尚为零；几何冻结必须读取上一真实施力子步的轮荷。
    load = previous.normal_load if frame.supported and previous.road_support else 0.
    cx, cy = tire_stiffness(load, config)
    trail = brush_trail(config.tire_contact_half_length, kappa, alpha,
                        tire_grip(load, frame.mu, config), cx, cy,
                        previous.longitudinal_speed, config.static_contact_speed)
    point = tuple(frame.point[a] - trail * frame.tangent[a] for a in range(3))
    moment_y = cross(point, frame.axle)
    ry = tuple(dot(row, moment_y) for row in inverse_inertia)
    mx, rx, rt = frame.moment_x, frame.response_x, frame.response_t
    mobility = Mobility(1. / config.mass + dot(mx, rx), dot(mx, ry), dot(mx, rt),
                        1. / config.mass + dot(moment_y, ry), dot(moment_y, rt),
                        dot(frame.spin_axis, rt))
    offset = tuple(-trail * value for value in frame.tangent)
    bias = dot(cross(steering_velocity, offset), frame.axle)
    return replace(frame, point=point, response_y=ry, mobility=mobility,
                   pneumatic_trail=trail, steering_lateral_velocity=bias)
