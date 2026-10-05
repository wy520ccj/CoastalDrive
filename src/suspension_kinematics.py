"""真实Box曲面或接触切平面上的有限行程与功共轭雅可比。"""

import math
from dataclasses import dataclass, replace

from rotor_dynamics import cross, dot
from suspension_geometry import BoxSurface, sphere_box_entry


@dataclass(frozen=True)
class SupportPlane:
    """本子步接点及可用的真实曲面；向量均在起点世界坐标中，不持有Bullet对象。"""
    hub: tuple
    direction: tuple
    normal: tuple
    length: float
    surface: BoxSurface | None = None


def curved_endpoint(contact, hub_end, direction_end, velocity, dt):
    """末姿态从同一Box球包络求真实交点；距离平方差商给出跨面/棱/角割线法线。"""
    surface = contact.surface
    hub = tuple(hub_end[a] + dt * velocity[a] for a in range(3))
    start = surface.local(tuple(hub[a] - surface.wheel_radius * direction_end[a] for a in range(3)))
    end = surface.local(tuple(hub[a] + surface.reach * direction_end[a] for a in range(3)))
    found = sphere_box_entry(start, end, surface.half, surface.radius)
    if found is None:
        return None  # 末姿态没有入射接点，轮胎进入原自由释放；车身碰撞仍由Bullet处理。
    fraction, endpoint_normal = found
    length = -surface.wheel_radius + fraction * (surface.wheel_radius + surface.reach)
    endpoint_normal = surface.world_vector(endpoint_normal)
    norm = math.sqrt(dot(endpoint_normal, endpoint_normal))
    endpoint_normal = tuple(value / norm for value in endpoint_normal)
    if -dot(endpoint_normal, direction_end) <= .1:
        return None
    c0 = surface.local(tuple(contact.hub[a] + contact.length * contact.direction[a] for a in range(3)))
    c1 = tuple(start[a] + fraction * (end[a] - start[a]) for a in range(3))
    secant = []
    for x0, x1, half in zip(c0, c1, surface.half):
        z0, z1 = max(-half, min(half, x0)), max(-half, min(half, x1))
        y0, y1 = x0 - z0, x1 - z1
        # 同分区直接化简平方差，避免极小位移下的相消；跨分区仍用完整恒等式。
        secant.append(y0 + y1 if z0 == z1 else 0. if y0 == y1 == 0.
                      else (y1 - y0) / (x1 - x0) * (y1 + y0))
    normal = surface.world_vector(secant)
    norm = math.sqrt(dot(normal, normal))
    return length, tuple(value / norm for value in normal)


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
    """曲面割线或l=p/a的离散恒等式；同一末速度决定行程、法向冲量和力矩。"""
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
        if plane.surface is not None:
            endpoint = curved_endpoint(plane, hub_end, direction_end, velocity, dt)
            if endpoint is None:
                gradients.append((0.,) * 6)
                alignment.append(None)
                touching.append(False)
                continue
            length, normal = endpoint
            a = -dot(normal, tuple((x + y) / 2 for x, y in zip(plane.direction, direction_end)))
            if a <= .1:
                gradients.append((0.,) * 6)
                alignment.append(a)
                touching.append(False)
                continue
            arm = tuple(hub_average[b] + (plane.length + length) / 2 * direction_average[b] for b in range(3))
            gradients.append(tuple(value / a for value in normal) + tuple(value / a for value in cross(arm, normal)))
            alignment.append(a)
            touching.append(True)
            continue
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
    """独立台架连续子步推进支撑几何；正式世界子步随后重新读取实际接点。"""
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
        surface = (replace(plane.surface, offset=plane.surface.local(tuple(dt * value for value in velocity)))
                   if plane.surface is not None else None)
        planes.append(replace(plane, hub=hub, direction=direction, length=length, surface=surface))
    return replace(system, compression=compression, geometry=geometry, kinematics=tuple(planes))
