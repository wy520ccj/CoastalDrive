"""机械轮轴的角动量输运；只计算轴承反力，不维护第二套车身状态。"""

from mechanical_kernels import cross
from mechanical_kernels import dot3 as dot


def solve_transport(angular, inverse_inertia, spin, dt):
    """解(I-h[S]×)Ω=IΩfree；使用同一世界逆惯量，保留局部轮胎的对称Mobility。"""
    x, y, z = spin
    skew = ((0., -z, y), (z, 0., -x), (-y, x, 0.))
    rows = tuple(tuple((1. if a == b else 0.) - dt * sum(
        inverse_inertia[a][c] * skew[c][b] for c in range(3)) for b in range(3)) for a in range(3))
    columns = (cross(rows[1], rows[2]), cross(rows[2], rows[0]), cross(rows[0], rows[1]))
    determinant = dot(rows[0], columns[0])
    return tuple(sum(columns[b][a] * angular[b] for b in range(3)) / determinant for a in range(3))


def bearing_torques(axes, omega, inertia, angular):
    """正滚动自旋为−Jωe；车身随动反力S×Ω与末车身角速正交。"""
    return tuple(cross(tuple(-inertia * speed * value for value in axis), angular)
                 for axis, speed in zip(axes, omega))


def steering_torque(old_axis, new_axis, omega, inertia, dt):
    """轴向指定运动的反力；JΔωe_new另由驱动/制动/接触负责，避免重复乘积项。"""
    return tuple(inertia * omega * (new_axis[a] - old_axis[a]) / dt for a in range(3))
