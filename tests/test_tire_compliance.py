"""串联弹性/路面元件的解析松弛、静止约束及轮-车体总能量。"""

import math
from dataclasses import replace

import numpy as np
import pytest

from tire_compliance import (
    contact_force,
    deformation_frame,
    energy_terms,
    project_deformation,
    world_deformation,
)
from tire_forces import tire_force
from vehicle_config import CAR
from wheel_dynamics import Mobility, _solve_force, advance_wheel

CONFIG = replace(CAR, tire_compliance=True)
LOAD = CAR.mass * 9.81 / 4
MASS = np.array(((300., 0., 0.), (0., 320., 12.), (0., 12., 50.)))
INVERSE = np.linalg.inv(MASS)
MOBILITY = Mobility(INVERSE[0, 0], INVERSE[0, 1], INVERSE[0, 2],
                    INVERSE[1, 1], INVERSE[1, 2], INVERSE[2, 2])


@pytest.mark.parametrize("axis,coefficient", [(0, CAR.longitudinal_stiffness), (1, CAR.lateral_stiffness)])
def test_linear_relaxation_time_and_steady_force(axis, coefficient):
    speed, h, slip = 20., .001, [0., 0.]
    slip[axis] = .00002
    old = (0., 0.)
    final = coefficient * slip[axis] / speed
    time_constant = (coefficient / speed + CONFIG.tire_contact_damping) / CONFIG.tire_contact_stiffness
    initial = CONFIG.tire_contact_damping * slip[axis] / (1 + CONFIG.tire_contact_damping * speed / coefficient)
    for tick in range(1, 81):
        def residual(fx, fy, prior=old):
            target, *_ = contact_force((fx, fy), prior, slip, speed, True, 1.1 * LOAD,
                                       CAR.longitudinal_stiffness, CAR.lateral_stiffness, h,
                                       CONFIG.tire_contact_stiffness, CONFIG.tire_contact_damping,
                                       CAR.tire_shape, CAR.tire_curvature)
            return fx - target[0], fy - target[1]
        fx, fy, error = _solve_force(residual)
        _, old, *_ = contact_force((fx, fy), old, slip, speed, True, 1.1 * LOAD,
                                  CAR.longitudinal_stiffness, CAR.lateral_stiffness, h,
                                  CONFIG.tire_contact_stiffness, CONFIG.tire_contact_damping,
                                  CAR.tire_shape, CAR.tire_curvature)
        expected = final + (initial - final) / (1 + h / time_constant) ** tick
        assert (fx, fy)[axis] == pytest.approx(expected, abs=2e-8)
        assert error < .001


@pytest.mark.parametrize("deformation", [(0., 0.), (.01, -.004), (-.02, .006)])
@pytest.mark.parametrize("speed,omega,side,drive,brake", [
    (20., 60., .3, 150., 0.), (-12., -34., -.4, -100., 120.),
    (0., 0., 0., 40., 0.), (0., 0., 0., 0., 1000.),
])
@pytest.mark.parametrize("load", [0., .01 * LOAD, LOAD, 2 * LOAD])
def test_coupled_momentum_and_elastic_energy_ledger(deformation, speed, omega, side, drive, brake, load):
    h = 1 / 240
    before = np.array((speed, side, .1))
    step = advance_wheel(omega, *before, drive, brake, load, .45, MOBILITY, h, CONFIG, deformation)
    after = np.array((step.vx, step.vy, step.body_omega))
    change = (.5 * after @ MASS @ after + .5 * CAR.wheel_inertia * step.omega**2
              - .5 * before @ MASS @ before - .5 * CAR.wheel_inertia * omega**2)
    old_energy = .5 * CONFIG.tire_contact_stiffness * sum(v * v for v in deformation)
    body_delta = after - before
    omega_delta = step.omega - omega
    mechanical_numerical = .5 * body_delta @ MASS @ body_delta + .5 * CAR.wheel_inertia * omega_delta**2
    expected = (h * (drive - step.brake_torque) * step.relative_omega
                - step.material_dissipation - step.road_dissipation
                - step.elastic_numerical_dissipation - mechanical_numerical)
    assert change + step.elastic_energy - old_energy == pytest.approx(expected, abs=2e-9)
    assert body_delta == pytest.approx(h * INVERSE @ np.array((step.fx, step.fy, drive - step.brake_torque)), abs=1e-10)
    assert CAR.wheel_inertia * omega_delta == pytest.approx(h * (drive - step.brake_torque - CAR.wheel_radius * step.fx))
    capacity = 0 if load == 0 else .45 * load * (load / LOAD) ** (CAR.tire_peak_load_exponent - 1)
    assert math.hypot(step.fx, step.fy) <= capacity + .001
    assert step.road_dissipation >= -1e-7
    assert step.material_dissipation >= 0 and step.elastic_numerical_dissipation >= 0
    assert step.residual < .001


