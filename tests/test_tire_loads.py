"""轮荷转移的轴总能力、小滑移斜率和冻结稳态曲线边界。"""

import math
from dataclasses import replace

import pytest

from tire_forces import tire_force
from tire_properties import tire_grip, tire_stiffness
from vehicle_config import CAR

NOMINAL = CAR.mass * 9.81 / 4
LINEAR = replace(CAR, tire_peak_load_exponent=1, longitudinal_load_exponent=1,
                 lateral_load_exponent=1)


def old_force(kappa, alpha, load, mu):
    # 冻结CTRL-03原公式，保留其运算顺序。
    if load == 0:
        return 0., 0.
    ratio = load / NOMINAL
    qx = CAR.longitudinal_stiffness * ratio * kappa
    qy = -CAR.lateral_stiffness * ratio * math.tan(alpha)
    norm = math.hypot(qx, qy)
    if norm == 0:
        return 0., 0.
    budget = mu * load
    n = norm / (CAR.tire_shape * budget)
    magnitude = budget * math.sin(CAR.tire_shape * math.atan(
        n - CAR.tire_curvature * (n - math.atan(n))))
    return magnitude * qx / norm, magnitude * qy / norm


@pytest.mark.parametrize("ratio", [.01, .5, 1, 1.5, 2, 6000 / NOMINAL])
def test_force_budget_symmetry_and_loaded_small_slip_slope(ratio):
    load = ratio * NOMINAL
    capacity = 1.1 * NOMINAL * ratio ** CAR.tire_peak_load_exponent
    for kappa in (-1, -.12, 0, .12, 1):
        for alpha in (-.4, 0, .4):
            force = tire_force(kappa, alpha, load, 1.1)
            reverse = tire_force(-kappa, -alpha, load, 1.1)
            assert math.hypot(*force) <= capacity + 1e-9
            assert reverse == pytest.approx(tuple(-v for v in force), abs=1e-10)
    cx = tire_force(1e-7, 0, load, 1.1)[0] / 1e-7
    cy = -tire_force(0, 1e-7, load, 1.1)[1] / 1e-7
    assert cx == pytest.approx(CAR.longitudinal_stiffness * ratio ** .90, rel=1e-7)
    assert cy == pytest.approx(CAR.lateral_stiffness * ratio ** .85, rel=1e-7)


def test_load_transfer_reduces_capacity_at_fixed_total_axle_load():
    capacities = [sum(tire_grip(2 * NOMINAL * fraction, 1.1, CAR)
                      for fraction in (share, 1 - share)) for share in (.5, .3, .1)]
    assert capacities[0] > capacities[1] > capacities[2]
    for share, capacity in zip((.5, .3, .1), capacities):
        expected_ratio = ((2 * share) ** .90 + (2 * (1 - share)) ** .90) / 2
        assert capacity / capacities[0] == pytest.approx(expected_ratio)


@pytest.mark.parametrize("mu", [.45, 1.1])
def test_nominal_curve_and_linear_disable_preserve_frozen_forces(mu):
    for ratio in (0, .01, .5, 1, 1.5, 2):
        load = ratio * NOMINAL
        for kappa in (-1, -.12, 0, .12, 1):
            for alpha in (-.4, 0, .4):
                expected = old_force(kappa, alpha, load, mu)
                assert tire_force(kappa, alpha, load, mu, LINEAR) == expected
                if ratio == 1:
                    assert tire_force(kappa, alpha, load, mu) == expected


def test_no_support_or_friction_has_no_tangent_force():
    assert tire_grip(0, 1.1, CAR) == 0
    assert tire_stiffness(0, CAR) == (0, 0)
    assert tire_force(.2, .3, 0, 1.1) == (0, 0)
    assert tire_force(.2, .3, NOMINAL, 0) == (0, 0)
