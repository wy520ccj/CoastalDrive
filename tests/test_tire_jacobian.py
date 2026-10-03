"""接触目标与轮/车体制动消元的解析导数，对照独立中心差分。"""

import math
from dataclasses import replace

import pytest

import wheel_dynamics
from tire_compliance import contact_force, contact_jacobian
from vehicle_config import CAR
from wheel_dynamics import Mobility, advance_wheel


@pytest.mark.parametrize("rolling,grip,slip,force,previous", [
    (True, 3000., (.1, -.04), (40., -25.), (.003, -.002)),
    (True, 3000., (-.3, .08), (-500., 200.), (-.005, .003)),
    (True, 500., (50., -12.), (300., -100.), (.005, -.004)),
    (True, 3000., (0., 0.), (75., -30.), (.0005, -.0002)),
    (True, 0., (.1, -.04), (40., -25.), (.003, -.002)),
    (False, 3000., (.03, .02), (40., -25.), (.001, -.001)),
    (False, 500., (5., -3.), (100., -100.), (.001, -.001)),
    (False, 0., (.1, -.04), (40., -25.), (.003, -.002)),
])
@pytest.mark.parametrize("denominator,gradient", [(20., (.0002, -.0001)), (1., (0., 0.))])
def test_contact_target_derivative_matches_independent_difference(
        rolling, grip, slip, force, previous, denominator, gradient):
    slip_jacobian = ((-.0007, .0001), (.0001, -.0003))
    parameters = (rolling, grip, 60000., 50000., 1 / 240, 150000., 1000., 1.55, .4)
    analytic = contact_jacobian(force, previous, slip, slip_jacobian, denominator, gradient, *parameters)
    epsilon = 1e-4
    for j in range(2):
        def target(sign, column):
            changed_force = tuple(force[i] + sign * epsilon * float(i == column) for i in range(2))
            changed_slip = tuple(slip[i] + sign * epsilon * slip_jacobian[i][column] for i in range(2))
            return contact_force(changed_force, previous, changed_slip,
                                 denominator + sign * epsilon * gradient[column], *parameters)[0]

        positive, negative = target(1, j), target(-1, j)
        for i in range(2):
            observed = (positive[i] - negative[i]) / (2 * epsilon)
            assert analytic[i][j] == pytest.approx(observed, abs=1e-7, rel=2e-6)


@pytest.mark.parametrize("omega,vx,vy,drive,brake,load", [
    (60., 20., .8, 120., 0., 2943.),
    (-25., -8., .4, -100., 80., 2943.),
    (0., 0., 0., 40., 200., 2943.),
    (0., 0., .3, 40., 2., 2943.),
    (.1, .4, .05, 10., 0., 2943.),
    (10., 3., .2, 0., 100., 0.),
])
def test_full_force_residual_derivative_includes_brake_and_speed_denominator(
        monkeypatch, omega, vx, vy, drive, brake, load):
    original = wheel_dynamics._solve_force
    checked = []

    def verify(residual, tolerance=.001, initial=(0., 0.), jacobian=None):
        assert jacobian is not None
        fx, fy = 50., -70.
        analytic = jacobian(fx, fy)
        epsilon = 1e-4
        plus_x, minus_x = residual(fx + epsilon, fy), residual(fx - epsilon, fy)
        plus_y, minus_y = residual(fx, fy + epsilon), residual(fx, fy - epsilon)
        numerical = ((plus_x[0] - minus_x[0]) / (2 * epsilon),
                     (plus_y[0] - minus_y[0]) / (2 * epsilon),
                     (plus_x[1] - minus_x[1]) / (2 * epsilon),
                     (plus_y[1] - minus_y[1]) / (2 * epsilon))
        assert analytic == pytest.approx(numerical, abs=2e-7, rel=2e-6)
        checked.append(True)
        return original(residual, tolerance=tolerance, initial=initial, jacobian=jacobian)

    monkeypatch.setattr(wheel_dynamics, "_solve_force", verify)
    mobility = Mobility(1 / 300, .0001, .0002, 1 / 320, -.0001, .0005)
    step = advance_wheel(omega, vx, vy, .1, drive, brake, load, .45,
                         mobility, 1 / 240, replace(CAR, tire_compliance=True), (.004, -.003))
    assert checked == [True]
    assert step.residual < .001
    assert math.isfinite(step.elastic_energy)
    assert step.brake_torque * step.relative_omega >= -1e-7
