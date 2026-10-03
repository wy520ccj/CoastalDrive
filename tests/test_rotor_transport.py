"""真实机械轴的虚功、共同末状态能量及角动量输运；不放宽既有残差门槛。"""

import math
from dataclasses import replace
from itertools import pairwise

import pytest

from rotor_dynamics import cross, dot, solve_transport, steering_torque
from tire_coupling import ContactFrame, advance_coupled
from vehicle_config import CAR
from wheel_dynamics import Mobility
from wheel_geometry import contact_geometry, mechanical_axis

CONFIG = replace(CAR, wheel_rotor_transport=True)
INERTIA = (1900., 510., 2200.)
TENSOR = tuple(tuple(1 / INERTIA[a] if a == b else 0. for b in range(3)) for a in range(3))


def frames(bank, steering, loads=(2943.,) * 4):
    normal = (math.sin(math.radians(bank)), 0., math.cos(math.radians(bank)))
    result = []
    for i, (x, y) in enumerate(((-.84, 1.1), (.84, 1.1), (-.84, -1.1), (.84, -1.1))):
        axis = mechanical_axis((1., 0., 0.), (0., 1., 0.), steering if i < 2 else 0.)
        point = (x, y, -.42)
        axis, elastic, radius, moment_x = contact_geometry(axis, normal, point, CAR.wheel_radius)
        tangent, lateral, normal = elastic
        hub = tuple(point[a] + CAR.wheel_radius * normal[a] for a in range(3))
        moment_y = cross(point, lateral)
        rx, ry, rt = tuple(tuple(dot(row, v) for row in TENSOR) for v in (moment_x, moment_y, axis))
        mobility = Mobility(1 / CAR.mass + dot(moment_x, rx), dot(moment_x, ry), dot(moment_x, rt),
                            1 / CAR.mass + dot(moment_y, ry), dot(moment_y, rt), dot(axis, rt))
        result.append(ContactFrame(steering if i < 2 else 0., loads[i] > 0, loads[i], .45,
                                   tangent, lateral, point, hub, mobility, elastic, rx, ry, rt,
                                   axis, radius, moment_x))
    return result


@pytest.mark.parametrize("bank", [-20., 0., 20.])
@pytest.mark.parametrize("steering", [-30., 0., 30.])
@pytest.mark.parametrize("omega", [-60., 0., 60.])
def test_contact_virtual_power_uses_real_axis_and_raycast_point(bank, steering, omega):
    velocity, angular, drive, brake, fx, fy = (.3, 20., .4), (.12, -.08, .2), 200., -30., 1234., -432.
    frame = frames(bank, steering)[0]
    axis, radius = frame.spin_axis, frame.rolling_radius
    force = tuple(frame.tangent[a] * fx + frame.axle[a] * fy for a in range(3))
    torque = tuple(cross(frame.point, force)[a] + (drive - brake - radius * fx) * axis[a] for a in range(3))
    # 独立从表面点速度展开，不使用生产的广义纵速/力矩组合。
    hub_velocity = tuple(velocity[a] + cross(angular, frame.hub)[a] for a in range(3))
    offset = tuple(frame.point[a] - frame.hub[a] for a in range(3))
    # omega为绝对轴向滚动分量，表面点相对壳体旋转还须计入Ω·e。
    spin_velocity = cross(tuple(-(omega + dot(angular, axis)) * value for value in axis), offset)
    surface_velocity = tuple(hub_velocity[a] + cross(angular, offset)[a] + spin_velocity[a] for a in range(3))
    left = dot(velocity, force) + dot(angular, torque) + omega * (drive - brake - radius * fx)
    right = dot(force, surface_velocity) + (drive - brake) * (omega + dot(angular, axis))
    assert left == pytest.approx(right, abs=3e-11)
    assert radius == pytest.approx(CAR.wheel_radius * math.sqrt(1 - dot(axis, frame.elastic_frame[2])**2), abs=1e-15)
    if bank != 0:
        assert math.dist(axis, frame.axle) > .1


