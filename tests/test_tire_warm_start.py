import math
from dataclasses import replace

import pytest

from vehicle_config import CAR
from wheel_dynamics import Mobility, _solve_force, advance_wheel

CONFIG = replace(CAR, tire_compliance=True)
RIGID = replace(CAR, tire_compliance=False)
LOAD = CAR.mass * 9.81 / 4
MOBILITY = Mobility(1 / 300, 0.0, 0.0, 1 / 320, 0.0, 0.0)


def test_force_solver_accepts_initial_force_without_changing_solution():
    residual = lambda fx, fy: (fx - 3.0, fy + 4.0)

    cold = _solve_force(residual)
    warm = _solve_force(residual, initial=(100.0, -50.0))

    assert cold == pytest.approx((3.0, -4.0, 0.0))
    assert warm == pytest.approx(cold, abs=1e-9)


@pytest.mark.parametrize(
    "state,expected_mode",
    (
        pytest.param((30.0, 10.0, 0.4, 0.1, 0.0, 0.0, 0.0, 1.1), "airborne", id="airborne"),
        pytest.param((0.0, 0.0, 0.0, 0.0, 40.0, 0.0, LOAD, 1.1), "compliant-sticking", id="static-drive"),
        pytest.param((60.0, 20.0, 0.8, 0.1, 120.0, 0.0, LOAD, 1.1), "compliant-rolling", id="forward-sliding"),
        pytest.param((-25.0, -8.0, 0.4, -0.1, -100.0, 80.0, LOAD, 0.45), "compliant-rolling", id="reverse-braking"),
    ),
)
def test_warm_and_zero_force_initials_reach_same_wheel_solution(state, expected_mode):
    omega, vx, vy, body_omega, drive, brake, load, mu = state
    args = (omega, vx, vy, body_omega, drive, brake, load, mu, MOBILITY, 1 / 240, CONFIG)

    cold = advance_wheel(*args, deformation=(0.004, -0.003))
    warm = advance_wheel(*args, deformation=(0.004, -0.003), force_initial=(300.0, -120.0))

    assert cold.mode == warm.mode == expected_mode
    assert warm.residual < 0.001 and cold.residual < 0.001
    assert math.hypot(warm.fx - cold.fx, warm.fy - cold.fy) < 0.001
    for field in (
        "omega", "relative_omega", "vx", "vy", "body_omega", "brake_torque",
        "elastic_energy", "material_dissipation", "road_dissipation",
    ):
        assert getattr(warm, field) == pytest.approx(getattr(cold, field), abs=1e-6)
    assert abs(warm.brake_torque) <= brake
    assert warm.brake_torque * warm.relative_omega >= -1e-7


def test_rigid_wheel_branch_ignores_force_initial_and_keeps_default_solution():
    args = (15.0, 4.5, 0.35, 0.12, 120.0, 0.0, LOAD, 1.1, MOBILITY, 1 / 120, RIGID)

    cold = advance_wheel(*args)
    explicit_initial = advance_wheel(*args, force_initial=(300.0, -120.0))

    assert explicit_initial == cold
