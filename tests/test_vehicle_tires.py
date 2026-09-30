"""真实刚体与四轮独立转动的受力、能量及快照边界。"""

import math

import pytest
from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import Quat, Vec3

from simulation import Control, Simulation, interpolate
from tire_forces import tire_force
from vehicle import Vehicle
from vehicle_config import CAR
from vehicle_state import FIXED_DT, VehicleCommand


@pytest.fixture
def sim():
    simulation = Simulation(track="test", traffic_count=0)
    for _ in range(240):
        simulation.step(Control())
    yield simulation
    simulation.close()


def tire_step(car, *, drive=0, brake=0):
    car.tires.advance(car._chassis, car.snapshot().wheel_contacts, (0, 0),
                      drive, 0, brake, car.snapshot().contact_tick, FIXED_DT)


def kinetic_energy(car):
    body = car._chassis
    local_angular = body.getTransform().getQuat().conjugate().xform(body.getAngularVelocity())
    inertia = body.getInertia()
    return (
        .5 * CAR.mass * body.getLinearVelocity().lengthSquared()
        + .5 * sum(inertia[i] * local_angular[i] ** 2 for i in range(3))
        + .5 * CAR.wheel_inertia * sum(omega ** 2 for omega in car.tires.omega)
    )


def test_native_tangent_forces_disabled_with_suspension_and_collision(sim):
    car = sim.player
    car.apply_command(VehicleCommand(throttle=1, direction=1))
    for wheel in car._vehicle.getWheels():
        assert wheel.getFrictionSlip() == wheel.getEngineForce() == wheel.getBrake() == 0
    assert all(c.normal_load > 0 for c in car.snapshot().wheel_contacts)
    # 真正车身压到地面时碰撞仍有效，而不是仅证明悬架射线存在。
    car.reset((95, 0, -.1))
    sim.step(Control())
    assert sim._world.contactTest(car._chassis).getNumContacts() > 0


@pytest.mark.parametrize("drive", [-200, 200])
def test_airborne_drive_reaction_conserves_angular_momentum(sim, drive):
    car = sim.player
    car.reset((95, 0, 20))
    axis = car._chassis.getTransform().getQuat().getRight()
    tire_step(car, drive=drive)
    body_omega = car._chassis.getAngularVelocity().dot(axis)
    assert body_omega * drive > 0
    # 独立轮速以向前滚动为正，对应物理轮角动量朝车体右轴的负向。
    assert car.tires.omega[2] * drive > 0
    inertia = car._chassis.getInertia().x
    momentum = inertia * body_omega - CAR.wheel_inertia * sum(car.tires.omega)
    assert momentum == pytest.approx(0, abs=1e-5)


@pytest.mark.parametrize("velocity, angular, omega", [
    ((3, 10, 0), (.2, -.3, .4), (0, 0, 0, 0)),
    ((-2, -4, 0), (-.3, .5, -.2), (12, -15, 18, -20)),
    ((0, .02, 0), (0, 0, .1), (.1, .2, -.3, .4)),
])
def test_isolated_tire_impulses_do_not_add_energy(sim, velocity, angular, omega):
    car = sim.player
    car._chassis.setLinearVelocity(Vec3(*velocity))
    car._chassis.setAngularVelocity(Vec3(*angular))
    car.tires.omega = list(omega)
    before = kinetic_energy(car)
    tire_step(car)
    after = kinetic_energy(car)
    assert after <= before + 1e-5, (before, after)


@pytest.mark.parametrize("speed", [-.1, .1])
def test_low_speed_braking_does_not_reverse(sim, speed):
    car = sim.player
    car._chassis.setLinearVelocity(Vec3(0, speed, 0))
    car._chassis.setAngularVelocity(Vec3(0))
    car.tires.initialize_rolling(speed)
    for _ in range(120):
        tire_step(car, brake=1)
        assert car.signed_speed() * speed >= -1e-6
    assert abs(car.signed_speed()) < abs(speed)