def test_airborne_free_relaxation_loses_energy_without_contact_impulse():
    initial = (.015, -.01)
    h = 1 / 240
    step = advance_wheel(30, 10, .4, .1, 0, 0, 0, 1.1, MOBILITY, h, CONFIG, initial)
    ratio = CONFIG.tire_contact_damping / (CONFIG.tire_contact_damping + CONFIG.tire_contact_stiffness * h)
    assert (step.deformation_x, step.deformation_y) == pytest.approx(tuple(ratio * v for v in initial))
    assert (step.fx, step.fy) == (0, 0)
    assert step.omega == 30 and step.vx == 10 and step.vy == .4
    assert step.mode == "airborne"
    assert step.elastic_energy < .5 * CONFIG.tire_contact_stiffness * sum(v * v for v in initial)


def test_stored_contact_energy_can_return_to_mechanical_motion():
    initial = (0., .012)
    step = advance_wheel(0, 0, 0, 0, 0, 0, LOAD, 1.1, MOBILITY, 1 / 240, CONFIG, initial)
    after = np.array((step.vx, step.vy, step.body_omega))
    kinetic = .5 * after @ MASS @ after + .5 * CAR.wheel_inertia * step.omega**2
    energy = .5 * CONFIG.tire_contact_stiffness * initial[1] ** 2
    assert kinetic > 0
    assert step.elastic_energy + kinetic < energy


def test_static_contact_has_zero_patch_slip_and_finite_deflection():
    step = advance_wheel(0, 0, 0, 0, 40, 0, LOAD, 1.1, MOBILITY, 1 / 240, CONFIG)
    assert step.mode == "compliant-sticking"
    assert step.patch_kappa == pytest.approx(0, abs=1e-8)
    assert step.patch_alpha == pytest.approx(0, abs=1e-8)
    assert step.deformation_x > 0
    assert CAR.wheel_radius * step.omega - step.vx > 0


def test_large_steady_slip_keeps_original_magic_formula_curve():
    slip = (.15 * 20, -.12 * 20)
    expected = tire_force(.15, math.atan(.12), LOAD, 1.1)
    old = (0., 0.)
    h = 1 / 240
    for _ in range(480):
        def residual(fx, fy, prior=old):
            target, *_ = contact_force((fx, fy), prior, slip, 20, True, 1.1 * LOAD,
                                       CAR.longitudinal_stiffness, CAR.lateral_stiffness, h,
                                       CONFIG.tire_contact_stiffness, CONFIG.tire_contact_damping,
                                       CAR.tire_shape, CAR.tire_curvature)
            return fx - target[0], fy - target[1]
        fx, fy, _ = _solve_force(residual)
        previous = old
        _, old, rate, patch, *_ = contact_force((fx, fy), previous, slip, 20, True, 1.1 * LOAD,
                                               CAR.longitudinal_stiffness, CAR.lateral_stiffness, h,
                                               CONFIG.tire_contact_stiffness, CONFIG.tire_contact_damping,
                                               CAR.tire_shape, CAR.tire_curvature)
        energy, material, road, numerical = energy_terms((fx, fy), previous, old, rate, patch, h,
                                                        CONFIG.tire_contact_stiffness, CONFIG.tire_contact_damping)
        previous_energy = .5 * CONFIG.tire_contact_stiffness * sum(v * v for v in previous)
        work = h * (fx * slip[0] + fy * slip[1])
        assert work == pytest.approx(energy - previous_energy + material + road + numerical, abs=1e-10)
    assert (fx, fy) == pytest.approx(expected, abs=.001)


def test_tangent_frame_rotation_preserves_energy_and_normal_projection_dissipates():
    elastic = (.015, -.009, .007)
    initial_energy = .5 * CONFIG.tire_contact_stiffness * sum(v * v for v in elastic)
    frame = deformation_frame((0, 1, 0), (0, 0, 1))
    local, loss = project_deformation(elastic, frame, CONFIG.tire_contact_stiffness)
    elastic = world_deformation(local, frame)
    energy = .5 * CONFIG.tire_contact_stiffness * sum(v * v for v in elastic)
    assert energy + loss == pytest.approx(initial_energy, abs=1e-13)
    for index in range(2000):
        angle = index * .02
        frame = deformation_frame((math.sin(angle), math.cos(angle), 0), (0, 0, 1))
        local, loss = project_deformation(elastic, frame, CONFIG.tire_contact_stiffness)
        assert loss == 0
        elastic = world_deformation(local, frame)
    assert .5 * CONFIG.tire_contact_stiffness * sum(v * v for v in elastic) == pytest.approx(energy, abs=1e-10)
