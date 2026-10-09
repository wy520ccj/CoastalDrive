"""真实有限三角面、接缝和胎宽；期望来自独立平面/圆几何。"""

import math
import pickle
import random

import pytest
from panda3d.bullet import (
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import TransformState, Vec3
from wheel_contact_kernels import cylinder_box_entry as numeric_box_entry
from wheel_contact_kernels import triangle_support_entry

from suspension_contacts import cylinder_suspension_rays
from suspension_kinematics import finite_contact_system
from triangle_support import TriangleSupport, triangle_entry
from vehicle import Vehicle
from vehicle_config import CAR, wheel_hubs
from wheel_envelope import _simplex_coordinates, cylinder_box_entry


def test_native_window_preserves_order_source_identity_nested_windows_and_lifetime():
    triangles = []
    for x in range(12):
        a,b,c = (float(x),0.,0.), (float(x)+.8,0.,0.), (float(x),1.,.01*x)
        triangles.append((a,b,c))
    mesh = TriangleSupport.build(triangles)
    for center,padding in (((3.,.4,0.),(1.,1.,1.)), ((-20.,0.,0.),(.1,.1,.1)),
                           ((6.,.5,0.),(20.,20.,20.))):
        expected = tuple(mesh.candidates(center,center,padding))
        window = mesh.window(center,center,padding)
        assert len(expected) == len(window.triangles)
        assert all(a is b for a,b in zip(expected,window.triangles))
        reconstructed = TriangleSupport(mesh.low,mesh.high,expected)
        assert window.triangle_bounds == reconstructed.triangle_bounds
        for x in (2.99,3.,3.8,4.,5.):
            arguments = ((x,.3,1.),(x,.3,-1.),.01,(1.,0.,0.),.33,.205,.01,.003)
            assert window.entry(*arguments) == reconstructed.entry(*arguments)
        inner = window.window(center,center,(.01,.01,.01))
        assert inner.triangles == tuple(window.candidates(center,center,(.01,.01,.01)))
        restored = pickle.loads(pickle.dumps(window))
        del window
        assert restored.triangles == expected
        assert inner.entry((3.,.2,1.),(3.,.2,-1.),.01,(1.,0.,0.),.33,.205,.01,.003) == (
            TriangleSupport(mesh.low,mesh.high,inner.triangles).entry(
                (3.,.2,1.),(3.,.2,-1.),.01,(1.,0.,0.),.33,.205,.01,.003))


def test_numeric_box_query_matches_complete_legacy_face_and_edge_sweep():
    random_source = random.Random(8107)
    hits = misses = 0
    for _ in range(512):
        x, y = random_source.uniform(-1.4,1.4), random_source.uniform(-1.4,1.4)
        angle = random_source.uniform(-.7,.7)
        axis = (math.cos(angle),math.sin(angle),0.)
        args = ((x,y,1.),(x+.03,y-.02,-1.),(1.,1.,.05),.01,axis,.33,.205/2,.01,.003)
        expected = cylinder_box_entry(*args)
        actual = numeric_box_entry(*args, _simplex_coordinates)
        assert actual == expected
        hits += actual is not None
        misses += actual is None
    assert hits > 0 and misses > 0


def test_numeric_mesh_query_keeps_bvh_order_faces_edges_and_misses():
    triangles = []
    for x in (-3., 0., 3.):
        for y in (-3., 0., 3.):
            a, b, c, d = ((x-.8,y-.8,.03*x), (x+.8,y-.8,.03*x),
                          (x+.8,y+.8,.03*x+.04), (x-.8,y+.8,.03*x+.04))
            triangles.extend(((a,b,c),(a,c,d)))
    mesh = TriangleSupport.build(triangles)
    random_source = random.Random(1708)
    hits = misses = 0
    for _ in range(512):
        x, y = random_source.uniform(-4.,4.), random_source.uniform(-4.,4.)
        start, end = (x,y,1.), (x+.03,y-.02,-1.)
        angle = random_source.uniform(-.4,.4)
        axis = (math.cos(angle),math.sin(angle),0.)
        args = (mesh._native,start,end,.01,axis,.33,.205,.01,.003,triangle_entry)
        expected = triangle_support_entry(*args)
        actual = triangle_support_entry(*args, _simplex_coordinates)
        assert actual == expected
        hits += actual is not None
        misses += actual is None
    assert hits > 0 and misses > 0


def platform():
    triangles = (((-1.,-1.,0.),(1.,-1.,0.),(1.,1.,0.)),
                 ((-1.,-1.,0.),(1.,1.,0.),(-1.,1.,0.)))
    mesh = BulletTriangleMesh()
    for triangle in triangles:
        mesh.addTriangle(*(Vec3(*p) for p in triangle))
    shape = BulletTriangleMeshShape(mesh,dynamic=False)
    shape.setMargin(.01)
    body = BulletRigidBodyNode("finite-road")
    body.addShape(shape)
    body.setPythonTag("suspension_mesh",TriangleSupport.build(triangles))
    world = BulletWorld()
    world.attachRigidBody(body)
    return world,body


@pytest.mark.parametrize("x,y", ((0.,0.),(.2,.2),(.2,.20001)))
def test_adjacent_triangle_faces_keep_same_height_without_fake_internal_edge(x,y):
    world,body = platform()
    hit, = cylinder_suspension_rays(world,BulletRigidBodyNode("query"),
        ((Vec3(x,y,1.),Vec3(x,y,-1.)),),((1.,0.,0.),),.33,.205,.01,.003)
    margin = body.getShape(0).getMargin()
    assert hit.node == body
    assert hit.fraction == pytest.approx((1.-margin-.33)/2,abs=1e-12)
    assert hit.normal == pytest.approx((0.,0.,1.),abs=1e-12)
    assert hit.point[2] == pytest.approx(margin,abs=1e-12)
    assert hit.surface.triangles is not None


def test_actual_mesh_edge_has_finite_radius_but_does_not_extend_as_infinite_plane():
    world,_body = platform()
    path = ((Vec3(0.,1.1,1.),Vec3(0.,1.1,-1.)),)
    hit, = cylinder_suspension_rays(world,BulletRigidBodyNode("query"),path,((1.,0.,0.),),.33,.205,.01,.003)
    expected_height = math.sqrt((.33+.01)**2-.1**2)
    assert hit.fraction == pytest.approx((1-expected_height)/2,abs=1e-8)
    outside = ((Vec3(1.2,0.,1.),Vec3(1.2,0.,-1.)),)
    absent, = cylinder_suspension_rays(world,BulletRigidBodyNode("query"),outside,((1.,0.,0.),),.33,.205,.01,.003)
    assert absent is None
    surface = hit.surface
    # 同一纯几何对象在末姿态也必须拒绝离开有限网格的接点。
    assert surface.entry((1.4,0.,1.),(1.4,0.,-1.),(1.,0.,0.)) is None


def test_real_finite_path_accepts_grazing_support_without_point_one_cutoff():
    from panda3d.bullet import BulletPlaneShape
    world = BulletWorld()
    ground = BulletRigidBodyNode("floor")
    ground.addShape(BulletPlaneShape(Vec3(0,0,1),0))
    world.attachRigidBody(ground)
    car = Vehicle(world,lambda _x,_y: True,(0,0,1.))
    try:
        pose = TransformState.makePosHpr(Vec3(0,0,1.),Vec3(0,0,86.))
        quat = pose.getQuat()
        hub = quat.xform(Vec3(*wheel_hubs(CAR)[0]))
        direction = quat.xform(Vec3(0,0,-1))
        axis = quat.getRight()
        norm = math.sqrt(sum(x*x for x in axis))
        axial = abs(axis.z) / norm
        support_height = (.205/2-.01)*axial + (.33-.01-.003)*math.sqrt(1-axial*axial) + .01
        height = support_height - .35 * direction.z - hub.z
        car._chassis.setTransform(TransformState.makePosHpr(Vec3(0,0,height),Vec3(0,0,86.)))
        system = car.suspension.prepare(world,car._chassis,car._vehicle.getWheels())
        assert system.touching[0]
        assert 0. < system.alignment[0] < .1
        assert system.geometry[0] == pytest.approx(.05,abs=2e-6)
        assert all(math.isfinite(x) for x in system.gradients[0])
    finally:
        car.close()


@pytest.mark.parametrize("height", (0., .04))
def test_end_pose_queries_adjacent_world_segment_and_its_actual_height(height):
    from panda3d.bullet import BulletBoxShape
    world = BulletWorld()
    for name, y, z in (("before", -1., 0.), ("after", 1., height)):
        road = BulletRigidBodyNode(name)
        road.addShape(BulletBoxShape(Vec3(4., 1., .05)))
        road.setTransform(TransformState.makePos(Vec3(0., y, z-.05)))
        world.attachRigidBody(road)
    # 前轴在分界前0.5m；一步移动1m，起点与末点分别由不同道路物体支撑。
    car = Vehicle(world, lambda _x, _y: True, (0., -.5-wheel_hubs(CAR)[0][1], .5))
    try:
        system = car.suspension.prepare(world, car._chassis, car._vehicle.getWheels())
        count = world.getNumRigidBodies()
        plane = system.kinematics[0]
        point = plane.surface.local(plane.hub)
        assert point[1] == pytest.approx(-.5, abs=2e-7)
        endpoint = finite_contact_system(system, (0., 10., 0.), (0., 0., 0.), .1)
        assert endpoint.touching[0]
        delta_length = .1 * sum(g*v for g,v in zip(endpoint.gradients[0], (0.,10.,0.,0.,0.,0.)))
        assert delta_length == pytest.approx(-height, abs=2e-8)
        assert world.getNumRigidBodies() == count
    finally:
        car.close()
