"""同一真实世界的完整准备、首命中和旧材料初值逐字段对照。"""

import random
from dataclasses import fields, is_dataclass, replace

import pytest
import suspension_prepare_reference
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import Quat, TransformState, Vec3
from suspension_prepare_reference import ReferenceSuspension
from wheel_contact_kernels import surface_initial_hits, surface_ray_hits, suspension_prepare_paths

import vehicle_suspension
from suspension import SuspensionState
from suspension_contacts import RayContact
from suspension_geometry import CylinderSurface
from triangle_support import triangle_entry
from vehicle_config import CAR, wheel_hubs
from vehicle_suspension import Suspension
from vehicle_tire_step import TireBodyInput, TireWheelInput
from wheel_envelope import _simplex_coordinates, cylinder_box_entry
from wheel_geometry import mechanical_axis


def exact(a, b):
    assert type(a) is type(b)
    if is_dataclass(a):
        for field in fields(a):
            if field.compare:
                exact(getattr(a, field.name), getattr(b, field.name))
    elif isinstance(a, tuple):
        assert len(a) == len(b)
        for left, right in zip(a, b):
            exact(left, right)
    else:
        assert a.hex() == b.hex() if isinstance(a, float) else a == b


def test_four_paths_keep_original_axes_positions_and_signed_steering():
    rng = random.Random(66103)
    for _ in range(256):
        orientation = Quat()
        orientation.setHpr(Vec3(rng.uniform(-180, 180), rng.uniform(-30, 30), rng.uniform(-30, 30)))
        origin = tuple(rng.uniform(-1e6, 1e6) for _ in range(3))
        direction = tuple(orientation.xform(Vec3(0, 0, -1)))
        arms = tuple(tuple(orientation.xform(Vec3(*hub))) for hub in wheel_hubs(CAR))
        wheels = tuple(TireWheelInput(.18, rng.uniform(-35, 35)) for _ in range(4))
        rests, lengths, axes, rays = suspension_prepare_paths(wheels, CAR, origin, direction, arms,
                                                              tuple(orientation.getRight()), tuple(orientation.getForward()))
        old_rests = tuple(w.getSuspensionRestLength() for w in wheels)
        old_lengths = tuple(rest+CAR.suspension_travel+CAR.wheel_radius for rest in old_rests)
        old_axes = tuple(mechanical_axis(orientation.getRight(), orientation.getForward(), -w.getSteering()) for w in wheels)
        starts = tuple(tuple(origin[a]+hub[a]-direction[a]*CAR.wheel_radius for a in range(3)) for hub in arms)
        old_rays = tuple((start, tuple(start[a]+direction[a]*length for a in range(3))) for start, length in zip(starts, old_lengths))
        exact((rests, lengths, axes, rays), (old_rests, old_lengths, old_axes, old_rays))


@pytest.mark.parametrize('tick,forces', [(0, (0.,)*4), (10, (0.,)*4), (10, (100., 0., 100., 0.))])
def test_full_initial_system_does_not_mutate_old_compression_and_keeps_actual_geometry(tick, forces):
    world = BulletWorld()
    road = BulletRigidBodyNode('support')
    road.addShape(BulletBoxShape(Vec3(8., 8., .1)))
    road.setTransform(TransformState.makePos(Vec3(0., 0., -.1)))
    world.attachRigidBody(road)
    config = replace(CAR, wheel_crown_height=0.)
    current, old = Suspension(config, wheel_hubs(config)), ReferenceSuspension(config, wheel_hubs(config))
    old.envelope = current.envelope
    compression = (.03, .04, .05, .06)
    for height in (.7, .45, 1.3, .4):
        pose = TransformState.makePos(Vec3(0., 0., height))
        body = TireBodyInput(pose, (0.,)*3, (0.,)*3, None, 0.)
        wheels = tuple(TireWheelInput(.18, 0.) for _ in range(4))
        for adapter in (current, old):
            adapter.compression = compression
            adapter.state = SuspensionState(force_tick=tick, normal_force=forces)
        actual = current.prepare(world, body, wheels)
        expected = old.prepare(world, body, wheels)
        assert current.compression is compression and old.compression is compression
        exact(current.geometry, old.geometry)
        for name in ('compression', 'geometry', 'gradients', 'touching', 'alignment', 'angular_damping'):
            exact(getattr(actual, name), getattr(expected, name))
        for a, b in zip(actual.kinematics, expected.kinematics):
            if a is None:
                assert b is None
                continue
            exact(a, b)
            assert a.surface.queries == b.surface.queries == {}
            assert a.surface.candidates is not b.surface.candidates
    current.clear_queries()
    old.clear_queries()


