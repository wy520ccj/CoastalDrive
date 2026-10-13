"""独立刷毛积分、实际共同末状态的虚功/能量及正反运动边界。"""

import math
from dataclasses import replace

import pytest
from test_rotor_transport import INERTIA, TENSOR, frames

from rotor_dynamics import cross, dot
from tire_aligning import aligning_frame, brush_trail
from tire_coupling import advance_coupled
from vehicle_config import CAR
from vehicle_state import WheelDynamicsState

CONFIG = replace(CAR, tire_aligning_enabled=True)


@pytest.mark.parametrize("trial", [0.01, 500., 1500., 3000., 15000.])
def test_trail_matches_independent_brush_pressure_integral(trial):
    a, load, count = .08, 3000., 100000
    dx = 2*a/count
    # 均布压力下局部摩擦限值D/(2a)，刷毛梯度由小滑移总力确定。
    traction = [min(trial/(2*a*a)*(i+.5)*dx, load/(2*a)) for i in range(count)]
    force = math.fsum(traction)*dx
    moment = math.fsum((a-(i+.5)*dx)*value for i, value in enumerate(traction))*dx
    expected = -moment/force
    result = brush_trail(a, trial/60000., 0., load, 60000., 50000., 20., .25)
    assert result == pytest.approx(expected, abs=2e-10)
    assert brush_trail(a, trial/60000., 0., load, 60000., 50000., -20., .25) == -result


def test_zero_load_and_low_speed_do_not_invent_parking_torque():
    assert brush_trail(.08, .01, .05, 0., 60000., 50000., 20., .25) == 0.
    assert brush_trail(.08, .01, .05, 3000., 60000., 50000., .1, .25) == 0.
    with pytest.raises(ValueError, match="半长"):
        replace(CAR, tire_contact_half_length=0.)


def test_old_snapshot_layout_recovers_original_values_without_new_mechanism():
    from dataclasses import fields

    from physics_packet_kernels import encode

    import snapshot_wire
    from lab_experiment import LabExperiment, LabOptions
    from lab_signals import PRE_ALIGN_SIGNAL_KEYS, sample_signals
    from vehicle_designs import REFERENCE_DESIGN
    from vehicle_state import VehicleCommand

    run = LabExperiment(LabOptions(duration=.1), config=replace(REFERENCE_DESIGN,tire_aligning_enabled=False))
    try:
        original = run.current
        binary = encode(snapshot_wire._legacy_layout, ((original,), {}))
        restored, _ = snapshot_wire.decode_snapshots(binary)
        expected = sample_signals(original, VehicleCommand(), original.time)
        actual = sample_signals(restored[0], VehicleCommand(), original.time)
        assert {k: actual[k] for k in PRE_ALIGN_SIGNAL_KEYS if k != "path_error"} == {
            k: expected[k] for k in PRE_ALIGN_SIGNAL_KEYS if k != "path_error"}
        for w in restored[0].player.wheel_dynamics:
            assert w.aligning_moment == 0. and w.contact_steering_work == 0.
            assert set(w.__dict__) == {f.name for f in fields(WheelDynamicsState)} - snapshot_wire._align_names
    finally:
        run.close()


@pytest.mark.parametrize("speed", [20., -20.])
@pytest.mark.parametrize("steer_rate", [-.6, 0., .6])
def test_shifted_force_velocity_and_prescribed_steering_energy_balance(speed, steer_rate):
    velocity, angular, h = (.3, speed, 0.), (.03, -.02, .2), 1/240
    prior = WheelDynamicsState(longitudinal_speed=speed, normal_load=2943., road_support=True,
                               force_patch_kappa=.004, force_patch_alpha=.018)
    original = frames(12., 8.)
    contacts = [aligning_frame(frame, prior, CONFIG, TENSOR, (0., 0., steer_rate if i < 2 else 0.))
                for i, frame in enumerate(original)]
    spins = (speed/.33,) * 4
    deformation = ((.005, -.003), (-.006, .004), (.007, .002), (-.004, -.006))
    steps = advance_coupled(velocity, angular, spins, contacts, deformation, (0.,)*4, (0.,)*4,
                            CONFIG, CONFIG, h, inverse_inertia=TENSOR)
    force = tuple(sum(f.tangent[a]*s.fx+f.axle[a]*s.fy for f,s in zip(contacts,steps)) for a in range(3))
    torque = tuple(sum(cross(f.point, tuple(f.tangent[b]*s.fx+f.axle[b]*s.fy for b in range(3)))[a]
                        - f.spin_axis[a]*f.rolling_radius*s.fx + s.gyro_torque[a]
                        for f,s in zip(contacts,steps)) for a in range(3))
    end_v = tuple(velocity[a]+h*force[a]/CONFIG.mass for a in range(3))
    end_a = tuple(angular[a]+h*torque[a]/INERTIA[a] for a in range(3))
    kinetic = .5*CONFIG.mass*(dot(end_v,end_v)-dot(velocity,velocity))
    kinetic += .5*sum(INERTIA[a]*(end_a[a]**2-angular[a]**2) for a in range(3))
    kinetic += .5*CONFIG.wheel_inertia*sum(s.omega**2-spins[i]**2 for i,s in enumerate(steps))
    numeric = .5*CONFIG.mass*sum((end_v[a]-velocity[a])**2 for a in range(3))
    numeric += .5*sum(INERTIA[a]*(end_a[a]-angular[a])**2 for a in range(3))
    numeric += .5*CONFIG.wheel_inertia*sum((s.omega-spins[i])**2 for i,s in enumerate(steps))
    elastic = sum(s.elastic_energy for s in steps)-.5*CONFIG.tire_contact_stiffness*sum(x*x for pair in deformation for x in pair)
    losses = sum(s.material_dissipation+s.road_dissipation+s.elastic_numerical_dissipation for s in steps)
    input_work = -h*sum(s.fy*f.steering_lateral_velocity for s,f in zip(steps,contacts))
    assert kinetic+numeric+elastic+losses-input_work == pytest.approx(0., abs=3e-9)
    for f, base, s in zip(contacts, original, steps):
        delta = tuple(cross(f.point,f.axle)[a]-cross(base.point,base.axle)[a] for a in range(3))
        assert delta == pytest.approx(tuple(f.pneumatic_trail*x for x in f.elastic_frame[2]), abs=1e-15)
        assert s.vy == pytest.approx(dot(end_v,f.axle)+dot(end_a,cross(f.point,f.axle))+f.steering_lateral_velocity, abs=1e-12)
        assert s.road_dissipation >= 0.


