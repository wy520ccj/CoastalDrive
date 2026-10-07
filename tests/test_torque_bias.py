"""真实末端负载控制偏置上限；独立能量／角动量账与逐轮矩约束。"""

from dataclasses import replace

import pytest
from test_driveline_inertia import AXES, INERTIAS, explicit_axes
from test_rotor_transport import CONFIG, TENSOR, frames
from test_tire_drivetrain import ENGINE_AXIS, ENGINE_INERTIA, audit

from differential import torque_bias_capacities
from tire_drivetrain import advance_drivetrain


def test_tbr_capacity_matches_two_output_ratio_and_vanishes_without_load():
    assert torque_bias_capacities((1000., 1000.), (2., 3.), (300., -400.)) == pytest.approx((50., 100.))
    assert torque_bias_capacities((1000., 1000.), (2., 3.), (0., 0.)) == (0., 0.)
    assert torque_bias_capacities((1000., 1000.), (1., 1.), (0., 0.)) == (1000., 1000.)
    for ratio in (2., 3., 5.):
        transfer, = torque_bias_capacities((1000.,), (ratio,), (400.,))
        assert (200. + transfer) / (200. - transfer) == pytest.approx(ratio)


@pytest.mark.parametrize("direction", (-1., 1.))
@pytest.mark.parametrize("compliance", (False, True))
@pytest.mark.parametrize("downstream", (False, True))
def test_load_dependent_bias_preserves_joint_mechanical_account(direction, compliance, downstream):
    config = replace(CONFIG, front_drive_share=0., tire_compliance=compliance,
                     differential_damping=(0., 300., 0.), differential_capacity=(0., 1000., 0.),
                     axle_torque_bias_ratios=(1., 3.))
    contact_frames = frames(direction * 12., 3., (2943., 2943., 5000., 800.))
    velocity, angular = (.3, direction * 12., .1), (.12, -.08, .2)
    spins, engine, shaft = tuple(direction * w for w in (36., 39., 33., 65.)), 500., 300.
    deformation, brakes, dt = ((.001, -.0002),) * 4, (0., 0., 0., 0.), 1 / 240
    steering = ((0., 0., 0.),) * 4
    extra = {}
    rotors = None
    if downstream:
        rows, inertias = explicit_axes(0., tuple(f.spin_axis for f in contact_frames))
        speeds = tuple(row @ (*angular, engine, shaft, *spins) if j else 0. for row, j in zip(rows, inertias))
        rotors = tuple(zip(speeds, inertias, AXES))
        extra = {"downstream_omega": speeds, "downstream_inertias": INERTIAS, "downstream_axes": AXES}
    result = advance_drivetrain(velocity, angular, spins, engine, contact_frames, deformation,
        120., 300., direction * 12., brakes, config, config, dt, inverse_inertia=TENSOR,
        engine_inertia=ENGINE_INERTIA, engine_axis=ENGINE_AXIS, engine_drag=.12, efficiency=.88,
        shaft_omega=shaft, shaft_inertia=.04, shaft_axis=ENGINE_AXIS, **extra)
    audit(result, velocity, angular, spins, engine, contact_frames, deformation, 120., brakes,
          config, dt, tuple(f.spin_axis for f in contact_frames), steering, shaft=shaft, downstream=rotors)
    total = sum(result.wheel_drive_torques[2:])
    assert abs(result.differential_torques[1]) <= abs(total) / 4 + 1e-11
    assert result.differential_heat[1] >= -1e-9
    assert result.differential_torques[0] == result.differential_torques[2] == 0.