@pytest.mark.parametrize(("drive", "brake"), [(0, 0), (200, 0), (0, 1), (200, .4)])
def test_wheel_angular_momentum_uses_full_tick_impulses(sim, drive, brake):
    car = sim.player
    old_omega = list(car.tires.omega)
    tire_step(car, drive=drive, brake=brake)
    for index, state in enumerate(car.snapshot().wheel_dynamics):
        applied_drive = drive / 2 if index >= 2 else 0.0
        assert state.drive_torque == pytest.approx(applied_drive)
        assert CAR.wheel_inertia * (car.tires.omega[index] - old_omega[index]) == pytest.approx(
            FIXED_DT * state.drive_torque
            - state.brake_angular_impulse
            - CAR.wheel_radius * state.longitudinal_impulse,
            abs=1e-9,
        )


def test_reset_shift_and_interpolation_preserve_tire_lifecycle(sim):
    for _ in range(30):
        sim.step(Control(throttle=1))
    previous = sim.snapshot()
    sim.step(Control(throttle=1))
    current = sim.snapshot()
    assert all(w.force_contact_tick == current.player.contact_tick - 1
               for w in current.player.wheel_dynamics)
    assert all(w.sample_tick == current.player.contact_tick
               for w in current.player.wheel_dynamics)
    assert interpolate(previous, current, .5).player.wheel_dynamics == current.player.wheel_dynamics
    omega, theta = list(sim.player.tires.omega), list(sim.player.tires.rotation)
    sim.player.shift(100)
    assert sim.player.tires.omega == omega
    assert sim.player.tires.rotation == theta
    sim.player.reset((95, 0, 20))
    assert sim.player.tires.omega == sim.player.tires.rotation == [0] * 4
    assert sim.player.snapshot().wheel_contacts == ()
    assert all(w.sample_tick == 0 and not w.sample_support
               for w in sim.player.snapshot().wheel_dynamics)
    sim.step(Control())
    assert all(w.force_contact_tick == 0 for w in sim.snapshot().player.wheel_dynamics)
    assert sim.snapshot().player.contact_tick == 1
    assert all(w.sample_tick == 1 and not w.sample_support
               for w in sim.snapshot().player.wheel_dynamics)


def test_post_bullet_slip_matches_current_snapshot_velocity_and_contact(sim):
    car = sim.player
    car._chassis.setLinearVelocity(Vec3(2, 8, 0))
    car._chassis.setAngularVelocity(Vec3(.1, -.2, .3))
    car.tires.initialize_rolling(5)
    previous = sim.snapshot().player
    sim.step(Control(throttle=.7, steering=.4))
    state = sim.snapshot().player
    orientation = car._chassis.getTransform().getQuat()
    velocity = Vec3(*state.velocity)
    angular = car._chassis.getAngularVelocity()
    config = car.tires.config
    for index, (wheel, contact) in enumerate(zip(state.wheel_dynamics, state.wheel_contacts)):
        assert wheel.sample_tick == state.contact_tick
        assert wheel.force_contact_tick == previous.contact_tick
        assert wheel.sample_support and contact.in_contact
        steer = Quat()
        steer.setHpr(Vec3(-wheel.steering, 0, 0))
        heading = orientation.xform(steer.xform(Vec3(0, 1, 0)))
        normal = Vec3(*contact.contact_normal)
        tangent = (heading - normal * heading.dot(normal)).normalized()
        axle = tangent.cross(normal)
        lever = Vec3(*contact.contact_point) - Vec3(*state.position)
        vx = (velocity + angular.cross(lever + normal * config.wheel_radius)).dot(tangent)
        vy = (velocity + angular.cross(lever)).dot(axle)
        denominator = max(abs(vx), config.slip_speed)
        assert wheel.longitudinal_speed == pytest.approx(vx, abs=1e-6)
        assert wheel.lateral_speed == pytest.approx(vy, abs=1e-6)
        assert wheel.kappa == pytest.approx(
            (config.wheel_radius * wheel.omega - vx) / denominator, abs=1e-6)
        assert wheel.alpha == pytest.approx(math.atan2(vy, denominator), abs=1e-6)
        # 力采用上一接触阶段的求解滑移，不拿完成Bullet后的κ重新解释该力。
        old_contact = previous.wheel_contacts[index]
        mu = config.road_friction if old_contact.surface == "asphalt" else config.grass_friction
        expected = tire_force(wheel.force_kappa, wheel.force_alpha, wheel.normal_load, mu, config)
        assert (wheel.fx, wheel.fy) == pytest.approx(expected, abs=.002)


