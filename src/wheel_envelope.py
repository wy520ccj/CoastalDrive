"""有限胎宽圆角圆柱的凸体距离与沿悬架方向的首次接触。"""

import math

from rotor_dynamics import cross, dot


def subtract(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cylinder_support(direction, axis, radius, half_width, shoulder, crown=0.):
    """圆柱内核加肩部球；radius和half_width都是含肩部的实际外廓。"""
    axial = dot(direction, axis)
    radial = subtract(direction, tuple(axial * x for x in axis))
    radial_length = math.sqrt(dot(radial, radial))
    length = math.sqrt(dot(direction, direction))
    half = half_width - shoulder
    axial_sign = (1. if axial > 0. else -1. if axial < 0. else 0.)
    x = (max(-half, min(half, axial * half**2 / (2 * crown * radial_length)))
         if crown and radial_length else half * axial_sign)
    tread_radius = radius - shoulder - crown * (x / half)**2
    return tuple(x * axis[i]
                 + (tread_radius * radial[i] / radial_length if radial_length else 0.)
                 + (shoulder * direction[i] / length if length else 0.) for i in range(3))


def crown_extent_secant(a0, a1, radius, half_width, shoulder, crown):
    """单位法线轴向投影的支持高度差商；同分区代数化简避免静载下相消。"""
    half, core = half_width - shoulder, radius - shoulder
    b0, b1 = math.sqrt(max(0., 1 - a0*a0)), math.sqrt(max(0., 1 - a1*a1))
    inside0 = crown > 0. and abs(a0) * half < 2 * crown * b0
    inside1 = crown > 0. and abs(a1) * half < 2 * crown * b1
    radial_secant = -(a0 + a1) / (b0 + b1) if b0 + b1 else 0.
    if inside0 and inside1:
        return core * radial_secant + half**2 / (4*crown) * ((a0 + a1) - a0*a0*radial_secant/b0) / b1
    if not inside0 and not inside1:
        axial_secant = ((abs(a1) - abs(a0)) / (a1 - a0) if a1 != a0
                        else math.copysign(1., a0) if a0 else 0.)
        return half * axial_secant + (core - crown) * radial_secant
    def height(a, b, inside):
        return core*b + half**2*a*a/(4*crown*b) if inside else half*abs(a) + (core-crown)*b
    return (height(a1,b1,inside1) - height(a0,b0,inside0)) / (a1 - a0)


def _segment(a, b):
    delta = subtract(b, a)
    length = dot(delta, delta)
    t = max(0., min(1., -dot(a, delta) / length)) if length else 0.
    return tuple(a[i] + t * delta[i] for i in range(3)), (1 - t, t)


def _triangle(a, b, c):
    ab, ac = subtract(b, a), subtract(c, a)
    normal = cross(ab, ac)
    norm = dot(normal, normal)
    if norm:
        v = dot(cross(tuple(-x for x in a), ac), normal) / norm
        w = dot(cross(ab, tuple(-x for x in a)), normal) / norm
        if v >= 0. and w >= 0. and v + w <= 1.:
            weights = (1 - v - w, v, w)
            return tuple(sum(weights[j] * p[i] for j, p in enumerate((a, b, c))) for i in range(3)), weights
    choices = []
    for i, j in ((0, 1), (0, 2), (1, 2)):
        p, weights = _segment((a, b, c)[i], (a, b, c)[j])
        expanded = [0.] * 3
        expanded[i], expanded[j] = weights
        choices.append((p, tuple(expanded)))
    return min(choices, key=lambda value: dot(value[0], value[0]))


def _closest(vertices):
    points = tuple(v[0] for v in vertices)
    if len(points) == 1:
        return points[0], (1.,)
    if len(points) == 2:
        return _segment(*points)
    if len(points) == 3:
        return _triangle(*points)
    a, b, c, d = points
    ab, ac, ad = subtract(b, a), subtract(c, a), subtract(d, a)
    det = dot(ab, cross(ac, ad))
    if det:
        rhs = tuple(-x for x in a)
        u, v, w = dot(rhs, cross(ac, ad)) / det, dot(ab, cross(rhs, ad)) / det, dot(ab, cross(ac, rhs)) / det
        if u >= 0. and v >= 0. and w >= 0. and u + v + w <= 1.:
            return (0.,) * 3, (1 - u - v - w, u, v, w)
    choices = []
    for face in ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)):
        p, weights = _triangle(*(points[i] for i in face))
        expanded = [0.] * 4
        for i, weight in zip(face, weights):
            expanded[i] = weight
        choices.append((p, tuple(expanded)))
    return min(choices, key=lambda value: dot(value[0], value[0]))


