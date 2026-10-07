"""输出轴与前/后驱动轴的刚性惯量消元；各实体转子仍保留机械账。"""

import mechanical_kernels
from mechanical_kernels import dot

project_inertia = mechanical_kernels.project_vector


def rotor_weights(front_share):
    """输出轴随中差平均速，前/后轴分别随实际驱动轴的平均速。"""
    return ((front_share / 2, front_share / 2, (1 - front_share) / 2, (1 - front_share) / 2),
            (.5, .5, 0., 0.), (0., 0., .5, .5))


def active_inertias(inertias, front_share):
    """未安装的非驱动轴不携带转子；输出轴始终属于当前传动链。"""
    return inertias[0], inertias[1] if front_share > 0 else 0., inertias[2] if front_share < 1 else 0.


def rotor_gradients(rotor_axes, wheel_axes, front_share, final_drive, wheel_start):
    """绝对轴速=Ω·轴+主减速比×相对轮速；完整保留车身交叉项。"""
    return tuple(tuple(axis[a] + final_drive * sum(w * e[a] for w, e in zip(weights, wheel_axes))
                       for a in range(3)) + (0.,) * (wheel_start - 3)
                 + tuple(final_drive * w for w in weights)
                 for axis, weights in zip(rotor_axes, rotor_weights(front_share)))


def inertia_projections(inverse_mass, gradients, inertias):
    """每个实体转子的J ggᵀ进入同一质量矩阵，不折成孤立标量。"""
    projections = []
    for gradient, inertia in zip(gradients, inertias):
        if inertia == 0:
            continue
        response = project_inertia(inverse_mass(gradient), projections)
        factor = inertia / (1 + inertia * dot(gradient, response))
        projections.append((gradient, response, factor))
    return tuple(projections)
