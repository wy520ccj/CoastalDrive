"""从接点速度、硬件及完整机械账核对法向/切向共同末状态。"""

import math
from dataclasses import replace

import pytest
from panda3d.core import TransformState, Vec3
from physics.reference_ab import _create_vehicle
from test_driveline_inertia import AXES, INERTIAS, explicit_axes
from test_finite_suspension import endpoint_length
from test_rotor_transport import CONFIG, TENSOR, frames
from test_tire_drivetrain import audit

from driving_modes import DrivingMode
from rotor_dynamics import cross, dot
from suspension import SuspensionInput
from suspension_kinematics import SupportPlane
from tire_drivetrain import advance_drivetrain
from vehicle_state import FIXED_DT, VehicleCommand


@pytest.mark.parametrize("bank", (-20., 20.))
@pytest.mark.parametrize("share", (0., .5, 1.))
@pytest.mark.parametrize("dt", (1 / 120, 1 / 240))
@pytest.mark.parametrize("finite_rotation", (False, True))
def test_joint_hardware_kinematics_and_full_rotor_energy(bank, share, dt, finite_rotation):
    config = replace(CONFIG, front_drive_share=share)
    contact_frames = frames(bank, 17.)
    normal = (math.sin(math.radians(bank)), 0., math.cos(math.radians(bank)))
    alignment = normal[2]
    gradients = tuple(tuple(n / alignment for n in normal)
                      + tuple(value / alignment for value in cross(frame.point, normal))
                      for frame in contact_frames)
    initial = (.064, .047, .067, .05)
    system = SuspensionInput(initial, initial, gradients, (True,) * 4, (alignment,) * 4, config)
    if finite_rotation:
        direction = (0., 0., -1.)
        planes = tuple(SupportPlane(tuple(frame.point[a] - (.4 - initial[i]) * direction[a]
                                         + config.wheel_radius * normal[a] for a in range(3)),
                                    direction, normal, .4 - initial[i]) for i, frame in enumerate(contact_frames))
        system = replace(system, kinematics=planes, angular_damping=.2)
    velocity, angular, spins, engine = (.3, 20., -.2), (.04, -.06, .17), (61., 60., 62., 59.), 175.
    deformation = ((.002, -.001),) * 4
    brakes = (200., 300., 120., 150.)
    result = advance_drivetrain(velocity, angular, spins, engine, contact_frames, deformation,
        85., 120., 3.2, brakes, config, replace(config, lateral_stiffness=config.rear_lateral_stiffness), dt,
        inverse_inertia=TENSOR, engine_inertia=.2, engine_axis=(0., 1., 0.), engine_drag=.12,
        efficiency=.88, shaft_omega=180., shaft_inertia=.04, shaft_axis=(0., 1., 0.), suspension=system)
    step = result.suspension
    # 从实际表面点的六维速度展开，不用生产的悬架速度雅可比求期望。
    for i, frame in enumerate(contact_frames):
        point_velocity = tuple(result.velocity[a] + cross(result.angular, frame.point)[a] for a in range(3))
        expected = initial[i] - dt * dot(point_velocity, normal) / alignment
        if finite_rotation:
            expected = .4 - endpoint_length(planes[i], result.velocity, result.angular, dt, system.angular_damping)
        assert step.compression[i] == pytest.approx(expected, abs=1e-13)
        dx = expected - initial[i]
        damping = config.suspension_compression_damping[i] if dx >= 0 else config.suspension_extension_damping[i]
        other = i ^ 1
        force = (config.suspension_spring_rates[i] * expected
                 + config.suspension_antiroll_rates[i // 2] * (expected - step.compression[other])
                 + damping * dx / dt)
        assert step.axial_force[i] == pytest.approx(force, abs=1e-8)
    effective = result.suspension_system
    loaded = tuple(replace(frame, load=force / a) for frame, force, a in zip(contact_frames, step.axial_force, effective.alignment))
    assert result.normal_residual < 1e-8
    assert step.body_numerical_dissipation == 0.
    audit(result, velocity, angular, spins, engine, loaded, deformation, 85., brakes, config, dt,
          tuple(frame.spin_axis for frame in loaded), ((0.,) * 3,) * 4, shaft=180., normal=(effective, step))


@pytest.mark.parametrize("mode", list(DrivingMode))
def test_actual_bullet_submission_matches_joint_six_dimensional_end(mode, monkeypatch):
    import vehicle_tires

    observed = []
    original = vehicle_tires.advance_drivetrain

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        observed.append((result.suspension_system, result))
        return result

    monkeypatch.setattr(vehicle_tires, "advance_drivetrain", capture)
    _world, car = _create_vehicle(mode.vehicle_config)
    try:
        # 仅试验初始条件：带真实倾角、车速、轮速及角速度，不在运行中改写状态。
        car._chassis.setTransform(TransformState.makePosHpr(Vec3(0, 0, .4), Vec3(0, 0, 3)))
        car._chassis.setLinearVelocity(Vec3(.2, 12., -.1))
        car._chassis.setAngularVelocity(Vec3(.15, -.1, .02))
        car.tires.initialize_rolling(12.)
        car.apply_command(VehicleCommand(steering=.25, throttle=.3, gear=1, clutch=.7))
        pending_v = car._chassis.getGravity() * FIXED_DT + car._chassis.getTotalForce() / car.config.mass * FIXED_DT
        pending_w = car._chassis.getInvInertiaTensorWorld().xform(car._chassis.getTotalTorque()) * FIXED_DT
        final = observed[-1][1]
        assert len(observed) == car.config.tire_substeps
        assert tuple(car._chassis.getLinearVelocity() + pending_v) == pytest.approx(final.velocity, abs=2e-6)
        assert tuple(car._chassis.getAngularVelocity() + pending_w) == pytest.approx(final.angular, abs=2e-7)
        for system, result in observed:
            assert result.normal_residual < 1e-8
            for i, (gradient, touching) in enumerate(zip(system.gradients, system.touching)):
                if touching and result.suspension.axial_force[i] > 0.:
                    assert result.suspension.compression[i] == pytest.approx(
                        system.geometry[i] - FIXED_DT / car.config.tire_substeps
                        * sum(a * b for a, b in zip(gradient, result.velocity + result.angular)), abs=1e-12)
        state = car.suspension.state
        assert len(state.substeps) == car.config.tire_substeps
        assert state.force_tick == 1
        for contact, tire, load in zip(car._wheel_contacts, car.tires.states, state.normal_force):
            assert contact.normal_load == tire.normal_load == load
            assert tire.force_contact_tick == state.force_tick
            assert tire.force_residual < .001
    finally:
        car.close()


@pytest.mark.parametrize("share", (0., .5, 1.))
def test_normal_coupling_keeps_downstream_storage_and_airborne_material(share):
    config = replace(CONFIG, front_drive_share=share)
    contact_frames = frames(20., 17.)
    normal = (math.sin(math.radians(20.)), 0., math.cos(math.radians(20.)))
    gradients = tuple(((0.,) * 6 if i == 0 else tuple(n / normal[2] for n in normal)
                      + tuple(value / normal[2] for value in cross(frame.point, normal)))
                      for i, frame in enumerate(contact_frames))
    initial = (.032, .058, .072, .041)
    system = SuspensionInput(initial, initial, gradients, (False, True, True, True), (normal[2],) * 4, config)
    velocity, angular, spins, engine, shaft = (.3, 12., -.1), (.12, -.08, .2), (36., 39., 33., 46.), 500., 300.
    old_axes = tuple(frame.spin_axis for frame in contact_frames)
    rows, inertias = explicit_axes(share, old_axes)
    old_speeds = tuple(row @ (*angular, engine, shaft, *spins) if j else 0. for row, j in zip(rows, inertias))
    dt, torque, brakes, deformation = 1 / 240, 80., (100., 300., 50., 0.), ((.001, -.0002),) * 4
    result = advance_drivetrain(velocity, angular, spins, engine, contact_frames, deformation,
        torque, 300., 12., brakes, config, config, dt, inverse_inertia=TENSOR,
        engine_inertia=.2, engine_axis=(0., 1., 0.), engine_drag=.12, efficiency=.88,
        shaft_omega=shaft, shaft_inertia=.04, shaft_axis=(0., 1., 0.),
        downstream_omega=old_speeds, downstream_inertias=INERTIAS, downstream_axes=AXES, suspension=system)
    step = result.suspension
    assert step.axial_force[0] == pytest.approx(0., abs=1e-9)
    assert 0. < step.compression[0] < initial[0]
    assert result.normal_residual < 1e-8
    loaded = tuple(replace(frame, load=force / normal[2]) for frame, force in zip(contact_frames, step.axial_force))
    audit(result, velocity, angular, spins, engine, loaded, deformation, torque, brakes, config, dt,
          old_axes, ((0.,) * 3,) * 4, shaft=shaft, downstream=tuple(zip(old_speeds, inertias, AXES)),
          normal=(system, step))


def test_normal_support_does_not_turn_nonroad_surface_into_tire_grip():
    contact_frames = tuple(replace(frame, supported=False, load=0.) for frame in frames(70., 0.))
    normal = (math.sin(math.radians(70.)), 0., math.cos(math.radians(70.)))
    assert normal[2] < .5
    gradients = tuple(tuple(n / normal[2] for n in normal)
                      + tuple(value / normal[2] for value in cross(frame.point, normal)) for frame in contact_frames)
    system = SuspensionInput((.06,) * 4, (.06,) * 4, gradients, (True,) * 4, (normal[2],) * 4, CONFIG)
    result = advance_drivetrain((.3, 12., -.1), (.12, -.08, .2), (36.,) * 4, 175.,
        contact_frames, ((0., 0.),) * 4, 0., 0., 0., (0.,) * 4, CONFIG, CONFIG, 1 / 240,
        inverse_inertia=TENSOR, engine_inertia=.2, engine_axis=(0., 1., 0.), engine_drag=.12,
        efficiency=.88, suspension=system)
    assert sum(result.suspension.axial_force) > 0.
    assert all(wheel.fx == 0. and wheel.fy == 0. and wheel.mode == "airborne" for wheel in result.wheels)