def cylinder_box_distance(center, axis, half, radius, half_width, shoulder, crown=0.):
    """GJK给出圆柱内核与Box内核距离、法线和Box见证点；肩部在扫掠时合并。"""
    def support(direction):
        offset = cylinder_support(tuple(-x for x in direction), axis, radius - shoulder,
                                  half_width - shoulder, 0., crown)
        box = tuple(math.copysign(h, x) if x else 0. for h, x in zip(half, direction))
        return subtract(tuple(center[i] + offset[i] for i in range(3)), box), box

    direction = subtract(center, tuple(max(-h, min(h, x)) for h, x in zip(half, center)))
    if not dot(direction, direction):
        return 0., (0., 0., 1.), center
    vertices = [support(direction)]
    point, weights = _closest(vertices)
    for _ in range(96):
        squared = dot(point, point)
        if squared < 1e-24:
            return 0., (0., 0., 1.), center
        candidate = support(point)
        if squared - dot(point, candidate[0]) <= 1e-13 * max(1., squared):
            distance = math.sqrt(squared)
            witness = tuple(sum(w * vertex[1][i] for w, vertex in zip(weights, vertices)) for i in range(3))
            return distance, tuple(x / distance for x in point), witness
        vertices = [vertex for vertex, weight in zip(vertices, weights) if weight > 1e-15]
        vertices.append(candidate)
        point, weights = _closest(vertices)
    raise ArithmeticError("圆柱/Box凸体距离未收敛")


def cylinder_box_entry(start, end, half, margin, axis, radius, half_width, shoulder, crown=0.):
    """保守推进到圆角外廓；不增加查询刚体或改变碰撞世界。"""
    from suspension_geometry import box_interval
    extent = tuple(abs(axis[i]) * (half_width - shoulder)
                   + (radius - shoulder) * math.sqrt(max(0., 1. - axis[i]**2)) + shoulder + margin for i in range(3))
    interval = box_interval(start, end, tuple(h + e for h, e in zip(half, extent)))
    if interval is None or interval[0] > 1. or interval[1] < 0.:
        return None
    velocity = subtract(end, start)
    # 有效平面见证点直接解析求交；棱角才进入凸体距离迭代。
    for i in range(3):
        for sign in (-1., 1.):
            normal = tuple(sign if a == i else 0. for a in range(3))
            speed = sign * velocity[i]
            support = cylinder_support(normal, axis, radius, half_width, shoulder, crown)
            distance = sign * start[i] - half[i] - margin - dot(normal, support)
            if speed >= 0. or distance < 0.:
                continue
            fraction = -distance / speed
            if not 0. <= fraction <= 1.:
                continue
            point = tuple(start[a] + fraction*velocity[a] - support[a] for a in range(3))
            if all(abs(point[a]) <= half[a] for a in range(3) if a != i):
                return fraction, normal, point
    fraction = 0.
    for _ in range(64):
        center = tuple(start[i] + fraction * velocity[i] for i in range(3))
        distance, normal, witness = cylinder_box_distance(center, axis, half, radius, half_width, shoulder, crown)
        gap = distance - margin - shoulder
        if fraction == 0. and gap < -1e-9:
            return None
        if gap <= 1e-9:
            return fraction, normal, tuple(witness[i] + margin * normal[i] for i in range(3))
        closing = -dot(normal, velocity)
        if closing <= 0.:
            return None
        fraction += gap / closing
        if fraction > 1.:
            return None
    raise ArithmeticError("圆柱/Box悬架扫掠未收敛")
