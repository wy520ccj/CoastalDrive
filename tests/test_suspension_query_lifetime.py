"""支撑查询复用只属于当前子步；下一子步读取实际世界变化。"""

import pytest
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import TransformState, Vec3

from vehicle import Vehicle


def test_next_prepare_reads_moved_support_instead_of_previous_query():
    world = BulletWorld()
    road = BulletRigidBodyNode("moving-test-platform")
    shape = BulletBoxShape(Vec3(6., 6., .05))
    shape.setMargin(0.)
    road.addShape(shape)
    road.setTransform(TransformState.makePos(Vec3(0., 0., -.05)))
    world.attachRigidBody(road)
    car = Vehicle(world, lambda _x, _y: True, (0., 0., .5))
    try:
        first = car.suspension.prepare(world, car._chassis, car._vehicle.getWheels())
        surface = first.kinematics[0].surface
        ray = (0., 0., .5), (0., 0., -1.), (1., 0., 0.)
        original = surface.relative_entry(*ray)
        assert surface.relative_entry(*ray) == original
        assert len(surface.queries) == 1
        road.setTransform(TransformState.makePos(Vec3(0., 0., .15)))
        second = car.suspension.prepare(world, car._chassis, car._vehicle.getWheels())
        next_surface = second.kinematics[0].surface
        assert next_surface.queries == {}
        moved = next_surface.relative_entry(*ray)
        assert moved[2][2] - original[2][2] == pytest.approx(.2, abs=2e-8)
    finally:
        car.close()
