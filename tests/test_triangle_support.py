"""真实有限三角面、接缝和胎宽；期望来自独立平面/圆几何。"""

import math

import pytest
from panda3d.bullet import (
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import TransformState, Vec3

from suspension_contacts import cylinder_suspension_rays
from suspension_kinematics import finite_contact_system
from triangle_support import TriangleSupport
from vehicle import Vehicle
from vehicle_config import CAR, wheel_hubs


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
