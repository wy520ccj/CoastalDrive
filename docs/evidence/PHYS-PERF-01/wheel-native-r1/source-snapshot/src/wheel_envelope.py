"""有限胎宽圆角圆柱的凸体距离与沿悬架方向的首次接触。"""

import math
from itertools import combinations

import numpy as np
import wheel_contact_kernels

from rotor_dynamics import dot


def subtract(a, b):
    return tuple(x - y for x, y in zip(a, b))


cylinder_support = wheel_contact_kernels.cylinder_support

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


def _difference_of_products(a, b, c, d):
    ab, cd = a*b, c*d
    return math.fsum((ab, -cd, math.fma(a, b, -ab), -math.fma(c, d, -cd)))


def _cross_precise(a, b):
    return tuple(_difference_of_products(a[i], b[j], a[j], b[i])
                 for i, j in ((1, 2), (2, 0), (0, 1)))


def _cylinder_point_delta(relative, axis, radius, half_width, crown):
    """点到胎冠内核的分离向量；轴向投影解凸距离的一维驻点。"""
    axis_squared = dot(axis, axis)
    axis_length = math.sqrt(axis_squared)
    unit_axis = tuple(x/axis_length for x in axis)
    axial = math.fsum(x*u for x, u in zip(relative, axis)) / axis_length
    radial = tuple(x/axis_squared for x in _cross_precise(axis, _cross_precise(relative, axis)))
    rho = math.sqrt(math.fsum(x*x for x in radial))
    k = crown / half_width**2
    q = max(-half_width, min(half_width, axial))

    def derivative(q):
        return q - axial + 2*k*q*max(rho - radius + k*q*q, 0.)

    if derivative(-half_width) >= 0.:
        q = -half_width
    elif derivative(half_width) <= 0.:
        q = half_width
    else:
        low, high = -half_width, half_width
        for _ in range(64):
            gap = max(rho - radius + k*q*q, 0.)
            value = q - axial + 2*k*q*gap
            if value == 0.:
                break
            slope = 1 + 2*k*gap + (4*k*k*q*q if gap else 0.)
            candidate = q - value/slope
            if candidate == q:
                break
            if value > 0.:
                high = q
            else:
                low = q
            if not low < candidate < high:
                candidate = (low + high) / 2
            q = candidate
            if q == low or q == high:
                break
    gap = max(rho - radius + k*q*q, 0.)
    return tuple((axial-q)*unit_axis[i] + (gap*radial[i]/rho if rho else 0.) for i in range(3))


def _cylinder_edge_distance(center, axis, a, b, radius, half_width, crown):
    """固定有限边到胎冠内核的最近点；边参数驻点保持接触法线平滑。"""
    edge = subtract(b, a)

    def evaluate(t):
        relative = tuple(math.fsum((a[i], -center[i], t*edge[i])) for i in range(3))
        delta = _cylinder_point_delta(relative, axis, radius, half_width, crown)
        return delta, math.fsum(x*y for x, y in zip(delta, edge))

    da, ga = evaluate(0.)
    db, gb = evaluate(1.)
    if ga >= 0.:
        t, delta = 0., da
    elif gb <= 0.:
        t, delta = 1., db
    else:
        low, high = 0., 1.
        for _ in range(64):
            t = (low + high) / 2
            delta, value = evaluate(t)
            if value == 0. or t == low or t == high:
                break
            if value > 0.:
                high = t
            else:
                low = t
    distance = math.sqrt(math.fsum(x*x for x in delta))
    return (distance, tuple(-x/distance for x in delta) if distance else (0., 0., 1.),
            tuple(math.fsum((a[i], t*edge[i])) for i in range(3)))


def _cylinder_face_candidates(center, axis, features, radius, half_width, crown):
    """有限三角面的投影候选；实际内点与全凸体支持判据共同确认最近面。"""
    faces = []
    for a, b, c in combinations(features, 3):
        ab, ac = subtract(b, a), subtract(c, a)
        normal = _cross_precise(ab, ac)
        length = math.sqrt(math.fsum(x*x for x in normal))
        if length:
            faces.append((length, a, ab, ac, normal))
    # 同一裁剪面优先用面积最大的三角形，避免短边放大法线的舍入误差。
    for length, a, ab, ac, normal in sorted(faces, reverse=True):
        normal = tuple(x/length for x in normal)
        if math.fsum(n*(x-y) for n, x, y in zip(normal, center, a)) < 0.:
            normal = tuple(-x for x in normal)
        offset = cylinder_support(tuple(-x for x in normal), axis, radius, half_width, 0., crown)
        relative = tuple(math.fsum((center[i], -a[i], offset[i])) for i in range(3))
        distance = math.fsum(n*x for n, x in zip(normal, relative))
        if distance <= 0.:
            continue
        body_relative = tuple(relative[i] - distance*normal[i] for i in range(3))
        coordinates, _residual, rank, _singular = np.linalg.lstsq(
            np.asarray((ab, ac)).T, np.asarray(body_relative), rcond=None)
        v, w = coordinates
        if rank == 2 and v >= 0. and w >= 0. and v + w <= 1.:
            yield distance, normal, tuple(math.fsum((a[i], v*ab[i], w*ac[i])) for i in range(3))


