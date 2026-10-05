"""通过真实 Bullet 积分验证轮接触诊断的单位和失效边界。"""

from dataclasses import replace

import pytest
from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import Vec3

from simulation import Control, Simulation, interpolate, shift_snapshot
from vehicle import Vehicle
from vehicle_config import CAR
from vehicle_contacts import read_wheel_contacts, road_support, shift_contacts
from vehicle_state import FIXED_DT, CarState


@pytest.mark.parametrize("normal, expected", [
    ((0, 0, 1), True),
    ((.8660254037844386, 0, .5), True),
    ((0, .8660254037844386, .5), True),
    ((.8661, 0, .4999), False),
    ((1, 0, 0), False),
    ((0, 0, -1), False),
])
def test_road_support_definition(normal, expected):
    assert road_support(normal) is expected


def test_support_classification_preserves_raw_contact(rig):
    world, car = rig
    advance(world)
    for wheel in car._vehicle.getWheels():
        wheel.setMaxSuspensionForce(1000)
    advance(world, 1)
    contacts = read_wheel_contacts(car._vehicle, car.on_asphalt)
    for contact in contacts:
        unsupported = replace(contact, contact_normal=(1, 0, 0))
        assert not road_support(unsupported.contact_normal)
        assert unsupported.in_contact
        assert unsupported.suspension_force == contact.suspension_force > 1000
        assert unsupported.normal_load == contact.normal_load == 1000
    assert read_wheel_contacts(car._vehicle, car.on_asphalt) == contacts


@pytest.fixture
def rig():
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("diagnostic-ground")
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda x, y: x < 0, (0, 0, .55),
                  config=replace(CAR, suspension_coupled_enabled=False))
    yield world, car
    car.close()


def advance(world, count=240):
    for _ in range(count):
        world.doPhysics(FIXED_DT, 0, FIXED_DT)


def test_static_load_lengths_and_surface(rig):
    world, car = rig
    advance(world)
    contacts = read_wheel_contacts(car._vehicle, car.on_asphalt)
    assert len(contacts) == 4
    assert sum(c.normal_load for c in contacts) == pytest.approx(CAR.mass * 9.81, rel=.002)
    for c in contacts:
        assert c.in_contact
        assert c.contact_normal == pytest.approx((0, 0, 1))
        assert c.contact_point[2] == pytest.approx(0, abs=1e-5)
        assert c.compression == pytest.approx(.4 - c.suspension_length)
        assert c.skid == pytest.approx(1)
    assert [c.surface for c in contacts] == ["asphalt", "grass", "asphalt", "grass"]


def test_airborne_fields_are_explicitly_invalid(rig):
    world, car = rig
    advance(world)
    car.reset((0, 0, 3))
    advance(world, 1)
    contacts = read_wheel_contacts(car._vehicle, car.on_asphalt)
    for c in contacts:
        assert not c.in_contact
        assert c.normal_load == c.suspension_force == 0
        assert c.contact_point is c.contact_normal is c.skid is c.surface is None
        assert c.compression == pytest.approx(0)
    assert CarState((0, 0, 0)).wheel_contacts == ()
    assert CarState((0, 0, 0)).contact_tick == 0


def test_applied_load_is_capped_without_losing_raw_force(rig):
    world, car = rig
    advance(world)
    for wheel in car._vehicle.getWheels():
        wheel.setMaxSuspensionForce(1000)
    advance(world, 1)
    for c in read_wheel_contacts(car._vehicle, car.on_asphalt):
        assert c.suspension_force > 1000
        assert c.normal_load == 1000


def test_cross_slope_produces_asymmetric_wheel_loads():
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    normal = Vec3(-.15, 0, 1).normalized()
    ground = BulletRigidBodyNode("cross-slope")
    ground.addShape(BulletPlaneShape(normal, 0))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda x, y: True, (0, 0, .55),
                  config=replace(CAR, suspension_coupled_enabled=False))
    try:
        advance(world, 8)
        contacts = read_wheel_contacts(car._vehicle, car.on_asphalt)
        assert abs(contacts[0].normal_load - contacts[1].normal_load) > 100
        for c in contacts:
            if c.in_contact:
                assert c.contact_normal == pytest.approx(tuple(normal), abs=1e-6)
    finally:
        car.close()


def test_shift_preserves_force_and_normal(rig):
    world, car = rig
    advance(world)
    contacts = read_wheel_contacts(car._vehicle, car.on_asphalt)
    shifted = shift_contacts(contacts, 100)
    for before, after in zip(contacts, shifted):
        assert after.contact_point[1] == pytest.approx(before.contact_point[1] - 100)
        assert replace(after, contact_point=before.contact_point) == before
    assert shift_contacts((), 100) == ()


def test_snapshot_reset_and_next_step_have_current_contact_lifecycle():
    sim = Simulation(track="test")
    try:
        assert sim.snapshot().player.wheel_contacts == ()
        for _ in range(240):
            sim.step(Control())
        before = sim.snapshot()
        assert before.player.contact_tick == 240
        assert len(before.player.wheel_contacts) == 4
        for _ in range(5):
            assert sim.snapshot() == before
        sim.player.reset((180, 0, 20))
        assert sim.snapshot().player.wheel_contacts == ()
        assert sim.snapshot().player.contact_tick == 0
        sim.step(Control())
        after = sim.snapshot()
        assert after.player.contact_tick == 1
        assert all(not c.in_contact and c.normal_load == 0 for c in after.player.wheel_contacts)
        assert before.player.contact_tick == 240
    finally:
        sim.close()


def test_interpolation_keeps_measured_tick_and_shift_keeps_global_contact_points():
    sim = Simulation(track="endless", traffic_count=0)
    try:
        for _ in range(240):
            sim.step(Control())
        before = sim.snapshot()
        sim.step(Control(throttle=1))
        current = sim.snapshot()
        rendered = interpolate(before, current, .5)
        assert rendered.player.wheel_contacts == current.player.wheel_contacts
        assert rendered.player.contact_tick == current.player.contact_tick
        shifted = shift_snapshot(current, 100)
        for a, b in zip(current.player.wheel_contacts, shifted.player.wheel_contacts):
            assert a.contact_point[1] + current.origin_y == pytest.approx(
                b.contact_point[1] + shifted.origin_y
            )
            assert replace(b, contact_point=a.contact_point) == a
        sim.player.shift(100)
        assert sim.player.snapshot().wheel_contacts == shifted.player.wheel_contacts
    finally:
        sim.close()
