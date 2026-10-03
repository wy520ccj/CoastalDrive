"""完整机械账独立展开；柔性/刚性、正反挡、空挡与转向指定功。"""

from dataclasses import replace

import pytest
from test_rotor_transport import CONFIG, INERTIA, TENSOR, frames

from rotor_dynamics import cross, dot, steering_torque
from tire_drivetrain import advance_drivetrain
from wheel_geometry import mechanical_axis

ENGINE_INERTIA = .2
ENGINE_AXIS = (0., 1., 0.)


def solve(velocity, angular, spins, engine, contact_frames, deformation, torque, capacity, ratio,
          brakes, config, dt, steering=((0., 0., 0.),) * 4, drag=.12, efficiency=.88,
          inverse_inertia=TENSOR, engine_axis=ENGINE_AXIS):
    return advance_drivetrain(velocity, angular, spins, engine, contact_frames, deformation,
        torque, capacity, ratio, brakes, config, replace(config, lateral_stiffness=config.rear_lateral_stiffness), dt,
        inverse_inertia=inverse_inertia, engine_inertia=ENGINE_INERTIA, engine_axis=engine_axis,
        engine_drag=drag, efficiency=efficiency, steering_torques=steering)


def audit(result, velocity, angular, spins, engine, contact_frames, deformation, torque, brakes, config, dt,
          old_axes, steering, inertia=tuple(tuple(INERTIA[a] if a == b else 0. for b in range(3)) for a in range(3)),
          engine_axis=ENGINE_AXIS, drag=.12):
    wheels, end_angular, end_velocity = result.wheels, result.angular, result.velocity
    force, body_torque, external = [0.] * 3, list(result.engine_body_torque), [0.] * 3
    for i, (frame, wheel) in enumerate(zip(contact_frames, wheels)):
        drive = result.drive_torque / 2 if i >= 2 else 0.
        f = tuple(frame.tangent[a] * wheel.fx + frame.axle[a] * wheel.fy for a in range(3))
        moment = cross(frame.point, f)
        for a in range(3):
            force[a] += f[a]
            body_torque[a] += moment[a] + frame.spin_axis[a] * (
                drive - wheel.brake_torque - frame.rolling_radius * wheel.fx) + wheel.gyro_torque[a] + steering[i][a]
            external[a] += dt * moment[a]
        assert config.wheel_inertia * (wheel.omega - spins[i]) == pytest.approx(
            dt * (drive - wheel.brake_torque - frame.rolling_radius * wheel.fx), abs=1e-11)
        assert wheel.relative_omega == pytest.approx(wheel.omega + dot(end_angular, frame.spin_axis), abs=1e-12)
        assert wheel.residual < .001
        assert abs(wheel.brake_torque) <= brakes[i] + 1e-10
        assert wheel.brake_torque * wheel.relative_omega >= -1e-7
    for a in range(3):
        assert config.mass * (end_velocity[a] - velocity[a]) == pytest.approx(dt * force[a], abs=1e-11)
        assert dot(inertia[a], tuple(end_angular[b] - angular[b] for b in range(3))) == pytest.approx(
            dt * body_torque[a], abs=2e-11)
    relative_engine = result.engine_omega - dot(end_angular, engine_axis)
    assert relative_engine == pytest.approx(result.engine_relative_omega, abs=1e-12)
    assert ENGINE_INERTIA * (result.engine_omega - engine) == pytest.approx(
        dt * (torque - drag * relative_engine - result.clutch_torque), abs=1e-11)
    kinetic = (.5 * config.mass * (dot(end_velocity, end_velocity) - dot(velocity, velocity))
               + .5 * (sum(end_angular[a] * dot(inertia[a], end_angular) for a in range(3))
                        - sum(angular[a] * dot(inertia[a], angular) for a in range(3)))
               + .5 * ENGINE_INERTIA * (result.engine_omega**2 - engine**2)
               + .5 * config.wheel_inertia * sum(wheel.omega**2 - spins[i]**2 for i, wheel in enumerate(wheels)))
    delta_angular = tuple(end_angular[a] - angular[a] for a in range(3))
    numerical = (.5 * config.mass * sum((end_velocity[a] - velocity[a])**2 for a in range(3))
                 + .5 * sum(delta_angular[a] * dot(inertia[a], delta_angular) for a in range(3))
                 + .5 * ENGINE_INERTIA * (result.engine_omega - engine)**2
                 + .5 * config.wheel_inertia * sum((wheel.omega - spins[i])**2 for i, wheel in enumerate(wheels)))
    if config.tire_compliance:
        elastic = sum(wheel.elastic_energy for wheel in wheels) - .5 * config.tire_contact_stiffness * sum(
            value**2 for previous in deformation for value in previous)
        contact_loss = sum(w.material_dissipation + w.road_dissipation + w.elastic_numerical_dissipation for w in wheels)
    else:
        elastic = 0.
        contact_loss = dt * sum(w.fx * (f.rolling_radius * w.omega - w.vx) - w.fy * w.vy for f, w in zip(contact_frames, wheels))
    brake_heat = dt * sum(w.brake_torque * w.relative_omega for w in wheels)
    steering_work = dt * sum(dot(end_angular, value) for value in steering)
    energy_error = (kinetic + numerical + elastic + contact_loss + brake_heat + result.engine_drag_heat
                    + result.clutch_heat + result.gear_heat - result.engine_work - steering_work)
    assert energy_error == pytest.approx(0., abs=3e-9)
    assert result.clutch_heat >= -1e-9 and result.gear_heat >= -1e-9
    old_spin = tuple(ENGINE_INERTIA * engine * engine_axis[a] - config.wheel_inertia * sum(
        spins[i] * old_axes[i][a] for i in range(4)) for a in range(3))
    new_spin = tuple(ENGINE_INERTIA * result.engine_omega * engine_axis[a] - config.wheel_inertia * sum(
        w.omega * contact_frames[i].spin_axis[a] for i, w in enumerate(wheels)) for a in range(3))
    for a in range(3):
        balance = dot(inertia[a], delta_angular) + new_spin[a] - old_spin[a] + dt * cross(end_angular, new_spin)[a]
        assert balance == pytest.approx(external[a], abs=1e-10)
    return energy_error