def test_actual_world_publishes_aligning_moment_and_exact_archive(tmp_path):
    from lab_experiment import LabExperiment, LabOptions
    from lab_records import LabRecord, export_record, load_record
    from vehicle_designs import REFERENCE_DESIGN

    run = LabExperiment(LabOptions(maneuver="step_steer", speed_kph=60, duration=.5, onset=.1, steering_deg=3.),
                        config=replace(REFERENCE_DESIGN, tire_aligning_enabled=True))
    try:
        while not run.done:
            run.step()
        assert any(abs(w.aligning_moment)>1. for state in run.snapshots for w in state.player.wheel_dynamics)
        assert any(abs(w.contact_steering_work)>1e-6 for state in run.snapshots for w in state.player.wheel_dynamics[:2])
        record = LabRecord.from_run(run)
        export_record(record, tmp_path/"trial")
        loaded = load_record(tmp_path/"trial")
        assert loaded.snapshots == record.snapshots
    finally:
        run.close()


def test_native_and_python_joint_solve_and_full_energy_with_contact_steering(monkeypatch):
    import numpy as np
    from test_tire_drivetrain import audit

    import tire_drivetrain
    from lab_experiment import LabExperiment, LabOptions
    from vehicle_designs import REFERENCE_DESIGN

    original, captured = tire_drivetrain.advance_drivetrain, []

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        if any(f.pneumatic_trail != 0. and f.steering_lateral_velocity != 0. for f in args[4]):
            captured.append((args, kwargs, result))
        return result

    monkeypatch.setattr(tire_drivetrain, "advance_drivetrain", capture)
    run = LabExperiment(LabOptions(maneuver="step_steer", speed_kph=60, duration=.2, onset=.05),
                        config=replace(REFERENCE_DESIGN, tire_aligning_enabled=True))
    try:
        while not run.done:
            run.step()
        args, kwargs, native = captured[-1]
        monkeypatch.setattr(tire_drivetrain, "native_contact_geometry", lambda system: None)
        reference = original(*args, **kwargs)
        assert native.velocity == pytest.approx(reference.velocity, abs=1e-12)
        assert native.angular == pytest.approx(reference.angular, abs=1e-12)
        for n, p in zip(native.wheels, reference.wheels):
            assert (n.fx,n.fy,n.omega,n.deformation_x,n.deformation_y) == pytest.approx(
                (p.fx,p.fy,p.omega,p.deformation_x,p.deformation_y), abs=1e-7)
        velocity, angular, spins, engine, contacts, deform, torque, _capacity, _ratio, brakes, config, _rear, dt = args
        old_axes = tuple(tuple(f.spin_axis[a] - dt*kwargs["steering_torques"][i][a]/(config.wheel_inertia*spins[i])
                               if spins[i] else f.spin_axis[a] for a in range(3)) for i,f in enumerate(contacts))
        downstream = tuple(zip(kwargs["downstream_omega"],
            (kwargs["downstream_inertias"][0], 0., kwargs["downstream_inertias"][2]), kwargs["downstream_axes"]))
        audit(native, velocity, angular, spins, engine, contacts, deform, torque, brakes, config, dt,
              old_axes, kwargs["steering_torques"], inertia=np.linalg.inv(kwargs["inverse_inertia"]),
              engine_axis=kwargs["engine_axis"], drag=kwargs["engine_drag"], engine_inertia=kwargs["engine_inertia"],
              shaft=kwargs["shaft_omega"], shaft_inertia=kwargs["shaft_inertia"], shaft_axis=kwargs["shaft_axis"],
              downstream=downstream, normal=(native.suspension_system,native.suspension))
    finally:
        run.close()
