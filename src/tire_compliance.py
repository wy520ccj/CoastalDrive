"""接触区弹簧-阻尼与路面滑移串联，能量和速度共用同一变形状态。"""

import math

from mechanical_kernels import tire_contact_force, tire_contact_jacobian


def deformation_frame(tangent, normal):
    """变形用双精度正交基传递，避免Panda单精度轴反复投影改变储能。"""
    length = math.sqrt(sum(value * value for value in normal))
    up = tuple(value / length for value in normal)
    projection = sum(tangent[i] * up[i] for i in range(3))
    forward = tuple(tangent[i] - projection * up[i] for i in range(3))
    length = math.sqrt(sum(value * value for value in forward))
    forward = tuple(value / length for value in forward)
    lateral = (forward[1] * up[2] - forward[2] * up[1],
               forward[2] * up[0] - forward[0] * up[2],
               forward[0] * up[1] - forward[1] * up[0])
    return forward, lateral, up


def project_deformation(previous, frame, stiffness):
    elastic = tuple(sum(previous[i] * axis[i] for i in range(3)) for axis in frame[:2])
    normal_component = sum(previous[i] * frame[2][i] for i in range(3))
    return elastic, .5 * stiffness * normal_component**2


def world_deformation(elastic, frame):
    return tuple(elastic[0] * frame[0][i] + elastic[1] * frame[1][i] for i in range(3))


def deformation_state(force, previous, dt, stiffness, damping):
    rate = tuple((force[i] - stiffness * previous[i]) / (stiffness * dt + damping)
                 for i in range(2))
    deformation = tuple(previous[i] + dt * rate[i] for i in range(2))
    return deformation, rate


def contact_force(force, previous, slip, denominator, rolling, grip, cx, cy,
                  dt, stiffness, damping, shape, curvature):
    return tire_contact_force(force, previous, slip, denominator, rolling, grip, cx, cy,
                              dt, stiffness, damping, shape, curvature, math.hypot)


def energy_terms(force, previous, deformation, rate, patch, dt, stiffness, damping):
    energy = .5 * stiffness * sum(value * value for value in deformation)
    material = dt * damping * sum(value * value for value in rate)
    road = dt * sum(force[i] * patch[i] for i in range(2))
    numerical = .5 * stiffness * sum((deformation[i] - previous[i]) ** 2 for i in range(2))
    return energy, material, road, numerical


def contact_jacobian(force, previous, slip, slip_jacobian, denominator, denominator_gradient,
                     rolling, grip, cx, cy, dt, stiffness, damping, shape, curvature):
    """同一接触目标对Fx/Fy的解析导数；投影边界选取分段半光滑导数。"""
    return tire_contact_jacobian(force, previous, slip, slip_jacobian, denominator, denominator_gradient,
                                 rolling, grip, cx, cy, dt, stiffness, damping, shape, curvature, math.hypot)
