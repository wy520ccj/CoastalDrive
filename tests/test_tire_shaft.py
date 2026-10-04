"""实体输入轴与四轮共同接触、限滑和制动的独立机械账。"""

from dataclasses import replace

import pytest
from test_rotor_transport import CONFIG, TENSOR, frames
from test_tire_drivetrain import ENGINE_AXIS, ENGINE_INERTIA, audit

from tire_drivetrain import advance_drivetrain


@pytest.mark.parametrize("share", (0., .5, 1.))
@pytest.mark.parametrize("compliance", (False, True))
@pytest.mark.parametrize("mode", ("engaged", "neutral", "synchronizing"))
@pytest.mark.parametrize("ratio_sign", (-1, 1))
def test_real_shaft_joint_tire_brake_and_limited_differential_balance(share, compliance, mode, ratio_sign):
    damping = (20. if share else 0., 20. if share < 1 else 0., 20. if 0 < share < 1 else 0.)
    config = replace(CONFIG, front_drive_share=share, tire_compliance=compliance,
                     differential_damping=damping, differential_capacity=tuple(80. if c else 0. for c in damping))
    contact_frames = frames(20., 12., (0., 300., 5500., 5886.))
    deformation = ((.001, -.0002),) * 4
    velocity, angular = (.3, ratio_sign * 12., .1), (.12, -.08, .2)
    spins, engine, shaft = (36., 39., 33., 46.), 500., 300.
    ratio = 0. if mode == "neutral" else ratio_sign * 12.
    torque, brakes, dt = 80., (100., 300., 50., 0.), 1 / 240
    steering = ((0., 0., 0.),) * 4
    result = advance_drivetrain(velocity, angular, spins, engine, contact_frames, deformation,
        torque, 300., ratio, brakes, config, config, dt, inverse_inertia=TENSOR,
        engine_inertia=ENGINE_INERTIA, engine_axis=ENGINE_AXIS, engine_drag=.12, efficiency=.88,
        shaft_omega=shaft, shaft_inertia=.04, shaft_axis=ENGINE_AXIS,
        synchronizing=mode == "synchronizing", synchronizer_capacity=20. if mode == "synchronizing" else 0.)
    audit(result, velocity, angular, spins, engine, contact_frames, deformation, torque, brakes, config, dt,
          tuple(f.spin_axis for f in contact_frames), steering, shaft=shaft)
    assert result.synchronizer_heat >= -1e-9
    assert result.gear_heat >= -1e-9
    if mode == "engaged":
        driven_speed = sum(config.drive_weights[i] * wheel.relative_omega for i, wheel in enumerate(result.wheels))
        assert result.shaft_relative_omega == pytest.approx(ratio * driven_speed, abs=1e-11)
        assert result.drive_torque == pytest.approx(ratio * (result.gear_reaction - result.gear_loss_torque), abs=1e-10)
    elif mode == "neutral":
        assert result.gear_reaction == result.drive_torque == 0.
        assert result.shaft_omega != shaft
    else:
        assert abs(result.gear_reaction) <= 20. + 1e-11
        assert result.synchronizer_heat == pytest.approx(dt * result.gear_reaction * result.synchronizer_slip, abs=1e-11)


def test_real_shaft_neutral_clutch_never_locks_engine_to_fictitious_zero_speed():
    result = advance_drivetrain((0.,) * 3, (0.,) * 3, (0.,) * 4, 100., frames(0., 0., (0.,) * 4),
        ((0., 0.),) * 4, 0., 300., 0., (0.,) * 4, CONFIG, CONFIG, 1 / 120,
        inverse_inertia=TENSOR, engine_inertia=.2, engine_axis=ENGINE_AXIS, engine_drag=0., efficiency=.88,
        shaft_omega=0., shaft_inertia=.04, shaft_axis=ENGINE_AXIS)
    assert result.engine_omega == pytest.approx(87.5, abs=1e-12)
    assert result.shaft_omega == pytest.approx(62.5, abs=1e-12)
    assert result.clutch_slip == pytest.approx(25., abs=1e-12)
    assert result.shaft_body_torque[1] == -300.
    assert result.engine_body_torque[1] == 300.
    assert result.angular == (0.,) * 3
