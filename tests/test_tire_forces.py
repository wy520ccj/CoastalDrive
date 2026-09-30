import math

import pytest

from tire_forces import slip_state, tire_force
from vehicle_config import CAR

NOMINAL_LOAD = CAR.mass * 9.81 / 4


def test_small_slips_have_configured_longitudinal_and_lateral_stiffness():
    normal_load = NOMINAL_LOAD
    mu = 1.1
    kappa = 1e-6
    alpha = 1e-6

    longitudinal, _ = tire_force(kappa, 0.0, normal_load, mu)
    _, lateral = tire_force(0.0, alpha, normal_load, mu)

    assert longitudinal / kappa == pytest.approx(CAR.longitudinal_stiffness, rel=0.01)
    assert lateral / alpha == pytest.approx(-CAR.lateral_stiffness, rel=0.01)


def test_slip_state_uses_signed_forward_and_reverse_wheel_slip():
    radius = 0.33
    forward_slip, _ = slip_state(10.0, 0.0, 10.1 / radius, radius)
    reverse_slip, _ = slip_state(-10.0, 0.0, -10.1 / radius, radius)
    locked_reverse_slip, _ = slip_state(-10.0, 0.0, 0.0, radius)

    assert forward_slip > 0
    assert reverse_slip < 0
    assert locked_reverse_slip > 0
    assert tire_force(forward_slip, 0.0, NOMINAL_LOAD, 1.1)[0] > 0
    assert tire_force(reverse_slip, 0.0, NOMINAL_LOAD, 1.1)[0] < 0
    assert tire_force(locked_reverse_slip, 0.0, NOMINAL_LOAD, 1.1)[0] > 0


def test_lateral_force_opposes_lateral_velocity():
    for vy in (-4.0, -0.5, 0.5, 4.0):
        _, alpha = slip_state(8.0, vy, 8.0 / CAR.wheel_radius, CAR.wheel_radius)
        _, lateral_force = tire_force(0.0, alpha, NOMINAL_LOAD, 1.1)
        assert lateral_force * vy < 0


def test_combined_slip_respects_budget_and_reduces_longitudinal_share():
    normal_load = NOMINAL_LOAD
    mu = 1.1
    pure_longitudinal = tire_force(0.15, 0.0, normal_load, mu)
    combined = tire_force(0.15, 0.25, normal_load, mu)

    assert math.hypot(*pure_longitudinal) <= mu * normal_load
    assert math.hypot(*combined) <= mu * normal_load
    assert abs(combined[0]) < abs(pure_longitudinal[0])
    assert combined[1] < 0


def test_force_is_centrally_symmetric():
    first = tire_force(0.12, -0.08, NOMINAL_LOAD, 1.1)
    opposite = tire_force(-0.12, 0.08, NOMINAL_LOAD, 1.1)

    assert opposite[0] == pytest.approx(-first[0])
    assert opposite[1] == pytest.approx(-first[1])


def test_zero_normal_load_produces_no_force():
    assert tire_force(0.5, -0.3, 0.0, 1.1) == (0.0, 0.0)


def test_locked_wheel_slip_is_past_the_braking_force_peak():
    normal_load = NOMINAL_LOAD
    mu = 1.1
    braking_forces = [
        abs(tire_force(-slip, 0.0, normal_load, mu)[0])
        for slip in (index / 1000 for index in range(1, 1001))
    ]
    locked_force = abs(tire_force(-1.0, 0.0, normal_load, mu)[0])

    assert locked_force < max(braking_forces)
