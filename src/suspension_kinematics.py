"""固定接触切平面上的有限转动行程与功共轭雅可比。"""

import math
from dataclasses import dataclass, replace

from rotor_dynamics import cross, dot


@dataclass(frozen=True)
class SupportPlane:
    """本子步真实接点的切平面；向量均在起点世界坐标中，不持有Bullet对象。"""
    hub: tuple
    direction: tuple
    normal: tuple
    length: float


def rotation_path(angular, dt, damping=0.):
    """匹配原生先阻尼再指数转动、运动限制及归一化；功仍对准备阶段角速共轭。"""
    speed = math.sqrt(dot(angular, angular))
    if speed == 0.:
        return (0., 0., 0.), 0., 1.
    damped_speed = speed * (1 - damping)**dt
    limited = min(damped_speed, math.pi / (4 * dt))
    sine_scale = (dt / 2 - dt**3 * limited**2 / 48 if limited < .001
                  else math.sin(limited * dt / 2) / limited)
    angle = 2 * math.atan2(damped_speed * sine_scale, math.cos(limited * dt / 2))
    return tuple(value / speed for value in angular), angle, angle / (dt * speed)


def rotated_path(vector, axis, angle, scale):
    """返回末向量及沿实际转动路径的共轭平均向量，使Δr=dt*Ω×平均r。"""
    if angle == 0.:
        return vector, vector
    parallel = tuple(dot(vector, axis) * value for value in axis)
    radial = tuple(vector[a] - parallel[a] for a in range(3))
    tangent = cross(axis, vector)
    sine, cosine = math.sin(angle), math.cos(angle)
    average_sine = sine / angle
    average_cosine = 2 * math.sin(angle / 2)**2 / angle
    end = tuple(parallel[a] + cosine * radial[a] + sine * tangent[a] for a in range(3))
    average = tuple(scale * (parallel[a] + average_sine * radial[a] + average_cosine * tangent[a]) for a in range(3))
    return end, average


def finite_contact_system(system, velocity, angular, dt):
    """l=p/a采用离散乘积恒等式；同一末速度决定行程、法向冲量和共轭力矩。"""
    if system.kinematics is None:
        return system  # 纯机械台架的输入明确为固定线性雅可比。
    axis, angle, scale = rotation_path(angular, dt, system.angular_damping)
    gradients, alignment, touching = [], [], []
    for plane in system.kinematics:
        if plane is None:
            gradients.append((0.,) * 6)
            alignment.append(None)
            touching.append(False)
            continue
        hub_end, hub_average = rotated_path(plane.hub, axis, angle, scale)
        direction_end, direction_average = rotated_path(plane.direction, axis, angle, scale)
        a0, a1 = -dot(plane.normal, plane.direction), -dot(plane.normal, direction_end)
        if a1 <= .1:
            # 末姿态越出既有近掠支撑资格，进入原无质量轮释放方程。
            gradients.append((0.,) * 6)
            alignment.append(a1)
            touching.append(False)
            continue
        p0 = a0 * plane.length
        p1 = p0 + dot(plane.normal, tuple(dt * velocity[a] + hub_end[a] - plane.hub[a] for a in range(3)))
        reciprocal = (1 / a0 + 1 / a1) / 2
        arm = tuple(reciprocal * hub_average[a] + (p0 + p1) / (2 * a0 * a1) * direction_average[a] for a in range(3))
        gradients.append(tuple(reciprocal * value for value in plane.normal) + cross(arm, plane.normal))
        alignment.append(1 / reciprocal)
        touching.append(True)
    return replace(system, gradients=tuple(gradients), alignment=tuple(alignment), touching=tuple(touching))


def advance_contact_geometry(system, compression, velocity, angular, dt):
    """独立台架连续机械子步沿同一切平面推进；正式世界子步随后重新读取实际接点。"""
    geometry = tuple(x - dt * sum(a * b for a, b in zip(g, tuple(velocity) + tuple(angular)))
                     for x, g in zip(system.geometry, system.gradients))
    if system.kinematics is None:
        return replace(system, compression=compression, geometry=geometry)
    axis, angle, scale = rotation_path(angular, dt, system.angular_damping)
    planes = []
    for plane, eligible, gradient in zip(system.kinematics, system.touching, system.gradients):
        if not eligible:
            planes.append(None)
            continue
        hub, _mean = rotated_path(plane.hub, axis, angle, scale)
        direction, _mean = rotated_path(plane.direction, axis, angle, scale)
        length = plane.length + dt * sum(a * b for a, b in zip(gradient, tuple(velocity) + tuple(angular)))
        planes.append(replace(plane, hub=hub, direction=direction, length=length))
    return replace(system, compression=compression, geometry=geometry, kinematics=tuple(planes))
