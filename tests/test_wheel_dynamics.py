from dataclasses import replace

import numpy as np
import pytest

from vehicle_config import CAR
from wheel_dynamics import Mobility, advance_wheel

# 本文件冻结零柔性的刚性约束；柔性储能与四轮共同末速度在专门测试验证。
RIGID = replace(CAR, tire_compliance=False)


def _mass_and_mobility():
    # 平移质量与非零质心耦合构成正定广义质量矩阵。
    mass = np.array(((300.0, 0.0, 0.0), (0.0, 320.0, 12.0), (0.0, 12.0, 50.0)))
    inverse = np.linalg.inv(mass)
    mobility = Mobility(
        inverse[0, 0], inverse[0, 1], inverse[0, 2],
        inverse[1, 1], inverse[1, 2], inverse[2, 2],
    )
    matrix = np.array(
        (
            (mobility.xx, mobility.xy, mobility.xt),
            (mobility.xy, mobility.yy, mobility.yt),
            (mobility.xt, mobility.yt, mobility.tt),
        )
    )
    return mass, mobility, matrix


def _body_speed(step):
    return np.array((step.vx, step.vy, step.body_omega))


def _state_energy(speed, omega, mass_matrix, wheel_inertia):
    return 0.5 * speed @ mass_matrix @ speed + 0.5 * wheel_inertia * omega**2


def _energy_ledger(before, after, mass_matrix, drive, dt):
    old_speed = np.array(before[:3])
    new_speed = _body_speed(after)
    delta_speed = new_speed - old_speed
    delta_omega = after.omega - before[3]
    old_energy = _state_energy(old_speed, before[3], mass_matrix, CAR.wheel_inertia)
    new_energy = _state_energy(new_speed, after.omega, mass_matrix, CAR.wheel_inertia)
    relative_omega = after.relative_omega
    drive_work = dt * drive * relative_omega
    brake_dissipation = dt * after.brake_torque * relative_omega
    tire_dissipation = dt * (
        after.fx * (CAR.wheel_radius * after.omega - after.vx) - after.fy * after.vy
    )
    numerical_dissipation = (
        0.5 * delta_speed @ mass_matrix @ delta_speed
        + 0.5 * CAR.wheel_inertia * delta_omega**2
    )
    expected_change = drive_work - brake_dissipation - tire_dissipation - numerical_dissipation
    return new_energy - old_energy, expected_change


def test_mobility_is_symmetric_positive_definite():
    mass, _mobility, matrix = _mass_and_mobility()

    assert np.allclose(matrix, matrix.T)
    assert np.all(np.linalg.eigvalsh(matrix) > 0)
    assert np.all(np.linalg.eigvalsh(mass) > 0)


def test_static_contact_transmits_drive_without_slip():
    _mass, mobility, _matrix = _mass_and_mobility()
    step = advance_wheel(0, 0, 0, 0, 20, 0, 3000, 1.1, mobility, 1 / 120, RIGID)
    assert step.mode == "sticking"
    assert step.fx > 0
    assert step.vx == pytest.approx(CAR.wheel_radius * step.omega, abs=1e-8)
    assert step.vy == pytest.approx(0, abs=1e-8)
    assert step.kappa == pytest.approx(0, abs=1e-8)
    assert step.fx**2 + step.fy**2 <= (3300)**2
    assert step.residual < .001


def test_static_contact_exhausted_budget_enters_actual_sliding():
    _mass, mobility, _matrix = _mass_and_mobility()
    step = advance_wheel(0, 0, 0, 0, 100, 0, 10, .5, mobility, 1 / 120, RIGID)
    assert step.mode == "magic-formula"
    assert abs(CAR.wheel_radius * step.omega - step.vx) > .01
    capacity = .5 * 10 * (10 / (CAR.mass * 9.81 / 4)) ** (CAR.tire_peak_load_exponent - 1)
    assert step.fx**2 + step.fy**2 <= capacity**2 + 1e-6


def test_low_load_static_feasibility_uses_same_nonlinear_capacity():
    _mass, mobility, _matrix = _mass_and_mobility()
    linear = replace(RIGID, tire_peak_load_exponent=1, longitudinal_load_exponent=1,
                     lateral_load_exponent=1)
    candidate = advance_wheel(0, 0, 0, 0, 2.5, 0, 10, .5, mobility, 1 / 120, RIGID)
    old = advance_wheel(0, 0, 0, 0, 2.5, 0, 10, .5, mobility, 1 / 120, linear)
    assert candidate.mode == "sticking"
    assert old.mode == "magic-formula"
    assert candidate.fx**2 + candidate.fy**2 > (.5 * 10)**2


def test_static_external_force_predictor_is_balanced_with_closed_energy_ledger():
    mass, mobility, matrix = _mass_and_mobility()
    dt = 1 / 120
    # 已知外力先形成free predictor，轮胎反力需保持无滑移约束。
    external_force = np.array((30.0, -20.0, 0.0))
    speed = dt * matrix @ external_force
    before = np.array((*speed, 0.0))
    step = advance_wheel(0, *speed, 0, 1500, 3000, 1.1, mobility, dt, RIGID)
    assert step.mode == "sticking"
    assert step.fx < 0 and step.fy > 0
    assert step.vx == pytest.approx(CAR.wheel_radius * step.omega, abs=1e-8)
    assert step.vy == pytest.approx(0, abs=1e-8)
    actual, expected = _energy_ledger(before, step, mass, 0, dt)
    assert actual == pytest.approx(expected, abs=1e-9)
    assert actual <= 1e-10


