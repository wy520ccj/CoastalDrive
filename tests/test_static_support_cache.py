"""静态数值复用仍读取唯一世界的实际变换、形状与生命周期。"""

import pytest
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, TransformState, Vec3

from simulation import Control, Simulation
from suspension_contacts import cylinder_suspension_rays, static_support_shapes
from vehicle import Vehicle


def test_cached_support_tracks_movement_margin_shape_offset_and_removal():
    world = BulletWorld()
    ground = BulletRigidBodyNode('ground')
    box = BulletBoxShape(Vec3(2., 2., .05))
    box.setMargin(0.)
    ground.addShape(box)
    ground.setTransform(TransformState.makePos(Vec3(0., 0., -.05)))
    world.attachRigidBody(ground)
    chassis = BulletRigidBodyNode('car')
    cache = {}
    packets = {}
    rays = (((0., 0., 1.), (0., 0., -.5)),)

    def hit_height():
        geometry = static_support_shapes(world, chassis, BitMask32.bit(0), cache=cache, packet_cache=packets)
        hit, = cylinder_suspension_rays(world, chassis, rays, ((1., 0., 0.),),
                                      .33, .205, .01, static_shapes=geometry)
        return hit.point[2]

    assert hit_height() == pytest.approx(0., abs=1e-12)
    original = cache[ground][1]
    original_packet = packets['prepared']
    assert hit_height() == pytest.approx(0., abs=1e-12)
    assert cache[ground][1] is original
    assert packets['prepared'] is original_packet
    ground.setTransform(TransformState.makePos(Vec3(0., 0., .15)))
    assert hit_height() == pytest.approx(.2, abs=2e-8)
    assert cache[ground][1] is not original
    assert packets['prepared'] is not original_packet
    box.setMargin(.02)
    assert hit_height() == pytest.approx(.2, abs=2e-8)
    # BulletBox保持含margin的外廓；增加形状局部高度必须改变真实接点。
    ground.removeShape(box)
    ground.addShape(box, TransformState.makePos(Vec3(0., 0., .1)))
    assert hit_height() == pytest.approx(.3, abs=2e-8)
    world.removeRigidBody(ground)
    assert static_support_shapes(world, chassis, BitMask32.bit(0), cache=cache) == ()
    assert cache == {}


def test_simulation_reset_and_close_release_cached_world_references():
    sim = Simulation(seed=17, track='test', traffic_count=0)
    try:
        sim.step(Control())
        old_bodies = set(sim._static_support_cache)
        assert old_bodies
        sim.reset(23)
        assert sim._static_support_cache == {}
        assert sim._static_support_packet == {}
        sim.step(Control())
        assert old_bodies.isdisjoint(sim._static_support_cache)
    finally:
        sim.close()
    assert sim._static_support_cache == {}
    assert sim._static_support_packet == {}


def test_vehicle_neighborhood_reuses_only_unchanged_geometry_and_refreshes_outside():
    world = BulletWorld()
    ground = BulletRigidBodyNode('finite-platform')
    box = BulletBoxShape(Vec3(6., 6., .05))
    box.setMargin(0.)
    ground.addShape(box)
    ground.setTransform(TransformState.makePos(Vec3(0., 0., -.05)))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda _x, _y: True, (0., 0., .5))
    cache, packets = {}, {}

    def prepare():
        shapes = static_support_shapes(world, None, BitMask32.bit(0), cache=cache, packet_cache=packets)
        return car.suspension.prepare(world, car._chassis, car._vehicle.getWheels(), shapes)

    try:
        first = prepare()
        surfaces = car.suspension._candidate_cache['surfaces']
        second = prepare()
        assert car.suspension._candidate_cache['surfaces'] is surfaces
        assert second == first
        ground.setTransform(TransformState.makePos(Vec3(0., 0., .15)))
        moved = prepare()
        assert car.suspension._candidate_cache['surfaces'] is not surfaces
        assert moved.geometry[0] - first.geometry[0] == pytest.approx(.2, abs=2e-8)
        # 同一几何包内移出旧覆盖盒，仍查询真实平台边界。
        car._chassis.setTransform(TransformState.makePos(Vec3(12., 0., .5)))
        outside = prepare()
        assert not any(outside.touching)
        car.reset((0., 0., .5))
        assert car.suspension._support_shapes is None
        assert car.suspension._candidate_cache == {}
        assert any(prepare().touching)
    finally:
        car.close()
    assert car.suspension._support_shapes is None
    assert car.suspension._candidate_cache == {}