def _triangle(a, b, c):
    ab, ac = subtract(b, a), subtract(c, a)
    # 瘦长道路边的单纯形会同时包含40m和微米级边；SVD投影避免行列式相消。
    coordinates, _residual, rank, _singular = np.linalg.lstsq(np.asarray((ab,ac)).T, -np.asarray(a), rcond=None)
    v, w = coordinates
    if rank == 2 and v >= 0. and w >= 0. and v + w <= 1.:
        weights = (1 - v - w, v, w)
        # 近共线边的叉积由接近的乘积相减；保留乘法低位，避免错误法线卡住GJK。
        normal = _cross_precise(ab, ac)
        height = math.fsum(x*y for x,y in zip(normal,a)) / dot(normal,normal)
        # 投影点直接由平面法线生成，避免把40m顶点的重心和当作微米级距离。
        return tuple(height*x for x in normal), weights
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
    coordinates, _residual, rank, _singular = np.linalg.lstsq(np.asarray((ab,ac,ad)).T, -np.asarray(a), rcond=None)
    u, v, w = coordinates
    if rank == 3 and u >= 0. and v >= 0. and w >= 0. and u + v + w <= 1.:
        weights = (1 - u - v - w, u, v, w)
        return (0.,) * 3, weights
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
    def support_body(direction):
        return tuple(math.copysign(h, x) if x else 0. for h, x in zip(half, direction))

    return convex_distance(center, axis, support_body, radius, half_width, shoulder, crown)


def convex_distance(center, axis, support_body, radius, half_width, shoulder, crown):
    """轮胎内核对任意固定凸体的最近见证点；不持有物理世界。"""
    def support(direction):
        offset = cylinder_support(tuple(-x for x in direction), axis, radius - shoulder,
                                  half_width - shoulder, 0., crown)
        box = support_body(direction)
        # 先形成相对几何，保留小外廓量；大坐标加胎面偏移后再相减会丢低位。
        return tuple(math.fsum((center[i], -box[i], offset[i])) for i in range(3)), box

    direction = subtract(center, support_body(center))
    if not dot(direction, direction):
        direction = (0., 0., 1.)
    vertices = [support(direction)]
    point, weights = _closest(vertices)
    for _ in range(96):
        squared = dot(point, point)
        if squared < 1e-24:
            return 0., (0., 0., 1.), center
        features = tuple(dict.fromkeys(v[1] for v, w in zip(vertices, weights) if w > 0.))
        if len(features) <= 2:
            refined = _cylinder_edge_distance(center, axis, features[0], features[-1],
                                              radius-shoulder, half_width-shoulder, crown)
            refined_point = tuple(refined[0]*n for n in refined[1])
            refined_squared = dot(refined_point, refined_point)
            candidate = support(refined_point)
            if refined_squared - dot(refined_point, candidate[0]) <= 1e-13 * max(1., refined_squared):
                return refined
        body_pool = tuple(dict.fromkeys(v[1] for v in vertices))
        if len(body_pool) >= 3:
            for refined in _cylinder_face_candidates(center, axis, body_pool,
                                                     radius-shoulder, half_width-shoulder, crown):
                refined_point = tuple(refined[0]*n for n in refined[1])
                refined_squared = dot(refined_point, refined_point)
                candidate = support(refined_point)
                if refined_squared - dot(refined_point, candidate[0]) <= 1e-13 * max(1., refined_squared):
                    return refined
        candidate = support(point)
        if squared - dot(point, candidate[0]) <= 1e-13 * max(1., squared):
            features = tuple(dict.fromkeys(v[1] for v, w in zip(vertices, weights) if w > 0.))
            if len(features) <= 2:
                # 距离间隙不足以保证曲面法线精度；用实际角点/边投影再核对同一支持判据。
                refined = _cylinder_edge_distance(center, axis, features[0], features[-1],
                                                  radius-shoulder, half_width-shoulder, crown)
                refined_point = tuple(refined[0]*n for n in refined[1])
                refined_squared = dot(refined_point, refined_point)
                candidate = support(refined_point)
                if refined_squared - dot(refined_point, candidate[0]) <= 1e-13 * max(1., refined_squared):
                    return refined
                vertices = [(refined_point, refined[2]), candidate]
                point, weights = _closest(vertices)
                continue
            distance = math.sqrt(squared)
            witness = tuple(sum(w * vertex[1][i] for w, vertex in zip(weights, vertices)) for i in range(3))
            return distance, tuple(x / distance for x in point), witness
        vertices = [vertex for vertex, weight in zip(vertices, weights) if weight > 1e-15]
        vertices.append(candidate)
        point, weights = _closest(vertices)
    raise ArithmeticError(f"圆柱/固定凸体距离未收敛：center={center}, axis={axis}, point={point}, gap={squared - dot(point,candidate[0]):g}, vertices={vertices}")


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
                anchor = tuple(sign * half[i] if a == i else 0. for a in range(3))
                return fraction, normal, point, (anchor, margin)
    fraction = 0.
    for _ in range(64):
        center = tuple(start[i] + fraction * velocity[i] for i in range(3))
        distance, normal, witness = cylinder_box_distance(center, axis, half, radius, half_width, shoulder, crown)
        gap = distance - margin - shoulder
        if fraction == 0. and gap < -1e-9:
            return None
        if gap <= 1e-9:
            return fraction, normal, tuple(witness[i] + margin * normal[i] for i in range(3)), None
        closing = -dot(normal, velocity)
        if closing <= 0.:
            return None
        fraction += gap / closing
        if fraction > 1.:
            return None
    raise ArithmeticError("圆柱/Box悬架扫掠未收敛")