def test_batch_first_hit_keeps_equal_fraction_order_and_original_surface_metadata():
    world = BulletWorld()
    for name in ('first', 'second'):
        road = BulletRigidBodyNode(name)
        road.addShape(BulletBoxShape(Vec3(3., 3., .1)))
        world.attachRigidBody(road)
    body = TireBodyInput(TransformState.makePos(Vec3(0., 0., .4)), (0.,)*3, (0.,)*3, None, 0.)
    adapter = Suspension(CAR, wheel_hubs(CAR))
    system = adapter.prepare(world, body, tuple(TireWheelInput(.18, 0.) for _ in range(4)))
    cache = system.kinematics[0].surface.candidates
    surfaces = cache['surfaces']
    origin = (0., 0., .4)
    world_rays = (((0., 0., 1.), (0., 0., -1.)),)*4
    relative_rays = tuple(tuple(tuple(p[a]-origin[a] for a in range(3)) for p in ray) for ray in world_rays)
    axes = ((1., 0., 0.),)*4
    actual = surface_initial_hits(surfaces, cache, world_rays, relative_rays, axes, origin,
        CAR.wheel_radius, CAR.wheel_width, CAR.wheel_shoulder_radius, CAR.wheel_crown_height,
        CylinderSurface, RayContact, _simplex_coordinates, False)
    for a, (start, end) in zip(actual, relative_rays):
        expected = min(surface_ray_hits(surfaces, start, end, axes[0], origin,
            CAR.wheel_radius, 2.-CAR.wheel_radius, CAR.wheel_width, CAR.wheel_shoulder_radius,
            CAR.wheel_crown_height, CylinderSurface, RayContact, triangle_entry, cylinder_box_entry, False),
            key=lambda hit: hit.fraction)
        exact(a, expected)
        assert a.node == surfaces[0][0]
    adapter.clear_queries()


@pytest.mark.parametrize('tick,forces', [(0, (0.,)*4), (10, (100., 0., 100., 0.))])
@pytest.mark.parametrize('mixed', [False, True])
def test_frozen_sloped_hits_keep_dynamic_backface_and_missing_support_rules(monkeypatch, tick, forces, mixed):
    """冻结已完成的几何查询，仅对照原生装配对接触资格与斜面梯度的处理。"""
    fixed, dynamic = BulletRigidBodyNode('fixed'), BulletRigidBodyNode('dynamic')
    dynamic.setMass(10.)
    hits = (RayContact(fixed, .4, (2., 1., .3), (.3, .4, .8660254037844386)),
            RayContact(dynamic if mixed else fixed, .5, (-2., 1., .3), (0., 0., 1.)),
            RayContact(fixed, .6, (2., -1., .3), (0., 0., -1. if mixed else 1.)),
            None if mixed else RayContact(fixed, .7, (-2., -1., .3), (-.3, -.4, .8660254037844386)))

    def frozen_hits(*args, **kwargs):
        return hits

    monkeypatch.setattr(vehicle_suspension, 'cylinder_suspension_rays', frozen_hits)
    monkeypatch.setattr(suspension_prepare_reference, 'cylinder_suspension_rays', frozen_hits)
    world = BulletWorld()
    body = TireBodyInput(TransformState.makePos(Vec3(0., 0., .5)), (0.,)*3, (0.,)*3, None, .17)
    wheels = tuple(TireWheelInput(.18, 3. if i < 2 else -0.) for i in range(4))
    new, old = Suspension(CAR, wheel_hubs(CAR)), ReferenceSuspension(CAR, wheel_hubs(CAR))
    old.envelope = new.envelope
    for adapter in (new, old):
        adapter.compression = (.03, -.0, -.02, .06)
        adapter.state = SuspensionState(force_tick=tick, normal_force=forces)
    actual, expected = new.prepare(world, body, wheels, ()), old.prepare(world, body, wheels, ())
    exact(actual, expected)
    exact(new.geometry, old.geometry)
    assert actual.touching == ((True, False, False, False) if mixed else (True,)*4)
    for adapter in (new, old):
        adapter.clear_queries()