@pytest.mark.parametrize("bank,steering", [(-20., -30.), (0., 0.), (20., 30.)])
@pytest.mark.parametrize("speed,spins,drives,brakes,loads", [
    (20., (61.,) * 4, (0., 0., 150., 150.), (0.,) * 4, (2943.,) * 4),
    (-12., (-36.,) * 4, (0., 0., -100., -100.), (500.,) * 4, (2943.,) * 4),
    (0., (0.,) * 4, (0.,) * 4, (1200.,) * 4, (2943.,) * 4),
    (20., (60., 62., 58., 75.), (0., 0., 150., 150.), (0.,) * 4, (0., 300., 5500., 5886.)),
    (0., (60.,) * 4, (0.,) * 4, (0.,) * 4, (0.,) * 4),
])
@pytest.mark.parametrize("h", [1 / 240, 1 / 960])
@pytest.mark.parametrize("steer_change", [False, True])
def test_joint_energy_transport_and_dry_brake_with_steering_work(
        bank, steering, speed, spins, drives, brakes, loads, h, steer_change):
    contact_frames = frames(bank, steering, loads)
    velocity, angular = (.3, speed, 0.), (.03, -.02, .2)
    old_axes = tuple(mechanical_axis((1., 0., 0.), (0., 1., 0.), frame.steering - (1. if steer_change and i < 2 else 0.))
                     for i, frame in enumerate(contact_frames))
    torques = tuple(steering_torque(old_axes[i], frame.spin_axis, spins[i], CAR.wheel_inertia, h)
                    for i, frame in enumerate(contact_frames))
    deformation = ((.005, -.003), (-.006, .004), (.007, .002), (-.004, -.006))
    rear = replace(CONFIG, lateral_stiffness=CONFIG.rear_lateral_stiffness)
    steps = advance_coupled(velocity, angular, spins, contact_frames, deformation, drives, brakes,
                            CONFIG, rear, h, inverse_inertia=TENSOR, steering_torques=torques)
    force, torque, external = [0.] * 3, [0.] * 3, [0.] * 3
    for i, (frame, step) in enumerate(zip(contact_frames, steps)):
        f = tuple(frame.tangent[a] * step.fx + frame.axle[a] * step.fy for a in range(3))
        contact_moment = cross(frame.point, f)
        for a in range(3):
            force[a] += f[a]
            external[a] += h * contact_moment[a]
            torque[a] += (contact_moment[a] + frame.spin_axis[a] * (
                drives[i] - step.brake_torque - frame.rolling_radius * step.fx)
                + step.gyro_torque[a] + torques[i][a])
    v_end = tuple(velocity[a] + h * force[a] / CAR.mass for a in range(3))
    a_end = tuple(angular[a] + h * torque[a] / INERTIA[a] for a in range(3))
    kinetic = (.5 * CAR.mass * (dot(v_end, v_end) - dot(velocity, velocity))
               + .5 * sum(INERTIA[a] * (a_end[a]**2 - angular[a]**2) for a in range(3))
               + .5 * CAR.wheel_inertia * sum(s.omega**2 - spins[i]**2 for i, s in enumerate(steps)))
    elastic = sum(s.elastic_energy for s in steps) - .5 * CAR.tire_contact_stiffness * sum(
        value**2 for strain in deformation for value in strain)
    numerical = (.5 * CAR.mass * sum((v_end[a] - velocity[a])**2 for a in range(3))
                 + .5 * sum(INERTIA[a] * (a_end[a] - angular[a])**2 for a in range(3))
                 + .5 * CAR.wheel_inertia * sum((s.omega - spins[i])**2 for i, s in enumerate(steps)))
    actuator = h * sum(drives[i] * s.relative_omega + dot(torques[i], a_end) for i, s in enumerate(steps))
    brake_loss = h * sum(s.brake_torque * s.relative_omega for s in steps)
    contact_loss = sum(s.material_dissipation + s.road_dissipation + s.elastic_numerical_dissipation for s in steps)
    assert kinetic + elastic + numerical + brake_loss + contact_loss - actuator == pytest.approx(0., abs=3e-9)
    old_spin = tuple(-CAR.wheel_inertia * sum(spins[i] * old_axes[i][a] for i in range(4)) for a in range(3))
    new_spin = tuple(-CAR.wheel_inertia * sum(s.omega * contact_frames[i].spin_axis[a]
                                            for i, s in enumerate(steps)) for a in range(3))
    for a in range(3):
        balance = INERTIA[a] * (a_end[a] - angular[a]) + new_spin[a] - old_spin[a] + h * cross(a_end, new_spin)[a]
        assert balance == pytest.approx(external[a], abs=2e-11)
    for i, (frame, step) in enumerate(zip(contact_frames, steps)):
        assert abs(dot(step.gyro_torque, a_end)) < 1e-10
        assert step.body_omega == pytest.approx(dot(a_end, frame.spin_axis), abs=1e-12)
        assert step.vx == pytest.approx(dot(v_end, frame.tangent) + dot(a_end, frame.moment_x), abs=1e-12)
        assert step.residual < .001
        assert abs(step.brake_torque) <= brakes[i]
        assert step.brake_torque * step.relative_omega >= -1e-7


