"""道路坡度来自实际支撑面；悬架俯仰不参与坡度项。"""

import math
from dataclasses import replace

import pytest
from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, Vec3

from vehicle import Vehicle
from vehicle_config import CAR
from vehicle_dynamics import aerodynamic_load, contact_grade
from vehicle_state import FIXED_DT, Control, VehicleCommand


@pytest.mark.parametrize("velocity,wind,force", (
    ((3.,4.,12.), (0.,0.,0.), (-39.,-52.,-156.)),
    ((3.,4.,12.), (3.,4.,12.), (0.,0.,0.)),
    ((0.,10.,0.), (0.,20.,0.), (0.,100.,0.)),
    ((0.,10.,0.), (0.,-10.,0.), (0.,-400.,0.)),
    ((0.,10.,0.), (10.,10.,0.), (100.,0.,0.)),
    ((0.,0.,12.), (0.,0.,0.), (0.,0.,-144.)),
))
def test_three_dimensional_relative_air_speed_sets_load_and_direction(velocity,wind,force):
    config = replace(CAR, air_density=1., drag_coefficient=.5, frontal_area=4.)
    relative, load = aerodynamic_load(velocity,wind,config)
    assert relative == tuple(v-w for v,w in zip(velocity,wind))
    assert load == pytest.approx(force,abs=1e-12)
    assert sum(f*v for f,v in zip(load,relative)) <= 0.


def test_actual_bullet_body_receives_vertical_drag_and_snapshot_records_power():
    world = BulletWorld()
    config = replace(CAR, air_density=1., drag_coefficient=.5, frontal_area=4.)
    car = Vehicle(world, lambda _x,_y: True, (0.,0.,20.), config=config)
    try:
        car._chassis.setLinearVelocity(Vec3(3.,4.,12.))
        car.apply_command(VehicleCommand(gear=0))
        assert tuple(car._chassis.getTotalForce()) == pytest.approx((-39.,-52.,-156.),abs=1e-5)
        dynamics = car.snapshot().dynamics
        assert dynamics.air_relative_velocity == (3.,4.,12.)
        assert dynamics.aerodynamic_force_vector == (-39.,-52.,-156.)
        assert dynamics.aerodynamic_force == 169.
        assert dynamics.aerodynamic_power == -2197.
        assert dynamics.rolling_force == 0.
    finally:
        car.close()


def test_contact_grade_uses_heading_and_support_only():
    slope = (0, -math.sin(math.radians(6)), math.cos(math.radians(6)))
    assert contact_grade(0, [slope]) == pytest.approx(6)
    assert contact_grade(180, [slope] * 4) == pytest.approx(-6)
    assert contact_grade(90, [slope]) == pytest.approx(0, abs=1e-10)
    assert contact_grade(0, []) is None
    assert contact_grade(0, [(0.2, 0, 0.98)] * 2) == 0


def plane_vehicle(grade=0, heading=0):
    angle = math.radians(grade)
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("standard-plane")
    ground.addShape(BulletPlaneShape(Vec3(0, -math.sin(angle), math.cos(angle)), 0))
    ground.setIntoCollideMask(BitMask32.bit(0) | BitMask32.bit(1))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda x, y: True, (0, 0, 0.55), heading=heading)
    return world, car


def advance(world, car, control, ticks):
    for _ in range(ticks):
        velocity = Vec3(car._chassis.getLinearVelocity())
        car.apply_control(control)
        world.doPhysics(FIXED_DT, 0, FIXED_DT)
        car.after_step(velocity)


def test_flat_acceleration_does_not_count_body_pitch_as_road_grade():
    world, car = plane_vehicle()
    try:
        advance(world, car, Control(), 240)
        peak_pitch = 0
        peak_grade_force = 0
        for _ in range(360):
            advance(world, car, Control(throttle=1), 1)
            state = car.snapshot()
            peak_pitch = max(peak_pitch, abs(state.pitch))
            peak_grade_force = max(peak_grade_force, abs(state.dynamics.grade_force))
        assert peak_pitch > 0.1
        assert peak_grade_force < 0.01
    finally:
        car.close()


@pytest.mark.parametrize("grade,heading", [(6, 0), (6, 180), (-6, 0)])
def test_actual_slope_grade_force_has_direction_of_travel_sign(grade, heading):
    world, car = plane_vehicle(grade, heading)
    try:
        advance(world, car, Control(brake=1), 240)
        car.apply_control(Control(brake=1))
        expected = CAR.mass * 9.81 * math.sin(math.radians(grade))
        if heading == 180:
            expected *= -1
        assert car.dynamics.grade_force == pytest.approx(expected, abs=0.1)
        assert car.dynamics.front_load + car.dynamics.rear_load == pytest.approx(
            CAR.mass * 9.81 * math.cos(math.radians(grade)), abs=0.1
        )
    finally:
        car.close()


def test_reset_in_air_does_not_reuse_ground_support():
    world, car = plane_vehicle(6)
    try:
        advance(world, car, Control(brake=1), 240)
        car.reset((0, 0, 20), pitch=12)
        car.apply_control(Control(throttle=1))
        assert car.dynamics.grade_force == 0
        assert car.dynamics.front_load == car.dynamics.rear_load == 0
        assert all(w.getEngineForce() == 0 for w in car._vehicle.getWheels())
        advance(world, car, Control(throttle=1), 12)
        assert car.dynamics.grade_force == 0
    finally:
        car.close()
