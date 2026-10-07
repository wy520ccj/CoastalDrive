"""前/后轴与开放中差的有限粘性限滑；不持有车辆或原生世界。"""

from itertools import product

import mechanical_kernels
from mechanical_kernels import dot

from transmission_ports import PORT_TOLERANCE

viscous_projection = mechanical_kernels.project_vector


def torque_bias_capacities(maximum, biases, axle_torques):
    """T左右=T轴/2±τ；给定TBR得到|τ|≤|T轴|(B−1)/(2(B+1))。"""
    return tuple(min(limit, abs(torque) * (bias - 1.) / (2 * (bias + 1.))) if bias > 1. else limit
                 for limit, bias, torque in zip(maximum, biases, axle_torques))


def differential_gradients(axes):
    """滑差是相对壳体轴速之差；转向轴不平行时反力不能省略。"""
    coefficients = ((1., -1., 0., 0.), (0., 0., 1., -1.), (.5, .5, -.5, -.5))
    return tuple(tuple(sum(weights[i] * axes[i][a] for i in range(4)) for a in range(3))
                 + (0.,) + weights for weights in coefficients)


def differential_branches(gradients, damping, capacities, mobility, dt):
    """每个有限端口仅有粘性区及正/负饱和区，提前构成精确消元。"""
    branches = []
    choices = [(0, 1, -1) if c and limit else (0,) for c, limit in zip(damping, capacities)]
    for modes in product(*choices):
        projections = []
        offset = (0.,) * len(gradients[0])
        for g, c, limit, mode in zip(gradients, damping, capacities, modes):
            if not c or not limit:
                continue
            if mode:
                response = mobility(g)
                offset = tuple(offset[a] - dt * mode * limit * response[a] for a in range(len(offset)))
            else:
                response = viscous_projection(mobility(g), projections)
                factor = dt * c / (1 + dt * c * dot(g, response))
                projections.append((g, response, factor))
        branches.append((tuple(projections), viscous_projection(offset, projections), modes))
    return tuple(branches)


def differential_torques(state, branch, gradients, damping, capacities):
    """只接受满足本构律的分区；不靠轮速钳位或迭代后补矩。"""
    _projections, _offset, modes = branch
    torques = []
    for g, c, limit, mode in zip(gradients, damping, capacities, modes):
        if not c or not limit:
            torques.append(0.)
            continue
        viscous = c * dot(g, state)
        torque = mode * limit if mode else viscous
        expected = max(-limit, min(limit, viscous))
        if abs(torque - expected) > PORT_TOLERANCE:
            return None
        torques.append(torque)
    return tuple(torques)
