"""显式实体转子约束与完整机械账，独立核对中间轴刚性消元。"""

import math
from dataclasses import replace

import numpy as np
import pytest
from test_rotor_transport import CONFIG, INERTIA, TENSOR, frames
from test_tire_drivetrain import ENGINE_AXIS, audit

from driveline_inertia import active_inertias, inertia_projections, project_inertia, rotor_gradients
from rotor_dynamics import steering_torque
from tire_drivetrain import advance_drivetrain
from wheel_geometry import mechanical_axis

INERTIAS = (.03, .015, .02)
AXES = ((0., 1., 0.), (.6, .8, 0.), (0., .8, .6))


def explicit_axes(share, wheel_axes):
    weights = ((share / 2, share / 2, (1 - share) / 2, (1 - share) / 2),
               (.5, .5, 0., 0.), (0., 0., .5, .5))
    js = (INERTIAS[0], INERTIAS[1] if share > 0 else 0., INERTIAS[2] if share < 1 else 0.)
    rows = []
    for axis, w in zip(AXES, weights):
        rows.append([axis[a] + CONFIG.final_drive * sum(w[i] * wheel_axes[i][a] for i in range(4))
                     for a in range(3)] + [0., 0.] + [CONFIG.final_drive * value for value in w])
    return np.array(rows), js


@pytest.mark.parametrize("share", (0., .5, 1.))
@pytest.mark.parametrize("steer", (0., 25.))
def test_elimination_matches_explicit_rotors_and_constraints(share, steer):
    wheel_axes = tuple(f.spin_axis for f in frames(20., steer))
    rows, js = explicit_axes(share, wheel_axes)
    diagonal = np.array([*INERTIA, .2, .04, *([CONFIG.wheel_inertia] * 4)])
    active = [i for i, j in enumerate(js) if j]
    size = 9 + len(active)
    mass = np.diag([*diagonal, *(js[i] for i in active)])
    constraints = np.zeros((len(active), size))
    for k, i in enumerate(active):
        constraints[k, :9], constraints[k, 9 + k] = -rows[i], 1.
    kkt = np.block([[mass, -constraints.T], [constraints, np.zeros((len(active), len(active)))]])
    gradients = rotor_gradients(AXES, wheel_axes, share, CONFIG.final_drive, 5)
    inertias = active_inertias(INERTIAS, share)
    inverse = lambda v: tuple(np.array(v) / diagonal)
    projections = inertia_projections(inverse, gradients, inertias)
    for impulse in np.eye(9):
        actual = project_inertia(inverse(impulse), projections)
        explicit = np.linalg.solve(kkt, np.r_[impulse, np.zeros(2 * len(active))])
        assert actual == pytest.approx(explicit[:9], abs=1e-13)
    # 新几何下仍保留上一真实转子速度，不能将其重新投影为新约束初速。
    old = np.array([.12, -.08, .2, 500., 300., 36., 39., 33., 46.])
    old_speeds = rows @ old + np.array([4., -3., 2.])
    rhs = np.r_[diagonal * old, *(js[i] * old_speeds[i] for i in active), np.zeros(len(active))]
    explicit = np.linalg.solve(kkt, rhs)
    correction = sum((js[i] * rows[i] * (old_speeds[i] - rows[i] @ old) for i in active), np.zeros(9))
    actual = old + project_inertia(inverse(correction), projections)
    assert actual == pytest.approx(explicit[:9], abs=1e-11)
    assert math.dist(actual, old) > .01


def joint_case(share, compliance, mode, steer_change=True):
    damping = (20. if share else 0., 20. if share < 1 else 0., 20. if 0 < share < 1 else 0.)
    config = replace(CONFIG, front_drive_share=share, tire_compliance=compliance,
                     differential_damping=damping, differential_capacity=tuple(80. if c else 0. for c in damping))
    contact_frames = frames(20., 12., (0., 300., 5500., 5886.))
    old_axes = tuple(mechanical_axis((1., 0., 0.), (0., 1., 0.),
                     f.steering - (1. if steer_change and i < 2 else 0.)) for i, f in enumerate(contact_frames))
    velocity, angular, spins, engine, shaft = (.3, 12., .1), (.12, -.08, .2), (36., 39., 33., 46.), 500., 300.
    old_rows, js = explicit_axes(share, old_axes)
    initial = (*angular, engine, shaft, *spins)
    old_speeds = tuple(row @ initial if j else 0. for row, j in zip(old_rows, js))
    old_rotors = tuple(zip(old_speeds, js, AXES))
    deformation = ((.001, -.0002),) * 4
    ratio = 0. if mode == "neutral" else -12. if mode == "reverse" else 12.
    dt, torque, brakes = 1 / 240, 80., (100., 300., 50., 0.)
    steering = tuple(steering_torque(old_axes[i], f.spin_axis, spins[i], config.wheel_inertia, dt)
                     for i, f in enumerate(contact_frames))
    result = advance_drivetrain(velocity, angular, spins, engine, contact_frames, deformation,
        torque, 300., ratio, brakes, config, config, dt, inverse_inertia=TENSOR,
        engine_inertia=.2, engine_axis=ENGINE_AXIS, engine_drag=.12, efficiency=.88,
        shaft_omega=shaft, shaft_inertia=.04, shaft_axis=ENGINE_AXIS,
        synchronizing=mode == "synchronizing", synchronizer_capacity=20. if mode == "synchronizing" else 0.,
        steering_torques=steering, downstream_omega=old_speeds, downstream_inertias=INERTIAS, downstream_axes=AXES)
    arguments = (velocity, angular, spins, engine, contact_frames, deformation, torque, brakes, config, dt,
                 old_axes, steering)
    audit(result, *arguments, shaft=shaft, downstream=old_rotors)
    return result, arguments, old_rotors


@pytest.mark.parametrize("share", (0., .5, 1.))
@pytest.mark.parametrize("compliance", (False, True))
@pytest.mark.parametrize("mode", ("engaged", "neutral", "synchronizing", "reverse"))
def test_downstream_rotors_joint_energy_momentum_and_steering(share, compliance, mode):
    result, _arguments, old = joint_case(share, compliance, mode)
    assert sum(result.downstream_kinetic_energy) > 0.
    assert any(abs(t) > 0. for t in result.downstream_wheel_torques)
    if mode == "neutral":
        assert result.drive_torque == 0.
        assert result.downstream_omega != tuple(row[0] for row in old)


@pytest.mark.parametrize("omitted", ("reaction", "storage", "wheel-torque"))
def test_independent_mechanical_account_detects_omitted_inertia(omitted):
    result, arguments, old = joint_case(.5, True, "neutral")
    incomplete = replace(result, **{
        "reaction": {"downstream_body_torque": (0.,) * 3},
        "storage": {"downstream_kinetic_energy": (0.,) * 3},
        "wheel-torque": {"downstream_wheel_torques": (0.,) * 4},
    }[omitted])
    with pytest.raises(AssertionError):
        audit(incomplete, *arguments, shaft=300., downstream=old)
