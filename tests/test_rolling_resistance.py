"""独立滚阻矩、能量与道路外力矩；实际车身不重复施加水平阻力。"""

import math
from dataclasses import replace

import pytest
from panda3d.core import Vec3
from physics.reference_ab import _create_vehicle, _step
from test_rotor_transport import CONFIG, TENSOR, frames
from test_tire_drivetrain import audit

from driving_modes import REFERENCE_CAR
from tire_drivetrain import advance_drivetrain
from vehicle_state import VehicleCommand


@pytest.mark.parametrize("share", (0., .5, 1.))
@pytest.mark.parametrize("speed", (20., -.03))
def test_wheel_port_rolling_moment_and_full_mechanical_accounting(share,speed):
    config = replace(CONFIG, front_drive_share=share)
    contacts = frames(20.,17., (0.,300.,5500.,5886.))
    velocity, angular = (.3,speed,-.1), (.12,-.08,.2)
    spins, engine = (speed/.33,)*4, 500.
    deformation, brakes = ((.001,-.0002),)*4, (100.,300.,50.,0.)
    coefficients = (.013,.013,.076,.076)
    dt = 1/240
    result = advance_drivetrain(velocity,angular,spins,engine,contacts,deformation,
        80.,300.,12.,brakes,config,config,dt,inverse_inertia=TENSOR,
        engine_inertia=.2,engine_axis=(0.,1.,0.),engine_drag=.12,efficiency=.88,
        rolling_coefficients=coefficients)
    for wheel,frame,coefficient in zip(result.wheels,contacts,coefficients):
        cap = coefficient * frame.load * frame.rolling_radius
        expected = cap * wheel.omega * frame.rolling_radius / max(abs(wheel.omega*frame.rolling_radius),1.)
        assert wheel.rolling_torque == pytest.approx(expected,abs=1e-9)
        assert wheel.rolling_dissipation == pytest.approx(dt*expected*wheel.omega,abs=1e-9)
        assert wheel.rolling_dissipation >= 0.
        assert abs(wheel.rolling_torque) <= cap+1e-9
    assert result.wheels[0].rolling_torque == result.wheels[0].rolling_dissipation == 0.
    audit(result,velocity,angular,spins,engine,contacts,deformation,80.,brakes,config,dt,
          tuple(f.spin_axis for f in contacts),((0.,0.,0.),)*4)


def test_actual_shared_normal_load_feeds_rolling_torque_without_duplicate_body_force():
    config = replace(REFERENCE_CAR, drag_coefficient=0.)
    world,car = _create_vehicle(config)
    try:
        for _ in range(240):
            _step(world,car,VehicleCommand(gear=0))
        car._chassis.setLinearVelocity(Vec3(0.,12.,0.))
        car.tires.initialize_rolling(12.)
        _step(world,car,VehicleCommand(gear=0))
        snapshot = car.snapshot()
        for wheel,contact in zip(snapshot.wheel_dynamics,snapshot.wheel_contacts):
            assert wheel.normal_load == contact.normal_load
            assert wheel.rolling_torque == pytest.approx(config.rolling_coefficient*contact.normal_load*wheel.force_rolling_radius,abs=1e-7)
            assert wheel.rolling_dissipation > 0.
            assert wheel.rolling_angular_impulse != 0.
            assert wheel.brake_torque == 0.
        assert snapshot.dynamics.rolling_force == pytest.approx(sum(
            abs(w.rolling_torque)/w.force_rolling_radius for w in snapshot.wheel_dynamics),abs=1e-7)
        # 世界尚未推进时，只准备中性命令；真实轮端冲量独立于外加中央力。
        car.apply_command(VehicleCommand(gear=0))
        assert car._chassis.getTotalForce().length() == 0.
        car.reset((0.,0.,20.),speed=12.)
        _step(world,car,VehicleCommand(gear=0))
        assert all(w.rolling_torque == w.rolling_dissipation == 0. for w in car.snapshot().wheel_dynamics)
        assert all(math.isfinite(w.omega) for w in car.snapshot().wheel_dynamics)
    finally:
        car.close()
