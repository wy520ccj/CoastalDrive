"""车型配置作用于真实Bullet几何和动力部件，实例及reset互不污染。"""
from dataclasses import replace

import pytest
from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import Vec3
from physics.export_reference import shape_axis_limits, shape_volume_center

from driver_assist import GAME_INPUT
from vehicle import Vehicle
from vehicle_config import CAR, body_center, wheel_hubs
from vehicle_state import FIXED_DT, VehicleCommand


def make_vehicle(config=CAR, *, ground=False):
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    if ground:
        plane = BulletRigidBodyNode("配置试验平地")
        plane.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
        world.attachRigidBody(plane)
    return world, Vehicle(world, lambda x, y: True, (0, 0, .55), config=config)


def step(world, car, count):
    for _ in range(count):
        previous = car._chassis.getLinearVelocity()
        car.apply_command(VehicleCommand())
        world.doPhysics(FIXED_DT, 0, FIXED_DT)
        car.after_step(previous)


def test_default_geometry_preserves_original_dimensions():
    expected = ((-.84, 1.1, .25), (.84, 1.1, .25),
                (-.84, -1.1, .25), (.84, -1.1, .25))
    for hub, original in zip(wheel_hubs(CAR), expected):
        assert hub == pytest.approx(original, abs=1e-15)
    assert body_center(CAR) == (0, 0, .42)


def test_bias_configuration_checks_port_dimensions_before_axle_dependency():
    with pytest.raises(ValueError, match="三项"):
        replace(CAR, axle_torque_bias_ratios=(1., 2.), differential_damping=(0.,))


def test_custom_bullet_geometry_and_reset_keep_instance_configuration():
    cfg = replace(CAR, mass=1450, wheel_radius=.37, wheelbase=2.6,
                  track_width=1.9, center_of_mass_height=.48,
                  front_weight_share=.6, collision_half_height=.46,
                  body_inertia=(700, 950, 1100), angular_damping=.12,
                  suspension_travel=.24, suspension_force_limit=7000)
    _world, car = make_vehicle(cfg)
    _other_world, other = make_vehicle()
    try:
        body = car._chassis
        limits = shape_axis_limits(body)
        assert tuple((high-low)/2 for low, high in limits) == pytest.approx(
            (cfg.collision_half_width, cfg.collision_half_length, cfg.collision_half_height), abs=1e-6)
        assert body.getMass() == pytest.approx(cfg.mass)
        assert tuple(body.getInertia()) == pytest.approx(cfg.body_inertia)
        assert body.getAngularDamping() == pytest.approx(cfg.angular_damping)
        center = shape_volume_center(body)
        assert tuple(center) == pytest.approx(body_center(cfg))
        for wheel, hub in zip(car._vehicle.getWheels(), wheel_hubs(cfg)):
            assert tuple(wheel.getChassisConnectionPointCs()) == pytest.approx(hub)
            assert wheel.getWheelRadius() == pytest.approx(cfg.wheel_radius)
            assert wheel.getMaxSuspensionTravelCm() == pytest.approx(24)
            assert wheel.getMaxSuspensionForce() == pytest.approx(7000)
            assert wheel.getSuspensionRestLength() == pytest.approx(.4)
        car.reset((0, 0, 1), speed=5)
        assert car.config is cfg
        assert car.input_config is GAME_INPUT
        for component in (car.assist, car.powertrain, car.steering, car.tires):
            assert component.config is cfg
        assert car.tires.hubs == wheel_hubs(cfg)
        assert car.tires.omega == pytest.approx([5 / cfg.wheel_radius] * 4)
        assert other.config is CAR
        assert other.tires.hubs == wheel_hubs(CAR)
        assert other._chassis.getMass() == pytest.approx(CAR.mass)
    finally:
        car.close()
        other.close()


def test_explicit_inertia_controls_real_angular_impulse_response():
    _, car = make_vehicle(replace(CAR, body_inertia=(500, 800, 1000)))
    try:
        car._chassis.applyTorqueImpulse(Vec3(50, 80, 100))
        assert tuple(car._chassis.getAngularVelocity()) == pytest.approx((.1, .1, .1))
    finally:
        car.close()


def test_axle_tracks_reach_native_wheels_and_front_ackermann():
    from vehicle_steering import wheel_angles

    config = replace(CAR, wheelbase=2.575, axle_track_widths=(1.52, 1.55), front_weight_share=.53)
    _, car = make_vehicle(config)
    try:
        expected = ((-.76, 1.21025, .25), (.76, 1.21025, .25),
                    (-.775, -1.36475, .25), (.775, -1.36475, .25))
        for wheel, hub in zip(car._vehicle.getWheels(), expected):
            assert tuple(wheel.getChassisConnectionPointCs()) == pytest.approx(hub)
        front_only = replace(config, axle_track_widths=None, track_width=1.52)
        assert wheel_angles(25., config) == wheel_angles(25., front_only)
        assert wheel_angles(25., replace(config, axle_track_widths=(1.52, 1.9))) == wheel_angles(25., config)
    finally:
        car.close()


@pytest.mark.parametrize("share", [.4, .6])
def test_front_weight_share_changes_real_static_suspension_load(share):
    cfg = replace(CAR, front_weight_share=share)
    world, car = make_vehicle(cfg, ground=True)
    try:
        step(world, car, 600)
        contacts = car.snapshot().wheel_contacts
        assert all(c.in_contact and c.normal_load > 0 for c in contacts)
        total = sum(c.normal_load for c in contacts)
        assert total == pytest.approx(cfg.mass * 9.81, rel=.01)
        assert sum(c.normal_load for c in contacts[:2]) / total == pytest.approx(share, abs=.025)
    finally:
        car.close()

