"""布局共用真实机械端口；独立守恒账与原生逐轮输出核对。"""

import json
import math
from dataclasses import replace

import pytest
from panda3d.bullet import BulletRigidBodyNode
from panda3d.core import TransformState, Vec3
from physics.reference_ab import _create_vehicle, _step
from physics.testbed import load_vehicle_config
from test_rotor_transport import CONFIG, frames
from test_tire_drivetrain import audit, solve
from test_vehicle_traction import wheels

from driving_modes import DrivingMode
from vehicle_config import CAR
from vehicle_state import VehicleCommand
from vehicle_tires import Tires
from vehicle_traction import TractionControl


@pytest.mark.parametrize("share", (0., .3, .5, 1.))
@pytest.mark.parametrize("ratio", (-12., 12.))
@pytest.mark.parametrize("compliance", (False, True))
def test_layout_conserves_energy_and_momentum_with_steered_driven_wheels(share, ratio, compliance):
    config = replace(CONFIG, front_drive_share=share, tire_compliance=compliance)
    contact_frames = frames(20., 25., (2943., 0., 4500., 300.))
    velocity, angular, spins, engine = (.3, 12., 0.), (.03, -.02, .2), (36., 58., 32., 47.), 500.
    deformation, brakes, steering = ((0., 0.),) * 4, (100., 0., 200., 0.), ((0., 0., 0.),) * 4
    dt = 1 / 240
    result = solve(velocity, angular, spins, engine, contact_frames, deformation,
                   120., 300., ratio, brakes, config, dt)
    audit(result, velocity, angular, spins, engine, contact_frames, deformation, 120., brakes,
          config, dt, tuple(f.spin_axis for f in contact_frames), steering)
    expected_speed = ratio * sum((share if i < 2 else 1 - share) / 2
        * (w.omega + sum(result.angular[a] * f.spin_axis[a] for a in range(3)))
        for i, (w, f) in enumerate(zip(result.wheels, contact_frames)))
    assert result.gear_input_speed == pytest.approx(expected_speed, abs=1e-12)


@pytest.mark.parametrize("share", (0., .3, .5, 1.))
def test_open_axles_and_center_do_not_lock_wheel_speed(share):
    config = replace(CONFIG, front_drive_share=share)
    contact_frames = frames(0., 0., (0.,) * 4)
    spins, dt = (10., 30., 50., 90.), 1 / 240
    result = solve((0.,) * 3, (0.,) * 3, spins, 500., contact_frames, ((0., 0.),) * 4,
                   120., 300., 12., (0.,) * 4, config, dt, drag=0.)
    for i, wheel in enumerate(result.wheels):
        actual = config.wheel_inertia * (wheel.omega - spins[i]) / dt
        assert actual == pytest.approx(result.drive_torque * (share if i < 2 else 1 - share) / 2, abs=1e-10)
    assert result.wheels[1].omega - result.wheels[0].omega == pytest.approx(20., abs=1e-12)
    assert result.wheels[3].omega - result.wheels[2].omega == pytest.approx(40., abs=1e-12)


@pytest.mark.parametrize("share,driven", ((0., (2, 3)), (1., (0, 1)), (.3, (0, 1, 2, 3))))
@pytest.mark.parametrize("direction", (-1, 1))
def test_tcs_ignores_free_wheel_slip_and_brakes_only_driven_wheels(share, driven, direction):
    config = replace(CAR, front_drive_share=share)
    assert config.driven_wheels == driven
    for slipping in range(4):
        sample = list(wheels(direction=direction))
        sample[slipping] = replace(sample[slipping], omega=direction * 60.)
        control = TractionControl(config.traction, config.driven_wheels)
        state = control.advance(1., direction, False, sample, .33, 1 / 120)
        assert state.active is (slipping in driven)
        assert tuple(i for i, request in enumerate(state.brake_requests) if request) == (
            (slipping,) if slipping in driven else ())


@pytest.mark.parametrize("share", (.3, 1.))
def test_launch_feedback_uses_current_mechanical_front_axes(share):
    body = BulletRigidBodyNode("布局轴速试验")
    body.setTransform(TransformState.makeHpr(Vec3(15, 12, 20)))
    body.setAngularVelocity(Vec3(.2, -.1, .3))
    tires = Tires(replace(CAR, front_drive_share=share))
    tires.omega = [10., 30., 50., 90.]
    angles = (23., 27., 0., 0.)
    pose = body.getTransform().getQuat()
    expected = 0.
    for i, angle in enumerate(angles):
        axis = pose.getRight() * math.cos(math.radians(angle)) - pose.getForward() * math.sin(math.radians(angle))
        axis.normalize()
        expected += (share if i < 2 else 1 - share) / 2 * (tires.omega[i] + body.getAngularVelocity().dot(axis))
    assert tires.driven_omega(body, angles) == pytest.approx(expected, abs=2e-8)


@pytest.mark.parametrize("share", (-.1, 1.1, float("nan")))
def test_invalid_layout_is_rejected_at_config_boundary(share):
    with pytest.raises(ValueError, match="份额"):
        replace(CAR, front_drive_share=share)


def test_json_layout_and_legacy_branch_boundary(tmp_path):
    path = tmp_path / "layout.json"
    path.write_text(json.dumps({"front_drive_share": .3}), encoding="utf-8")
    config = load_vehicle_config(path, CAR)
    assert config.drive_weights == (.15, .15, .35, .35)
    with pytest.raises(ValueError, match="仅支持后驱"):
        replace(config, finite_drivetrain=False)


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("share", (0., .5, 1.))
@pytest.mark.parametrize("gear", (-1, 1))
def test_native_layout_launch_outputs_and_reset(mode, share, gear):
    config = replace(mode.vehicle_config, front_drive_share=share)
    world, vehicle = _create_vehicle(config)
    try:
        for _ in range(180):
            _step(world, vehicle, VehicleCommand(throttle=.7, direction=gear, gear=gear, steering=3.))
            snapshot = vehicle.snapshot()
            for i, wheel in enumerate(snapshot.wheel_dynamics):
                assert wheel.drive_torque == pytest.approx(snapshot.powertrain_state.drive_torque
                    * (share if i < 2 else 1 - share) / 2
                    + snapshot.powertrain_state.downstream_wheel_torques[i], abs=1e-10)
                assert wheel.force_residual < .001
        assert gear * vehicle.signed_speed() > .1
        engine_before = vehicle.powertrain.snapshot()
        omega_before = tuple(vehicle.tires.omega)
        vehicle.shift(1000.)
        assert vehicle.powertrain.snapshot() == engine_before
        assert tuple(vehicle.tires.omega) == omega_before
        assert vehicle.traction.driven_wheels == config.driven_wheels
        vehicle.reset((0., 0., .55))
        assert vehicle.traction.driven_wheels == config.driven_wheels
        assert vehicle.tires.config is config
    finally:
        vehicle.close()
