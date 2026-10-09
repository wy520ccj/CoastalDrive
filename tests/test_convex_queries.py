"""原Hull顶点、Bullet扫掠与唯一世界几何的独立对照。"""

import math
import random

import pytest
from convex_cast_kernels import hull, support
from panda3d.bullet import BulletConvexHullShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, Quat, TransformState, Vec3

from convex_queries import HullGeometry, native_transform, wheel_hull
from simulation import Simulation
from suspension_contacts import cylinder_suspension_rays, static_support_shapes, wheel_sweep_shape


def test_crowned_support_retains_all_original_vertices_and_float_tie_order():
    radius,width,shoulder,crown = .33,.205,.01,.004
    half = width/2-shoulder
    points = tuple(tuple(Vec3(half*(ring/8-1),
        (radius-shoulder-crown*(ring/8-1)**2)*math.cos(segment*math.pi/32),
        (radius-shoulder-crown*(ring/8-1)**2)*math.sin(segment*math.pi/32)))
        for ring in range(17) for segment in range(64))
    full,fast = hull(points,shoulder),hull(points,shoulder,True)
    randomizer = random.Random(17)
    for _ in range(100000):
        direction = tuple(randomizer.uniform(-1,1)*10**randomizer.uniform(-10,10) for _axis in range(3))
        assert support(fast,direction)==support(full,direction)
    for direction in ((1,0,0),(-1,0,0),(0,0,0),(0,1,0),(0,0,1)):
        assert support(fast,direction)==support(full,direction)


def test_standalone_original_bullet_cast_matches_world_sweep():
    world = BulletWorld()
    body = BulletRigidBodyNode('actual-hull')
    vertices = tuple(tuple(Vec3(x,y,z)) for x in (-.2,.2) for y in (-3.,3.) for z in (-.4,.4))
    shape = BulletConvexHullShape()
    for point in vertices:
        shape.addPoint(Vec3(*point))
    shape.setMargin(.01)
    body.addShape(shape)
    world.attachRigidBody(body)
    identity = native_transform(TransformState.makeIdentity())
    geometry = HullGeometry(vertices,shape.getMargin(),identity,identity)
    config = .33,.205,.01,.004
    original_wheel,fast_wheel = wheel_sweep_shape(*config),wheel_hull(*config)
    randomizer = random.Random(23)
    compared = 0
    for _ in range(1024):
        rotation = Quat()
        rotation.setHpr(Vec3(randomizer.uniform(-50,50),randomizer.uniform(-10,10),randomizer.uniform(-10,10)))
        start = Vec3(randomizer.uniform(-.55,.55),randomizer.uniform(-2.8,2.8),randomizer.uniform(.8,1.2))
        end = start+Vec3(0,0,-1.4)
        first,last = (TransformState.makePosQuatScale(point,rotation,Vec3(1)) for point in (start,end))
        expected = world.sweepTestClosest(original_wheel,first,last,BitMask32.bit(0),0.)
        actual = geometry.entry(fast_wheel,native_transform(first),native_transform(last))
        assert (actual is not None)==expected.hasHit()
        if actual is not None:
            fraction,normal,point = actual
            assert fraction==expected.getHitFraction()
            assert normal==tuple(expected.getHitNormal())
            assert point==pytest.approx(tuple(expected.getHitPos()),abs=1e-7)
            compared += 1
    assert compared>700


def test_actual_coastal_hulls_query_same_geometry_without_changing_collision_masks():
    sim = Simulation(seed=17,traffic_count=0)
    try:
        car = sim.player
        world = sim._world
        bodies = tuple(world.getRigidBodies())
        masks = tuple(body.getIntoCollideMask() for body in bodies)
        old = static_support_shapes(world,car._chassis,BitMask32.bit(0))
        new = static_support_shapes(world,car._chassis,BitMask32.bit(0),cache={},packet_cache={})
        assert len(new.hulls)==2
        count = 0
        for body in bodies:
            if body not in new.hulls:
                continue
            for shape in new.hulls[body][::11]:
                center = shape.shape_pose[:3]
                for offset in (-.3,0.,.3):
                    start = (center[0]+offset,center[1],center[2]+1.)
                    end = (start[0],start[1],center[2]-.8)
                    args = (world,car._chassis,((start,end),),((1.,0.,0.),),.33,.205,.01,.004)
                    expected, = cylinder_suspension_rays(*args,static_shapes=old)
                    actual, = cylinder_suspension_rays(*args,static_shapes=new)
                    assert (actual is not None)==(expected is not None)
                    if actual is not None:
                        assert actual.node==expected.node
                        assert actual.fraction==pytest.approx(expected.fraction,abs=1e-7)
                        assert actual.normal==pytest.approx(expected.normal,abs=2e-6)
                        assert actual.point==pytest.approx(expected.point,abs=2e-5)
                        count += 1
        assert count>30
        assert tuple(body.getIntoCollideMask() for body in bodies)==masks
    finally:
        sim.close()
