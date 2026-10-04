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
          inverse_inertia=TENSOR, engine_axis=ENGINE_AXIS, engine_inertia=ENGINE_INERTIA):
    return advance_drivetrain(velocity, angular, spins, engine, contact_frames, deformation,
        torque, capacity, ratio, brakes, config, replace(config, lateral_stiffness=config.rear_lateral_stiffness), dt,
        inverse_inertia=inverse_inertia, engine_inertia=engine_inertia, engine_axis=engine_axis,
        engine_drag=drag, efficiency=efficiency, steering_torques=steering)


def audit(result, velocity, angular, spins, engine, contact_frames, deformation, torque, brakes, config, dt,
          old_axes, steering, inertia=tuple(tuple(INERTIA[a] if a == b else 0. for b in range(3)) for a in range(3)),
          engine_axis=ENGINE_AXIS, drag=.12, engine_inertia=ENGINE_INERTIA,
          shaft=None, shaft_inertia=.04, shaft_axis=(0., 1., 0.)):
    wheels, end_angular, end_velocity = result.wheels, result.angular, result.velocity
    relative_wheels = tuple(w.omega + dot(end_angular, f.spin_axis) for w, f in zip(wheels, contact_frames))
    slips = (relative_wheels[0] - relative_wheels[1], relative_wheels[2] - relative_wheels[3],
             (relative_wheels[0] + relative_wheels[1] - relative_wheels[2] - relative_wheels[3]) / 2)
    torques = tuple(max(-limit, min(limit, c * s)) for c, limit, s in
                    zip(config.differential_damping, config.differential_capacity, slips))
    transfers = (-torques[0] - torques[2] / 2, torques[0] - torques[2] / 2,
                 -torques[1] + torques[2] / 2, torques[1] + torques[2] / 2)
    assert result.differential_torques == pytest.approx(torques, abs=1e-11)
    assert result.differential_slips == pytest.approx(slips, abs=1e-12)
    force, body_torque, external = [0.] * 3, list(result.engine_body_torque), [0.] * 3
    if shaft is not None:
        for a in range(3):
            body_torque[a] += result.shaft_body_torque[a]
        assert shaft_inertia * (result.shaft_omega - shaft) == pytest.approx(
            dt * (result.clutch_torque - result.gear_reaction), abs=1e-11)
        assert result.shaft_relative_omega == pytest.approx(
            result.shaft_omega - dot(end_angular, shaft_axis), abs=1e-12)
        assert result.clutch_slip == pytest.approx(result.engine_relative_omega - result.shaft_relative_omega, abs=1e-11)
    for i, (frame, wheel) in enumerate(zip(contact_frames, wheels)):
        drive = result.drive_torque * (config.front_drive_share if i < 2 else 1 - config.front_drive_share) / 2 + transfers[i]
        assert result.wheel_drive_torques[i] == pytest.approx(drive, abs=1e-11)
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
    assert engine_inertia * (result.engine_omega - engine) == pytest.approx(
        dt * (torque - drag * relative_engine - result.clutch_torque), abs=1e-11)
    kinetic = (.5 * config.mass * (dot(end_velocity, end_velocity) - dot(velocity, velocity))
               + .5 * (sum(end_angular[a] * dot(inertia[a], end_angular) for a in range(3))
                        - sum(angular[a] * dot(inertia[a], angular) for a in range(3)))
               + .5 * engine_inertia * (result.engine_omega**2 - engine**2)
               + .5 * config.wheel_inertia * sum(wheel.omega**2 - spins[i]**2 for i, wheel in enumerate(wheels)))
    if shaft is not None:
        kinetic += .5 * shaft_inertia * (result.shaft_omega**2 - shaft**2)
    delta_angular = tuple(end_angular[a] - angular[a] for a in range(3))
    numerical = (.5 * config.mass * sum((end_velocity[a] - velocity[a])**2 for a in range(3))
                 + .5 * sum(delta_angular[a] * dot(inertia[a], delta_angular) for a in range(3))
                 + .5 * engine_inertia * (result.engine_omega - engine)**2
                 + .5 * config.wheel_inertia * sum((wheel.omega - spins[i])**2 for i, wheel in enumerate(wheels)))
    if shaft is not None:
        numerical += .5 * shaft_inertia * (result.shaft_omega - shaft)**2
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
                    + result.clutch_heat + result.gear_heat + result.synchronizer_heat + dt * sum(t * s for t, s in zip(torques, slips))
                    - result.engine_work - steering_work)
    assert energy_error == pytest.approx(0., abs=3e-9)
    assert result.clutch_heat >= -1e-9 and result.gear_heat >= -1e-9
    old_spin = tuple(engine_inertia * engine * engine_axis[a] - config.wheel_inertia * sum(
        spins[i] * old_axes[i][a] for i in range(4)) for a in range(3))
    new_spin = tuple(engine_inertia * result.engine_omega * engine_axis[a] - config.wheel_inertia * sum(
        w.omega * contact_frames[i].spin_axis[a] for i, w in enumerate(wheels)) for a in range(3))
    if shaft is not None:
        old_spin = tuple(old_spin[a] + shaft_inertia * shaft * shaft_axis[a] for a in range(3))
        new_spin = tuple(new_spin[a] + shaft_inertia * result.shaft_omega * shaft_axis[a] for a in range(3))
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
@pytest.mark.parametrize("engine_inertia", (.02, .2))
def test_shared_energy_momentum_steering_and_braking(speed, spins, engine, torque, capacity, ratio,
                                                   brakes, loads, bank, dt, compliance, steer_change, engine_inertia):
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
                   ratio, brakes, config, dt, steering, engine_inertia=engine_inertia)
    audit(result, velocity, angular, spins, engine, contact_frames, deformation, torque, brakes,
          config, dt, old_axes, steering, engine_inertia=engine_inertia)
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


