"""射线接触几何与机械轮轴分离；轮毂仍来自原生接点和名义轮半径。"""

import math

from rotor_dynamics import cross, dot
from wheel_envelope import cylinder_support


def unit(vector):
    length = math.sqrt(dot(vector, vector))
    return tuple(value / length for value in vector)


def mechanical_axis(right, forward, angle):
    """正转向为右转；先在双精度下旋转车身基轴，再归一化真实机械右轴。"""
    theta = math.radians(angle)
    return unit(tuple(math.cos(theta) * right[a] - math.sin(theta) * forward[a] for a in range(3)))


def contact_geometry(axis, normal, point, radius, *, width=None, shoulder=0., crown=0.):
    """广义纵速V·t+Ω·(p×t−ρe)与实际表面速仅差ρω。"""
    axis, normal = unit(axis), unit(normal)
    tangent = unit(cross(normal, axis))
    lateral = cross(tangent, normal)
    offset = (tuple(-value for value in cylinder_support(normal, axis, radius, width / 2, shoulder, crown))
              if width is not None else tuple(-radius * value for value in normal))
    rolling_radius = dot(axis, cross(offset, tangent))
    moment_x = tuple(cross(point, tangent)[a] - rolling_radius * axis[a] for a in range(3))
    return axis, (tangent, lateral, normal), rolling_radius, moment_x
