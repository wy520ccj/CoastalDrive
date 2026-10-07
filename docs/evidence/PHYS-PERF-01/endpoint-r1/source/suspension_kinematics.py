"""真实Box曲面或接触切平面上的有限行程与功共轭雅可比。"""

import math
from dataclasses import dataclass, replace

from wheel_contact_kernels import cylinder_endpoint as endpoint_kernel
from wheel_contact_kernels import rotated_path

from rotor_dynamics import cross, dot
from suspension_geometry import BoxSurface, CylinderSurface, sphere_box_entry
from wheel_envelope import crown_extent_secant, cylinder_support


@dataclass(frozen=True)
class SupportPlane:
    """本子步接点及可用的真实曲面；向量均相对起点车身原点。"""
    hub: tuple
    direction: tuple
    normal: tuple
    length: float
    surface: BoxSurface | None = None
    point: tuple | None = None


def cylinder_endpoint(contact, hub_end, hub_average, direction_end, direction_average,
                      rotation_axis, angle, scale, velocity, angular, dt):
    """真实圆柱末接点与离散行程梯度；功恒等式包含胎肩随车身转动的位移。"""
    return endpoint_kernel(contact, hub_end, hub_average, direction_end, direction_average,
                           rotation_axis, angle, scale, velocity, angular, dt, face_extension_difference)


def face_extension_difference(contact, normal, face, wheel_axis, hub_average, direction_average,
                              rotation_axis, angle, scale, velocity, angular, dt):
    """跨有限面时直接算Δl；固定高度余量与小运动分开，低速不减两个扫掠行程。"""
    surface = contact.surface
    anchor, margin = face
    old_axis = surface.wheel_axis
    old_support = cylinder_support(normal, old_axis, surface.wheel_radius,
                                   surface.width / 2, surface.shoulder, surface.crown)
    clearance = math.fsum([*(normal[a] * (contact.hub[a] - anchor[a]) for a in range(3)),
                           *(-normal[a] * old_support[a] for a in range(3)),
                           -margin, dot(normal, contact.direction) * contact.length])
    axis_length = math.sqrt(dot(old_axis, old_axis))
    normal_length = math.sqrt(dot(normal, normal))
    extent = normal_length * crown_extent_secant(
        dot(normal, old_axis) / (normal_length * axis_length),
        dot(normal, wheel_axis) / (normal_length * axis_length),
        surface.wheel_radius, surface.width / 2, surface.shoulder, surface.crown)
    wheel_average = rotated_path(old_axis, rotation_axis, angle, scale)[1]
    hub_rate, direction_rate, axis_rate = (cross(angular, vector)
                                          for vector in (hub_average, direction_average, wheel_average))
    transport = tuple(velocity[a] + hub_rate[a] + contact.length * direction_rate[a]
                      - extent * axis_rate[a] / axis_length for a in range(3))
    direction_end = rotated_path(contact.direction, rotation_axis, angle, scale)[0]
    return math.fsum((clearance, dt * dot(normal, transport))) / -dot(normal, direction_end)


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
        if isinstance(plane.surface, CylinderSurface):
            endpoint = cylinder_endpoint(plane, hub_end, hub_average, direction_end, direction_average,
                                         axis, angle, scale, velocity, angular, dt)
            gradients.append(endpoint[0] if endpoint else (0.,) * 6)
            alignment.append(endpoint[1] if endpoint else None)
            touching.append(endpoint is not None)
            continue
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
        if isinstance(surface, CylinderSurface):
            wheel_axis, _average = rotated_path(surface.wheel_axis, axis, angle, scale)
            surface = replace(surface, wheel_axis=wheel_axis)
        point = tuple(plane.point[a] - dt * velocity[a] for a in range(3)) if plane.point is not None else None
        planes.append(replace(plane, hub=hub, direction=direction, length=length, surface=surface, point=point))
    return replace(system, compression=compression, geometry=geometry, kinematics=tuple(planes))