@pytest.mark.parametrize("omitted", ("reaction", "gyro"))
def test_independent_body_balance_detects_missing_engine_reaction_or_gyro(omitted):
    contact_frames = frames(20., 25., (0.,) * 4)
    velocity, angular, spins, engine = (.3, 20., 0.), (.03, -.02, .2), (60.,) * 4, 500.
    deformation, steering, brakes = ((0., 0.),) * 4, ((0., 0., 0.),) * 4, (0.,) * 4
    dt, torque = 1 / 240, 150.
    result = solve(velocity, angular, spins, engine, contact_frames, deformation, torque,
                   300., 12., brakes, CONFIG, dt)
    arguments = (velocity, angular, spins, engine, contact_frames, deformation, torque, brakes,
                 CONFIG, dt, tuple(f.spin_axis for f in contact_frames), steering)
    audit(result, *arguments)
    gyro = cross(tuple(ENGINE_INERTIA * result.engine_omega * a for a in ENGINE_AXIS), result.angular)
    incomplete = (gyro if omitted == "reaction" else
                  tuple(result.engine_body_torque[a] - gyro[a] for a in range(3)))
    # 只删掉实际提交的反力项；独立惯量/动量账必须检出缺项。
    with pytest.raises(AssertionError):
        audit(replace(result, engine_body_torque=incomplete), *arguments)


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


