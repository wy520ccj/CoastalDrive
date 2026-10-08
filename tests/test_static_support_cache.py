"""静态数值复用仍读取唯一世界的实际变换、形状与生命周期。"""

import pytest
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, TransformState, Vec3
from wheel_contact_kernels import cached_surface_entry

from simulation import Control, Simulation
from suspension_contacts import cylinder_suspension_rays, static_support_shapes
from triangle_support import triangle_entry
from vehicle import Vehicle
from wheel_envelope import _simplex_coordinates, cylinder_box_entry


def test_numeric_surface_queries_match_original_after_origin_and_world_changes():
    sim = Simulation(seed=17, track='coastal', traffic_count=0)
    try:
        car = sim.player
        spawn = tuple(car._chassis.getTransform().getPos())
        for delta in ((0.,0.,0.), (.01,.03,0.), (1.,2.,.01)):
            position = tuple(a+b for a,b in zip(spawn,delta))
            car._chassis.setTransform(TransformState.makePosHpr(Vec3(*position),Vec3(3.,0.,1.)))
            shapes = static_support_shapes(sim._world, car._chassis, BitMask32.bit(0))
            system = car.suspension.prepare(sim._world, car._chassis, car._vehicle.getWheels(), shapes)
            compared = 0
            for contact in system.kinematics:
                if contact is None:
                    continue
                surface = contact.surface
                for shift in (-.001,0.,.001):
                    start = tuple(contact.hub[a]-surface.wheel_radius*contact.direction[a]+(shift if a==0 else 0.) for a in range(3))
                    end = tuple(contact.hub[a]+surface.reach*contact.direction[a]+(shift if a==0 else 0.) for a in range(3))
                    args = (surface.candidates,start,end,surface.wheel_axis,surface.offset,
                            surface.wheel_radius,surface.width,surface.shoulder,surface.crown,triangle_entry,cylinder_box_entry)
                    expected = cached_surface_entry(*args)
                    actual = cached_surface_entry(*args, _simplex_coordinates)
                    assert actual == expected
                    assert actual[0]
                    compared += 1
            assert compared > 0
    finally:
        sim.close()


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