@pytest.mark.parametrize(
    ("omega", "vx", "vy", "body_omega", "drive", "brake"),
    (
        (15.0, 4.5, 0.35, 0.12, 120.0, 0.0),
        (24.0, 8.0, -0.2, -0.08, 0.0, 120.0),
        (-10.0, -3.0, 0.5, 0.06, -90.0, 0.0),
    ),
)
@pytest.mark.parametrize("load_ratio", [.01, .5, 1, 2])
def test_implicit_step_closes_energy_and_generalized_momentum_ledger(
    omega, vx, vy, body_omega, drive, brake, load_ratio
):
    mass, mobility, matrix = _mass_and_mobility()
    dt = 1 / 120
    before = np.array((vx, vy, body_omega, omega))
    step = advance_wheel(
        omega,
        vx,
        vy,
        body_omega,
        drive,
        brake,
        load_ratio * CAR.mass * 9.81 / 4,
        1.1,
        mobility,
        dt,
        RIGID,
    )

    assert step.residual < 0.001
    assert step.relative_omega == pytest.approx(step.omega + step.body_omega)
    body_delta = _body_speed(step) - before[:3]
    generalized_impulse = np.array((step.fx, step.fy, drive - step.brake_torque)) * dt
    assert body_delta == pytest.approx(matrix @ generalized_impulse, abs=1e-10)
    wheel_impulse = CAR.wheel_inertia * (step.omega - omega)
    assert wheel_impulse == pytest.approx(dt * (drive - step.brake_torque - CAR.wheel_radius * step.fx))

    actual_change, expected_change = _energy_ledger(before, step, mass, drive, dt)
    assert actual_change == pytest.approx(expected_change, abs=1e-9)
    if brake > 0:
        assert step.brake_torque * step.relative_omega >= 0
    capacity = 1.1 * CAR.mass * 9.81 / 4 * load_ratio ** CAR.tire_peak_load_exponent
    assert step.fx**2 + step.fy**2 <= capacity**2


@pytest.mark.parametrize(("direction", "drive"), ((1, 120.0), (-1, -120.0)))
def test_drive_accelerates_in_forward_and_reverse(direction, drive):
    _mass, mobility, _matrix = _mass_and_mobility()
    speed = direction * 2.0
    step = advance_wheel(
        speed / CAR.wheel_radius,
        speed,
        0.0,
        0.0,
        drive,
        0.0,
        CAR.mass * 9.81 / 4,
        1.1,
        mobility,
        1 / 120,
        RIGID,
    )

    assert direction * (step.vx - speed) > 0
    assert direction * step.fx > 0


def test_dry_braking_stops_without_reversing_vehicle_or_wheel():
    # 此停车工况由支撑约束保持车体俯仰；自由空中刚体不能代表停在地面的车。
    mobility = Mobility(1 / 300, 0.0, 0.0, 1 / 320, 0.0, 0.0)
    speed = 10.0
    body_omega = 0.0
    omega = speed / CAR.wheel_radius
    for _ in range(600):
        step = advance_wheel(
            omega,
            speed,
            0.0,
            body_omega,
            0.0,
            1500.0,
            CAR.mass * 9.81 / 4,
            1.1,
            mobility,
            1 / 120,
            RIGID,
        )
        speed, omega = step.vx, step.omega
        body_omega = step.body_omega
        assert speed >= -1e-9
        assert step.relative_omega >= -1e-9
        if speed < 0.01 and step.relative_omega < 0.01:
            break
    assert speed < 0.01
    assert step.relative_omega < 0.01


def test_airborne_drive_torque_has_equal_opposite_angular_impulses():
    mass, mobility, _matrix = _mass_and_mobility()
    dt = 1 / 120
    body_speed = np.array((1.0, -0.2, 0.15))
    wheel_speed = 2.0
    drive = 90.0
    step = advance_wheel(
        wheel_speed,
        body_speed[0],
        body_speed[1],
        body_speed[2],
        drive,
        0.0,
        0.0,
        1.1,
        mobility,
        dt,
        RIGID,
    )

    assert step.fx == 0.0
    assert step.fy == 0.0
    body_momentum_delta = mass @ (_body_speed(step) - body_speed)
    wheel_angular_momentum_delta_about_right = -CAR.wheel_inertia * (step.omega - wheel_speed)
    assert body_momentum_delta[:2] == pytest.approx((0.0, 0.0), abs=1e-10)
    assert body_momentum_delta[2] == pytest.approx(dt * drive)
    assert wheel_angular_momentum_delta_about_right == pytest.approx(-dt * drive)
    assert body_momentum_delta[2] + wheel_angular_momentum_delta_about_right == pytest.approx(0.0, abs=1e-10)


def test_smaller_steps_preserve_drive_and_brake_directions():
    _mass, mobility, _matrix = _mass_and_mobility()
    for dt in (1 / 120, 1 / 480):
        driven = advance_wheel(0.0, 0.0, 0.0, 0.0, 120.0, 0.0,
                               CAR.mass * 9.81 / 4, 1.1, mobility, dt, RIGID)
        braked = advance_wheel(10 / CAR.wheel_radius, 10.0, 0.0, 0.0, 0.0, 120.0,
                               CAR.mass * 9.81 / 4, 1.1, mobility, dt, RIGID)
        assert driven.vx > 0 and driven.omega > 0
        assert braked.vx < 10.0 and braked.omega < 10 / CAR.wheel_radius