@pytest.mark.parametrize("speed,spins,engine,torque,capacity,ratio,brakes,loads", [
    (20., (61.,) * 4, 760., 150., 300., 12., (0.,) * 4, (2943.,) * 4),
    (20., (60.,) * 4, 500., 0., 300., 12., (0.,) * 4, (2943.,) * 4),
    (-12., (-36.,) * 4, 500., 120., 300., -12., (500.,) * 4, (2943.,) * 4),
    (0., (0.,) * 4, 100., 0., 300., 0., (1200.,) * 4, (2943.,) * 4),
    (0., (60.,) * 4, 250., 120., 300., 12., (0.,) * 4, (0.,) * 4),
    (20., (60., 62., 58., 75.), 800., 150., 0., 12., (0.,) * 4, (0., 300., 5500., 5886.)),
])
@pytest.mark.parametrize("bank", (-20., 0., 20.))
@pytest.mark.parametrize("dt", (1 / 240, 1 / 960))
@pytest.mark.parametrize("compliance", (True, False))
@pytest.mark.parametrize("steer_change", (False, True))
def test_shared_energy_momentum_steering_and_braking(speed, spins, engine, torque, capacity, ratio,
                                                   brakes, loads, bank, dt, compliance, steer_change):
    config = replace(CONFIG, tire_compliance=compliance)
    contact_frames = frames(bank, 25., loads)
    velocity, angular = (.3, speed, 0.), (.03, -.02, .2)
    deformation = (((.005, -.003), (-.006, .004), (.007, .002), (-.004, -.006))
                   if compliance else ((0., 0.),) * 4)
    old_axes = tuple(mechanical_axis((1., 0., 0.), (0., 1., 0.), frame.steering - (1. if steer_change and i < 2 else 0.))
                     for i, frame in enumerate(contact_frames))
    steering = tuple(steering_torque(old_axes[i], frame.spin_axis, spins[i], config.wheel_inertia, dt)
                     for i, frame in enumerate(contact_frames))
    result = solve(velocity, angular, spins, engine, contact_frames, deformation, torque, capacity,
                   ratio, brakes, config, dt, steering)
    audit(result, velocity, angular, spins, engine, contact_frames, deformation, torque, brakes,
          config, dt, old_axes, steering)
    if ratio == 0 or capacity == 0:
        assert result.clutch_torque == 0. and result.drive_torque == 0. and result.gear_loss_torque == 0.


@pytest.mark.parametrize("compliance", (True, False))
def test_neutral_free_engine_does_not_lock_to_a_stationary_input_shaft(compliance):
    config = replace(CONFIG, tire_compliance=compliance)
    contact_frames = frames(0., 0., (0.,) * 4)
    result = solve((0.,) * 3, (0.,) * 3, (0.,) * 4, 100., contact_frames, ((0., 0.),) * 4,
                   0., 300., 0., (0.,) * 4, config, 1 / 240, drag=0.)
    assert result.engine_omega == 100.
    assert result.engine_relative_omega == 100.
    assert result.clutch_torque == result.clutch_heat == result.drive_torque == 0.
    assert tuple(w.omega for w in result.wheels) == (0.,) * 4
    assert result.engine_body_torque == (0.,) * 3


@pytest.mark.parametrize("compliance", (True, False))
def test_open_differential_outputs_equal_torque_without_forcing_equal_wheel_speed(compliance):
    config = replace(CONFIG, tire_compliance=compliance)
    contact_frames = frames(0., 0., (0.,) * 4)
    spins = (0., 0., 10., 40.)
    dt = 1 / 240
    result = solve((0.,) * 3, (0.,) * 3, spins, 400., contact_frames, ((0., 0.),) * 4,
                   150., 300., 12., (0.,) * 4, config, dt)
    assert result.wheels[3].omega - result.wheels[2].omega == pytest.approx(30., abs=1e-12)
    for i in (2, 3):
        assert config.wheel_inertia * (result.wheels[i].omega - spins[i]) / dt == pytest.approx(
            result.drive_torque / 2, abs=1e-10)
