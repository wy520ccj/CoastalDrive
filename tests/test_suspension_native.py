"""真实原生冲量、轮胎轮荷、防倾响应与生命周期；单一Bullet世界。"""

import math
from dataclasses import replace

import pytest
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import TransformState, Vec3
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from vehicle import Vehicle
from vehicle_state import FIXED_DT, VehicleCommand


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("mass", (1200., 1800.))
def test_actual_support_load_matches_mass_and_reaches_tire_force_phase(mode, mass):
    config = replace(mode.vehicle_config, mass=mass)
    world, car = _create_vehicle(config)
    try:
        for _ in range(300):
            _step(world, car, VehicleCommand(gear=0))
        state = car.snapshot()
        assert sum(c.normal_load for c in state.wheel_contacts) == pytest.approx(mass * 9.81, rel=.002)
        expected = mass * 9.81 / (4 * 48000.)
        assert sum(c.compression for c in state.wheel_contacts) / 4 == pytest.approx(expected, abs=.0001)
        assert state.suspension_state.force_tick == state.contact_tick == 300
        for i, (contact, tire) in enumerate(zip(state.wheel_contacts, state.wheel_dynamics)):
            assert tire.normal_load == contact.normal_load == state.suspension_state.normal_force[i]
            assert tire.force_contact_tick == state.suspension_state.force_tick
            assert abs(tire.force_residual) < .001
        assert all(w.getWheelsSuspensionForce() == 0 for w in car._vehicle.getWheels())
    finally:
        car.close()


def test_actual_impulse_is_sum_of_contact_normals_and_real_arms():
    world, car = _create_vehicle(DrivingMode.SIMULATION.vehicle_config)
    try:
        car._chassis.setTransform(TransformState.makePosHpr(Vec3(0, 0, .4), Vec3(0, 0, 3)))
        car._chassis.setAngularVelocity(Vec3(.15, -.1, .02))
        before_v = Vec3(car._chassis.getLinearVelocity())
        before_w = Vec3(car._chassis.getAngularVelocity())
        tensor = car._chassis.getInvInertiaTensorWorld()
        contacts = car.suspension.advance(world, car._chassis, car._vehicle.getWheels(),
                                         car.on_asphalt, 1, FIXED_DT, (0.,) * 3, (0.,) * 3)
        linear, angular = Vec3(0), Vec3(0)
        for c in contacts:
            if c.in_contact:
                impulse = Vec3(*c.contact_normal) * (c.normal_load * FIXED_DT)
                arm = Vec3(*c.contact_point) - car._chassis.getTransform().getPos()
                linear += impulse
                angular += arm.cross(impulse)
        assert tuple(car._chassis.getLinearVelocity() - before_v) == pytest.approx(tuple(linear / car.config.mass), abs=2e-7)
        assert tuple(car._chassis.getAngularVelocity() - before_w) == pytest.approx(tuple(tensor.xform(angular)), abs=2e-7)
        assert car.suspension.state.linear_impulse == pytest.approx(tuple(linear), abs=1e-5)
        assert car.suspension.state.angular_impulse == pytest.approx(tuple(angular), abs=1e-5)
        # 独立核对实际车身末速度的全部六维分量，不能只检查总冲量。
        for i, c in enumerate(contacts):
            if c.in_contact:
                normal = Vec3(*c.contact_normal)
                arm = Vec3(*c.contact_point) - car._chassis.getTransform().getPos()
                velocity = car._chassis.getLinearVelocity() + car._chassis.getAngularVelocity().cross(arm)
                extension_rate = velocity.dot(normal) / car.suspension.state.contact_dot[i]
                assert car.suspension.state.step.compression_rate[i] == pytest.approx(-extension_rate, abs=2e-7)
    finally:
        car.close()


def test_bar_changes_actual_load_transfer_and_roll_reaction():
    results = []
    for bars in ((0., 0.), (6000., 4000.)):
        config = replace(DrivingMode.SIMULATION.vehicle_config, suspension_antiroll_rates=bars)
        world, car = _create_vehicle(config)
        try:
            car._chassis.setTransform(TransformState.makePosHpr(Vec3(0, 0, .4), Vec3(0, 0, 3)))
            _step(world, car, VehicleCommand(gear=0))
            s = car.snapshot()
            results.append((abs(car._chassis.getAngularVelocity().y),
                            abs(s.wheel_contacts[0].normal_load - s.wheel_contacts[1].normal_load),
                            sum(s.suspension_state.step.bar_energy)))
        finally:
            car.close()
    assert results[1][0] > results[0][0]
    assert results[1][1] > results[0][1]
    assert results[0][2] == 0 and results[1][2] > 0


def test_single_side_free_travel_is_relaxed_instead_of_clearing_energy():
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("left-only")
    ground.addShape(BulletBoxShape(Vec3(.4, 4., .05)))
    ground.setTransform(TransformState.makePos(Vec3(-.84, 0, -.05)))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda x, y: True, (0, 0, .4), config=DrivingMode.SIMULATION.vehicle_config)
    try:
        _step(world, car, VehicleCommand(gear=0))
        state = car.snapshot()
        assert state.suspension_state.candidate_contact == (True, False, True, False)
        assert state.wheel_contacts[1].normal_load == state.wheel_contacts[3].normal_load == 0
        assert state.suspension_state.step.compression[1] > 0
        assert state.suspension_state.step.compression[3] > 0
        assert state.suspension_state.step.damping_dissipation > 0
        assert sum(state.suspension_state.step.bar_energy) > 0
    finally:
        car.close()


def test_reset_and_origin_shift_preserve_correct_suspension_ownership():
    world, car = _create_vehicle(DrivingMode.SIMULATION.vehicle_config)
    try:
        for _ in range(30):
            _step(world, car, VehicleCommand(gear=0))
        before = car.snapshot()
        car.shift(100.)
        shifted = car.snapshot()
        assert shifted.suspension_state == before.suspension_state
        for a, b in zip(before.wheel_contacts, shifted.wheel_contacts):
            assert b.contact_point[1] == pytest.approx(a.contact_point[1] - 100.)
            assert b.normal_load == a.normal_load
        car.reset((0, 0, 3))
        assert car.suspension.compression == (0.,) * 4
        assert car.snapshot().suspension_state.step is None
        _step(world, car, VehicleCommand(gear=0))
        assert all(c.normal_load == 0 for c in car.snapshot().wheel_contacts)
        assert all(math.isfinite(v) for v in car.snapshot().velocity)
    finally:
        car.close()
