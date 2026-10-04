"""有限粘性限滑的解析极限、共同机械账与转向轴壳体反力。"""

import json
from dataclasses import replace

import pytest
from physics.reference_ab import _create_vehicle, _step
from physics.testbed import load_vehicle_config
from test_rotor_transport import CONFIG, frames
from test_tire_drivetrain import audit, solve

from driving_modes import DrivingMode
from vehicle_config import CAR
from vehicle_state import VehicleCommand


@pytest.mark.parametrize("difference", (-100., -2., 2., 100.))
@pytest.mark.parametrize("dt", (1 / 240, .1))
def test_rear_viscous_or_saturated_transfer_has_exact_free_wheel_solution(difference, dt):
    config = replace(CONFIG, differential_damping=(0., 12., 0.), differential_capacity=(0., 80., 0.))
    spins = (0., 0., difference / 2, -difference / 2)
    contact_frames = frames(0., 0., (0.,) * 4)
    result = solve((0.,) * 3, (0.,) * 3, spins, 100., contact_frames, ((0., 0.),) * 4,
                   0., 300., 0., (0.,) * 4, config, dt, drag=0.)
    expected_torque = max(-80., min(80., 12. * difference / (1 + 2 * dt * 12. / config.wheel_inertia)))
    end_difference = difference - 2 * dt * expected_torque / config.wheel_inertia
    assert result.differential_torques[1] == pytest.approx(expected_torque, abs=1e-11)
    assert result.wheels[2].omega - result.wheels[3].omega == pytest.approx(end_difference, abs=1e-12)
    assert end_difference * difference > 0
    assert result.differential_heat[1] == pytest.approx(dt * expected_torque * end_difference, abs=1e-11)
    assert sum(result.wheel_drive_torques) == 0.
    assert result.engine_omega == 100.


@pytest.mark.parametrize("share", (0., 1., .3, .5))
@pytest.mark.parametrize("ratio", (-12., 0., 12.))
@pytest.mark.parametrize("compliance", (False, True))
def test_all_enabled_limited_ports_share_tire_clutch_brake_and_body_state(share, ratio, compliance):
    damping = (20. if share else 0., 20. if share < 1 else 0., 20. if 0 < share < 1 else 0.)
    limits = tuple(80. if c else 0. for c in damping)
    config = replace(CONFIG, front_drive_share=share, tire_compliance=compliance,
                     differential_damping=damping, differential_capacity=limits)
    contact_frames = frames(20., 23., (2943., 0., 4500., 300.))
    contact_frames[1] = frames(20., 27., (2943., 0., 4500., 300.))[1]
    velocity, angular, spins, engine = (.3, 12., 0.), (.03, -.02, .2), (36., 58., 32., 47.), 500.
    deformation, brakes, steering, dt = ((0., 0.),) * 4, (100., 0., 200., 0.), ((0., 0., 0.),) * 4, 1 / 240
    result = solve(velocity, angular, spins, engine, contact_frames, deformation, 120., 300., ratio,
                   brakes, config, dt)
    audit(result, velocity, angular, spins, engine, contact_frames, deformation, 120., brakes,
          config, dt, tuple(f.spin_axis for f in contact_frames), steering)
    for torque, slip, heat, c, limit in zip(result.differential_torques, result.differential_slips,
                                          result.differential_heat, damping, limits):
        assert torque == pytest.approx(max(-limit, min(limit, c * slip)), abs=1e-11)
        assert heat == pytest.approx(dt * torque * slip, abs=1e-11)
        assert heat >= 0.


@pytest.mark.parametrize("changes", [
    {"differential_damping": (0., -1., 0.)},
    {"differential_capacity": (0., float("nan"), 0.)},
    {"differential_damping": (1., 2.)},
    {"differential_damping": (20., 0., 0.), "differential_capacity": (80., 0., 0.)},
    {"differential_damping": (0., 0., 20.), "differential_capacity": (0., 0., 80.)},
    {"finite_drivetrain": False, "differential_damping": (0., 20., 0.), "differential_capacity": (0., 80., 0.)},
])
def test_invalid_or_absent_mechanical_port_is_rejected_at_config_boundary(changes):
    with pytest.raises(ValueError):
        replace(CAR, **changes)


def test_json_restores_immutable_differential_parameters(tmp_path):
    path = tmp_path / "limited.json"
    path.write_text(json.dumps({"differential_damping": [0., 12., 0.],
                                "differential_capacity": [0., 80., 0.]}), encoding="utf-8")
    config = load_vehicle_config(path, CAR)
    assert config.differential_damping == (0., 12., 0.)
    assert config.differential_capacity == (0., 80., 0.)


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("share", (0., 1., .5))
def test_native_split_mu_limited_drive_and_reset(mode, share):
    base = mode.vehicle_config
    damping = (20. if share else 0., 20. if share < 1 else 0., 20. if 0 < share < 1 else 0.)
    limits = tuple(80. if c else 0. for c in damping)
    config = replace(base, front_drive_share=share, differential_damping=damping,
                     differential_capacity=limits, grass_friction=.2,
                     traction=replace(base.traction, tcs_enabled=False))
    world, car = _create_vehicle(config)
    car.on_asphalt = lambda x, _y: x < 0
    active, heat = False, 0.
    try:
        for _ in range(180):
            _step(world, car, VehicleCommand(throttle=1., direction=1, steering=3.))
            state = car.snapshot()
            train = state.powertrain_state
            active |= any(abs(torque) > 1e-6 for torque in train.differential_torques)
            heat += sum(train.differential_heat)
            assert all(abs(torque) <= cap + 1e-11 for torque, cap in zip(train.differential_torques, limits))
            assert all(value >= 0. for value in train.differential_heat)
            assert all(w.force_residual < .001 for w in state.wheel_dynamics)
        assert active and heat > 0.
        before = car.powertrain.snapshot()
        car.shift(1000.)
        assert car.powertrain.snapshot() == before
        car.reset((0., 0., .55))
        assert car.powertrain.snapshot().differential_heat == (0.,) * 3
        assert car.config is config
    finally:
        car.close()
