"""有限胎宽圆角圆柱的凸体距离与沿悬架方向的首次接触。"""

import math
from itertools import combinations

import numpy as np
import wheel_contact_kernels

from rotor_dynamics import dot

subtract = wheel_contact_kernels.subtract


cylinder_support = wheel_contact_kernels.cylinder_support

crown_extent_secant = wheel_contact_kernels.crown_extent_secant


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


# 原胎冠驻点与有限边二分，迭代上限和精确部分和保持。
_cylinder_point_delta = wheel_contact_kernels.cylinder_point_delta
_cylinder_edge_distance = wheel_contact_kernels.cylinder_edge_distance


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


def _simplex_coordinates(columns, rhs):
    """近共线及四面体单纯形沿用原SVD，不以普通行列式替代其精度。"""
    coordinates, _residual, rank, _singular = np.linalg.lstsq(
        np.asarray(columns).T, np.asarray(rhs), rcond=None)
    return tuple(coordinates), int(rank)


def cylinder_box_distance(center, axis, half, radius, half_width, shoulder, crown=0.):
    """有限Box的支持函数和原GJK在同一原生调用中完成。"""
    return wheel_contact_kernels.convex_distance(
        center, axis, half, radius, half_width, shoulder, crown, _simplex_coordinates, 1)


def convex_polygon_distance(center, axis, polygon, radius, half_width, shoulder, crown):
    """裁剪面的固定顶点一次读入；原支持顺序及有限边精修保持。"""
    return wheel_contact_kernels.convex_distance(
        center, axis, polygon, radius, half_width, shoulder, crown, _simplex_coordinates, 2)


def convex_distance(center, axis, support_body, radius, half_width, shoulder, crown):
    """独立凸体入口沿用调用方支持函数；生产Box/面走固定数值入口。"""
    return wheel_contact_kernels.convex_distance(
        center, axis, support_body, radius, half_width, shoulder, crown, _simplex_coordinates, 0)


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


def triangle_edge_entry(start, end, triangle, margin, axis, radius, width, shoulder, crown, ceiling, padding):
    """有限面边角保留原GJK/SVD和扫掠门槛，只一次传入本查询固定几何。"""
    return wheel_contact_kernels.triangle_edge_entry(start, end, triangle, margin, axis,
        radius, width, shoulder, crown, _simplex_coordinates, ceiling, padding)