def test_world_inverse_tensor_transport_is_rotation_equivariant():
    rotation = ((.8, -.6, 0.), (.6, .8, 0.), (0., 0., 1.))
    angular, spin, h = (.1, -.2, .3), (-400., 30., -50.), 1 / 240
    rotated_tensor = tuple(tuple(sum(rotation[a][i] * TENSOR[i][i] * rotation[b][i] for i in range(3))
                                 for b in range(3)) for a in range(3))
    rotated = lambda vector: tuple(dot(row, vector) for row in rotation)
    reference = solve_transport(angular, TENSOR, spin, h)
    result = solve_transport(rotated(angular), rotated_tensor, rotated(spin), h)
    assert result == pytest.approx(rotated(reference), abs=1e-15)


def test_native_free_world_transport_refines_and_preserves_zero_spin_control():
    from physics.rotor_probe import run_free_trial

    zero_on, _rows = run_free_trial(120, 0., True)
    zero_off, _rows = run_free_trial(120, 0., False)
    assert zero_on["energy_delta_j"] == zero_off["energy_delta_j"]
    assert zero_on["final_momentum_error_nms"] == zero_off["final_momentum_error_nms"]
    old, _rows = run_free_trial(120, 60., False)
    errors = []
    for rate in (120, 240, 480, 960):
        result, rows = run_free_trial(rate, 60., True)
        errors.append(result["final_momentum_error_nms"])
        assert result["energy_delta_j"] < 0
        assert len(rows) == rate + 1
        assert result["peak_force_residual_n"] < .001
    assert errors[0] < old["final_momentum_error_nms"] / 100
    assert all(.4 < refined / coarse < .6 for coarse, refined in pairwise(errors))


@pytest.mark.parametrize("compliance", [False, True])
def test_real_supported_rotor_has_independent_compliance_switch_and_reset(compliance):
    from physics.reference_ab import _create_vehicle, _step

    from vehicle_state import VehicleCommand

    config = replace(CONFIG, tire_compliance=compliance)
    world, car = _create_vehicle(config)
    try:
        for _ in range(240):
            _step(world, car, VehicleCommand())
        car.tires.initialize_rolling(10.)
        from panda3d.core import Vec3
        car._chassis.setLinearVelocity(Vec3(0, 10, 0))
        for _ in range(60):
            _step(world, car, VehicleCommand(steering=2., throttle=.2, direction=1))
        wheels = car.snapshot().wheel_dynamics
        assert all(w.sample_support for w in wheels)
        assert all(w.rolling_radius > .3 and w.force_residual < .001 for w in wheels)
        assert any(math.sqrt(dot(w.gyro_angular_impulse, w.gyro_angular_impulse)) > 1e-8 for w in wheels)
        assert any(abs(w.steering_work) > 1e-12 for w in wheels[:2])
        if compliance:
            assert any(w.elastic_energy > 0 for w in wheels)
        else:
            assert all(w.elastic_energy == 0 for w in wheels)
        omega = car.tires.omega.copy()
        car.shift(1000)
        assert car.tires.omega == omega
        car.reset((0, 0, 20))
        assert car.tires.omega == [0.] * 4
        assert all(w.steering_work == 0 and w.gyro_angular_impulse == (0., 0., 0.)
                   for w in car.snapshot().wheel_dynamics)
    finally:
        car.close()


@pytest.mark.parametrize("direction", [-1, 1])
def test_feedback_uses_effective_contact_radius_instead_of_nominal_hardware(direction):
    from vehicle_brakes import BrakeConfig, Brakes
    from vehicle_state import WheelDynamicsState
    from vehicle_traction import TractionConfig, TractionControl

    wheel = WheelDynamicsState(omega=direction * 20 / .30, longitudinal_speed=direction * 20,
                               rolling_radius=.30, sample_support=True, sample_tick=12)
    brakes = Brakes(BrakeConfig())
    brakes.advance((1.,) * 4, (wheel,) * 4, .33, 1 / 120)
    assert all(state.braking_slip == pytest.approx(0., abs=1e-15) for state in brakes.states)
    traction = TractionControl(TractionConfig())
    state = traction.advance(1., direction, False, (wheel,) * 4, .33, 1 / 120)
    assert state.wheel_slips == pytest.approx((0.,) * 4, abs=1e-15)
    assert not state.active
