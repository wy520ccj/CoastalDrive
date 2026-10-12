"""批量读取仍跟踪实际世界变化、稳定顺序、有限网格和原生凸体。"""

import pytest
from panda3d.bullet import (
    BulletBoxShape,
    BulletConvexHullShape,
    BulletPlaneShape,
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import BitMask32, ConfigVariableBool, NodePath, Vec3
from wheel_contact_kernels import static_support_read

from suspension_contacts import static_support_shapes
from triangle_support import TriangleSupport


@pytest.fixture(params=[True, False])
def transform_policy(request):
    variable = ConfigVariableBool('transform-cache')
    previous = variable.getValue()
    variable.setValue(request.param)
    try:
        yield
    finally:
        variable.setValue(previous)


def test_live_qualification_order_and_shape_changes(transform_policy):
    world = BulletWorld()
    bodies = []
    for name in ('tie', 'tie', 'alpha'):
        body = BulletRigidBodyNode(name)
        body.addShape(BulletBoxShape(Vec3(1.)))
        body.setIntoCollideMask(BitMask32.bit(0))
        world.attachRigidBody(body)
        bodies.append(body)
    cache, packets = {}, {}
    mask = BitMask32.bit(0)

    def read():
        value = static_support_shapes(world, None, mask, cache=cache, packet_cache=packets)
        expected = sorted((body for body in world.getRigidBodies()
                           if body.isStatic() and not (body.getIntoCollideMask() & mask).isZero()),
                          key=lambda body: (body.getName(), tuple(body.getTransform().getPos())))
        assert [group[0] for group in value] == expected
        assert tuple(value) == static_support_shapes(world, None, mask)
        assert set(cache) == set(expected)
        return value

    first = read()
    assert read() is first
    bodies[0].setName('aardvark')
    assert read()[0][0] == bodies[0]
    bodies[0].setIntoCollideMask(BitMask32.bit(1))
    read()
    assert bodies[0] not in cache
    bodies[1].setMass(1.)
    read()
    assert bodies[1] not in cache
    bodies[1].setMass(0.)
    read()
    bodies[2].removeShape(bodies[2].getShape(0))
    assert not read()[0][1]
    bodies[2].addShape(BulletPlaneShape(Vec3(0., 0., 1.), .1))
    assert read()[0][1]
    parent = NodePath('support-parent')
    NodePath(bodies[2]).reparentTo(parent)
    previous = cache[bodies[2]][1]
    parent.setPos(2., 1., .5)
    read()
    assert cache[bodies[2]][1] is not previous
    for body in bodies:
        world.removeRigidBody(body)
    assert tuple(read()) == () and not cache


def test_mesh_tag_replacement_and_unregistered_mutable_hull(transform_policy):
    world = BulletWorld()
    mesh = BulletTriangleMesh()
    triangle = ((0., 0., 0.), (2., 0., 0.), (0., 2., 0.))
    mesh.addTriangle(*(Vec3(*point) for point in triangle))
    road = BulletRigidBodyNode('mesh')
    road.addShape(BulletTriangleMeshShape(mesh, dynamic=False))
    world.attachRigidBody(road)
    hull = BulletConvexHullShape()
    for point in ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.), (0., 0., 1.)):
        hull.addPoint(Vec3(*point))
    convex = BulletRigidBodyNode('convex')
    convex.addShape(hull)
    world.attachRigidBody(convex)
    cache, packets = {}, {}

    def read():
        value = static_support_shapes(world, None, BitMask32.bit(0), cache=cache, packet_cache=packets)
        assert tuple(value) == static_support_shapes(world, None, BitMask32.bit(0))
        return value

    read()
    assert not cache[road][1][1]
    road.setPythonTag('suspension_mesh', TriangleSupport.build((triangle,)))
    read()
    assert cache[road][1][1]
    previous = cache[road][1]
    replacement = TriangleSupport.build((triangle,))
    road.setPythonTag('suspension_mesh', replacement)
    read()
    assert cache[road][1] is not previous
    assert cache[road][1][2][0][6] is replacement
    previous = cache[convex][1]
    hull.addPoint(Vec3(3., 0., 0.))
    read()
    assert cache[convex][1] is not previous
    assert not cache[convex][1][1]
    # 缺少注册顶点仍走原生凸体查询，不能把它当作Box或无限平面。
    assert convex not in packets['prepared'].hulls
    road.clearPythonTag('suspension_mesh')
    read()
    assert not cache[road][1][1]


def test_native_reader_invalid_boundary_reports_error():
    with pytest.raises(TypeError):
        static_support_read(BulletWorld(), None, BitMask32.bit(0), [], NodePath, (), Vec3(1.), None)