@pytest.mark.parametrize("compliance", (True, False))
@pytest.mark.parametrize("ratio", (-12., 0., 12.))
def test_force_warm_initial_preserves_physical_solution(compliance, ratio):
    config = replace(CONFIG, tire_compliance=compliance)
    contact_frames = frames(20., 25.)
    velocity, angular, spins, engine = (.3, 20., 0.), (.03, -.02, .2), (60., 62., 58., 75.), 800.
    deformation = ((.004, -.002),) * 4 if compliance else ((0., 0.),) * 4
    arguments = (velocity, angular, spins, engine, contact_frames, deformation, 150., 300., ratio,
                 (0.,) * 4, config, replace(config, lateral_stiffness=config.rear_lateral_stiffness), 1 / 240)
    keywords = {"inverse_inertia": TENSOR, "engine_inertia": ENGINE_INERTIA, "engine_axis": ENGINE_AXIS,
                "engine_drag": .12, "efficiency": .88}
    cold = advance_drivetrain(*arguments, **keywords)
    warm = advance_drivetrain(*arguments, **keywords, force_initial=tuple((w.fx, w.fy, w.brake_torque) for w in cold.wheels))
    assert warm.engine_omega == pytest.approx(cold.engine_omega, abs=1e-6)
    assert warm.velocity == pytest.approx(cold.velocity, abs=1e-8)
    assert warm.angular == pytest.approx(cold.angular, abs=1e-8)
    assert tuple(w.omega for w in warm.wheels) == pytest.approx(tuple(w.omega for w in cold.wheels), abs=1e-6)
    for a, b in zip(warm.wheels, cold.wheels):
        assert a.fx == pytest.approx(b.fx, abs=.001)
        assert a.fy == pytest.approx(b.fy, abs=.001)
    audit(warm, velocity, angular, spins, engine, contact_frames, deformation, 150., (0.,) * 4,
          config, 1 / 240, tuple(f.spin_axis for f in contact_frames), ((0., 0., 0.),) * 4)


@pytest.mark.parametrize("compliance", (True, False))
def test_full_world_tensor_and_engine_axis_rotation_covariance(compliance):
    rotation = ((.8, -.6, 0.), (.6, .8, 0.), (0., 0., 1.))
    rotate = lambda vector: tuple(dot(row, vector) for row in rotation)
    config = replace(CONFIG, tire_compliance=compliance)
    contact_frames = frames(-20., 25.)
    velocity, angular, spins, engine = (.3, 20., 0.), (.03, -.02, .2), (61.,) * 4, 760.
    deformation = ((.004, -.002),) * 4 if compliance else ((0., 0.),) * 4
    parameters = (deformation, 150., 300., 12., (0.,) * 4, config, 1 / 240)
    original = solve(velocity, angular, spins, engine, contact_frames, *parameters)
    rotated_frames = tuple(replace(f, tangent=rotate(f.tangent), axle=rotate(f.axle), point=rotate(f.point), hub=rotate(f.hub),
        response_x=rotate(f.response_x), response_y=rotate(f.response_y), response_t=rotate(f.response_t),
        spin_axis=rotate(f.spin_axis), moment_x=rotate(f.moment_x), elastic_frame=tuple(rotate(v) for v in f.elastic_frame))
        for f in contact_frames)
    inverse = tuple(tuple(sum(rotation[a][j] * TENSOR[j][j] * rotation[b][j] for j in range(3)) for b in range(3)) for a in range(3))
    inertia = tuple(tuple(sum(rotation[a][j] * INERTIA[j] * rotation[b][j] for j in range(3)) for b in range(3)) for a in range(3))
    rotated = solve(rotate(velocity), rotate(angular), spins, engine, rotated_frames, *parameters,
                    inverse_inertia=inverse, engine_axis=rotate(ENGINE_AXIS))
    assert rotated.engine_omega == pytest.approx(original.engine_omega, abs=1e-11)
    assert rotated.angular == pytest.approx(rotate(original.angular), abs=1e-12)
    assert rotated.velocity == pytest.approx(rotate(original.velocity), abs=1e-12)
    assert tuple(w.omega for w in rotated.wheels) == pytest.approx(tuple(w.omega for w in original.wheels), abs=1e-11)
    audit(rotated, rotate(velocity), rotate(angular), spins, engine, rotated_frames, deformation, 150., (0.,) * 4,
          config, 1 / 240, tuple(f.spin_axis for f in rotated_frames), ((0., 0., 0.),) * 4,
          inertia=inertia, engine_axis=rotate(ENGINE_AXIS))