def test_high_speed_contact_levers_use_current_body_pose(sim):
    car = sim.player
    car._chassis.setLinearVelocity(Vec3(0, 40, 0))
    car._chassis.setAngularVelocity(Vec3(0))
    car.tires.initialize_rolling(40)
    for _ in range(3):
        sim.step(Control())
        state = sim.snapshot().player
        assert all(contact.in_contact for contact in state.wheel_contacts)
        points = [Vec3(*contact.contact_point) for contact in state.wheel_contacts]
        origin = Vec3(*state.position)
        forward = car._chassis.getTransform().getQuat().getForward()
        levers = [(point - origin).dot(forward) for point in points]
        front, rear = sum(levers[:2]) / 2, sum(levers[2:]) / 2
        # 40m/s的一tick旧姿态会产生约.333m共同偏移；允许单精度及微小俯仰。
        assert front == pytest.approx(-rear, abs=1e-4)
        assert front == pytest.approx(CAR.wheelbase / 2, abs=1e-4)
        assert rear == pytest.approx(-CAR.wheelbase / 2, abs=1e-4)
        center = sum(points, Vec3(0)) / 4
        assert center.y == pytest.approx(origin.y, abs=1e-4)
        assert all(w.sample_tick == state.contact_tick
                   and w.force_contact_tick == state.contact_tick - 1
                   for w in state.wheel_dynamics)


def test_wheel_pose_uses_independent_angle_not_native_rotation(sim):
    car = sim.player
    car.tires.rotation = [.4, -.2, .8, -.6]
    for wheel in car._vehicle.getWheels():
        wheel.setRotation(123)
    state = car.snapshot()
    body = car._chassis.getTransform().getQuat()
    for index, wheel in enumerate(state.wheels):
        rotation = Quat()
        rotation.setFromAxisAngle(-math.degrees(car.tires.rotation[index]), Vec3(1, 0, 0))
        actual = Quat(*wheel.orientation)
        assert tuple(actual.xform(Vec3(0, 1, 0))) == pytest.approx(
            tuple(body.xform(rotation.xform(Vec3(0, 1, 0)))), abs=1e-6)


def test_five_degree_slope_parking_does_not_creep():
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    slope = math.radians(5)
    ground = BulletRigidBodyNode("parking-plane")
    ground.addShape(BulletPlaneShape(Vec3(0, -math.sin(slope), math.cos(slope)), 0))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda x, y: True, (0, 0, .55), pitch=5)
    try:
        def step():
            velocity = Vec3(car._chassis.getLinearVelocity())
            car.apply_command(VehicleCommand(brake=1))
            world.doPhysics(FIXED_DT, 0, FIXED_DT)
            car.after_step(velocity)

        for _ in range(600):
            step()
        start = car.snapshot().position
        previous = start
        longitudinal_forces = []
        for _ in range(1200):
            step()
            state = car.snapshot()
            assert math.dist(state.position, previous) < .001
            assert all(c.normal_load > 0 for c in state.wheel_contacts)
            longitudinal_forces.append(
                sum(w.longitudinal_impulse for w in state.wheel_dynamics) / FIXED_DT
            )
            previous = state.position
        assert math.dist(start, car.snapshot().position) < .01
        assert all(w.force_mode == "sticking" for w in car.snapshot().wheel_dynamics)
        mean_longitudinal_force = sum(longitudinal_forces) / len(longitudinal_forces)
        expected_grade_force = CAR.mass * 9.81 * math.sin(slope)
        assert mean_longitudinal_force == pytest.approx(expected_grade_force, rel=.01)
    finally:
        car.close()
