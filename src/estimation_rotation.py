"""Hamilton四元数与SO(3)局部旋转的纯数学函数。"""

import numpy as np


def skew(vector):
    """返回满足skew(v) @ u == v叉乘u的反对称矩阵。"""
    x, y, z = np.asarray(vector, dtype=float)
    return np.array(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def multiply(q, r):
    """Hamilton乘积；四元数顺序为(w, x, y, z)。"""
    w1, x1, y1, z1 = np.asarray(q, dtype=float)
    w2, x2, y2, z2 = np.asarray(r, dtype=float)
    return np.array((
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    ))


def conjugate(q):
    """返回单位四元数的逆。"""
    return np.asarray(q, dtype=float) * np.array((1.0, -1.0, -1.0, -1.0))


def exp(rotation_vector):
    """将旋转向量映射为主动旋转四元数，旋转角使用半角指数式。"""
    vector = np.asarray(rotation_vector, dtype=float)
    angle = np.linalg.norm(vector)
    half = 0.5 * angle
    if angle < 1e-8:
        square = angle * angle
        scale = 0.5 - square / 48.0 + square * square / 3840.0
    else:
        scale = np.sin(half) / angle
    return np.concatenate(([np.cos(half)], scale * vector))


def log(q):
    """将单位四元数映射为最短旋转向量；q与-q得到相同结果。"""
    quaternion = np.asarray(q, dtype=float)
    if quaternion[0] < 0.0:
        quaternion = -quaternion
    elif quaternion[0] == 0.0:
        first_nonzero = np.flatnonzero(quaternion[1:])
        if first_nonzero.size and quaternion[1 + first_nonzero[0]] < 0.0:
            quaternion = -quaternion

    vector = quaternion[1:]
    magnitude = np.linalg.norm(vector)
    if magnitude < 1e-8:
        square = magnitude * magnitude
        scale = 2.0 + square / 3.0 + 3.0 * square * square / 20.0
    else:
        scale = 2.0 * np.arctan2(magnitude, quaternion[0]) / magnitude
    return scale * vector


def matrix(q):
    """返回单位四元数对应的body到world主动旋转矩阵。"""
    w, x, y, z = np.asarray(q, dtype=float)
    return np.array((
        (1.0 - 2.0*(y*y + z*z), 2.0*(x*y - w*z), 2.0*(x*z + w*y)),
        (2.0*(x*y + w*z), 1.0 - 2.0*(x*x + z*z), 2.0*(y*z - w*x)),
        (2.0*(x*z - w*y), 2.0*(y*z + w*x), 1.0 - 2.0*(x*x + y*y)),
    ))


def right_jacobian(rotation_vector):
    """返回SO(3)右雅可比，使Exp(phi+d)约等于Exp(phi)Exp(Jr(phi)d)。"""
    vector = np.asarray(rotation_vector, dtype=float)
    square = float(vector @ vector)
    cross = skew(vector)
    if square < 1e-4:
        square2 = square * square
        first = 0.5 - square / 24.0 + square2 / 720.0
        second = 1.0 / 6.0 - square / 120.0 + square2 / 5040.0
    else:
        angle = np.sqrt(square)
        first = (1.0 - np.cos(angle)) / square
        second = (angle - np.sin(angle)) / (square * angle)
    return np.eye(3) - first * cross + second * (cross @ cross)
