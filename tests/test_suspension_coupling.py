"""独立刚体KKT、射线几何虚功与悬架能量账；不沿用生产矩阵作期望。"""

import math

import numpy as np
import pytest

from suspension import advance_suspension, contact_gradient

RATES = (42000., 48000., 50000., 46000.)
BARS = (6000., 4000.)
STOPS = (480000.,) * 4
DT = 1 / 120


def potential(x):
    return sum(k * v * v / 2 for k, v in zip(RATES, x)) + sum(
        b * (x[i] - x[i + 1]) ** 2 / 2 for i, b in zip((0, 2), BARS)) + sum(
        k * max(abs(v) - .2, 0.) ** 2 / 2 for k, v in zip(STOPS, x))


def frames(bank):
    normal = np.array([math.sin(bank), 0., math.cos(bank)])
    points = [np.array([x, y, -.4]) for y in (1.1, -1.1) for x in (-.84, .84)]
    gradient = np.array([np.r_[normal, np.cross(p, normal)] / normal[2] for p in points])
    mass = np.diag([1200., 1200., 1200., 1900., 510., 2290.])
    return gradient, mass


@pytest.mark.parametrize("bank", (0., .2, -.4))
@pytest.mark.parametrize("speed", (-.2, .15))
def test_common_end_state_matches_explicit_body_and_elastic_constraints(bank, speed):
    gradient, mass = frames(bank)
    compression = np.array([.085, .075, .08, .07])
    velocity = np.array([.1, .2, speed, .03, -.02, .01])
    damping = (3200.,) * 4
    k = np.diag(RATES)
    for i, b in zip((0, 2), BARS):
        difference = np.eye(4)[i] - np.eye(4)[i + 1]
        k += b * np.outer(difference, difference)
    c = np.diag(damping)
    matrix = np.block([
        [mass, np.zeros((6, 4)), -DT * gradient.T],
        [DT * gradient, np.eye(4), np.zeros((4, 4))],
        [np.zeros((4, 6)), -(k + c / DT), np.eye(4)],
    ])
    explicit = np.linalg.solve(matrix, np.r_[mass @ velocity, compression, -c @ compression / DT])
    expected_velocity, expected_x, expected_force = explicit[:6], explicit[6:10], explicit[10:]
    assert all(0 < f < 6000 * math.cos(bank) for f in expected_force)
    mobility = gradient @ np.linalg.solve(mass, gradient.T)
    actual = advance_suspension(compression, gradient @ velocity, mobility, (True,) * 4,
                               RATES, damping, damping,
                               BARS, STOPS, .2, DT)
    assert actual.compression == pytest.approx(expected_x, abs=2e-15)
    assert actual.axial_force == pytest.approx(expected_force, abs=1e-9)
    end_velocity = velocity + DT * np.linalg.solve(mass, gradient.T @ actual.axial_force)
    assert end_velocity == pytest.approx(expected_velocity, abs=2e-15)
    kinetic_change = (end_velocity @ mass @ end_velocity - velocity @ mass @ velocity) / 2
    delta = np.array(actual.compression) - compression
    damping_loss = delta @ c @ delta / DT
    elastic_loss = delta @ k @ delta / 2
    body_loss = (end_velocity - velocity) @ mass @ (end_velocity - velocity) / 2
    balance = kinetic_change + potential(actual.compression) - potential(compression) + damping_loss + elastic_loss + body_loss
    assert balance == pytest.approx(0., abs=2e-12)
    assert actual.damping_dissipation == pytest.approx(damping_loss, abs=1e-13)
    assert actual.elastic_numerical_dissipation == pytest.approx(elastic_loss, abs=2e-12)
    assert actual.body_numerical_dissipation == pytest.approx(body_loss, abs=1e-13)


@pytest.mark.parametrize("bank", (0., .25, -.45))
def test_ray_geometry_virtual_work_and_axial_damping(bank):
    n = np.array([math.sin(bank), 0., math.cos(bank)])
    hub, direction = np.array([-.8, 1.1, .6]), np.array([0., 0., -1.])
    distance = n @ hub / (-n @ direction)
    point = hub + distance * direction
    gradient = np.array(contact_gradient(n, direction, point))
    numerical = []
    epsilon = 1e-7
    for a in range(6):
        delta = np.eye(6)[a] * epsilon
        axis = delta[3:]
        skew = np.array([[0., -axis[2], axis[1]], [axis[2], 0., -axis[0]], [-axis[1], axis[0], 0.]])
        moved_hub, moved_direction = (np.eye(3) + skew) @ hub + delta[:3], (np.eye(3) + skew) @ direction
        moved_distance = n @ moved_hub / (-n @ moved_direction)
        numerical.append((moved_distance - distance) / epsilon)
    assert gradient == pytest.approx(numerical, abs=2e-7)
    velocity = np.array([.2, 1., -.3, .03, -.08, .04])
    axial_speed = gradient @ velocity
    c = 5280.
    damper_force = -c * axial_speed
    body_power = (damper_force * gradient) @ velocity
    assert body_power == pytest.approx(-c * axial_speed ** 2, abs=1e-12)
    if bank:
        old_native_power = -c * axial_speed ** 2 * math.cos(bank)
        assert abs(old_native_power - body_power) > 1.


def test_free_wheels_relax_without_erasing_bar_or_spring_energy():
    x = (.15, .02, .09, -.04)
    for _ in range(80):
        step = advance_suspension(x, (0.,) * 4, ((0.,) * 4,) * 4, (False,) * 4,
                                  RATES, (5280.,) * 4, (2760.,) * 4,
                                  BARS, STOPS, .2, DT)
        assert step.axial_force == pytest.approx((0.,) * 4, abs=1e-10)
        assert potential(step.compression) < potential(x)
        assert step.damping_dissipation > 0
        assert potential(step.compression) - potential(x) + step.damping_dissipation + step.elastic_numerical_dissipation == pytest.approx(0., abs=1e-12)
        x = step.compression
    assert potential(x) < .01


@pytest.mark.parametrize("x", ((.26, .24, .23, .25), (-.28, -.25, -.24, -.26)))
def test_progressive_stops_and_free_travel_energy(x):
    step = advance_suspension(x, (0.,) * 4, ((0.,) * 4,) * 4, (False,) * 4,
                              RATES, (5280.,) * 4, (2760.,) * 4,
                              BARS, STOPS, .2, DT)
    assert potential(step.compression) < potential(x)
    assert step.elastic_numerical_dissipation >= 0.
    assert abs(step.energy_residual) < 1e-10


def test_stop_response_exceeds_legacy_clip_with_passive_energy():
    gradient, mass = frames(.3)
    velocity = np.array([0., 0., -3., 0., 0., 0.])
    initial = np.array([.18] * 4)
    mobility = gradient @ np.linalg.solve(mass, gradient.T)
    step = advance_suspension(initial, gradient @ velocity, mobility, (True,) * 4,
                              RATES, (5280.,) * 4, (2760.,) * 4,
                              BARS, STOPS, .2, DT)
    assert min(step.axial_force) / math.cos(.3) > 6000.
    assert step.raw_axial_force == pytest.approx(step.axial_force, abs=1e-8)
    end_velocity = velocity + DT * np.linalg.solve(mass, gradient.T @ step.axial_force)
    change = (end_velocity @ mass @ end_velocity - velocity @ mass @ velocity) / 2
    balance = change + potential(step.compression) - potential(initial) + step.damping_dissipation + step.elastic_numerical_dissipation + step.body_numerical_dissipation
    assert balance == pytest.approx(0., abs=1e-10)
    assert change + potential(step.compression) - potential(initial) <= 0.
    assert step.contact_offset_work == 0.


def test_grazing_contact_has_no_fabricated_geometry_factor():
    assert contact_gradient((1., 0., 0.), (0., 0., -1.), (0., 0., -.4)) is None


def test_prospective_contact_gap_is_dissipative_instead_of_preloading_airborne_spring():
    gradient, mass = frames(0.)
    velocity = np.array([0., 0., -3.5, 0., 0., 0.])
    mobility = gradient @ np.linalg.solve(mass, gradient.T)
    step = advance_suspension((0.,) * 4, gradient @ velocity, mobility, (True,) * 4,
                              RATES, (5280.,) * 4, (2760.,) * 4, BARS, STOPS, .2, DT,
                              geometry=(-.0048,) * 4)
    end_velocity = velocity + DT * np.linalg.solve(mass, gradient.T @ step.axial_force)
    kinetic_change = (end_velocity @ mass @ end_velocity - velocity @ mass @ velocity) / 2
    assert step.contact_offset_work < 0.
    assert kinetic_change + potential(step.compression) < 0.
    assert kinetic_change + potential(step.compression) + step.damping_dissipation + step.elastic_numerical_dissipation + step.body_numerical_dissipation == pytest.approx(step.contact_offset_work, abs=1e-10)
