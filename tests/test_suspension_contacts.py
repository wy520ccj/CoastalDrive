"""独立几何交点核对：细长Box假命中、漏命中和同世界遮挡。"""

import pytest
from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, TransformState, Vec3

from suspension_contacts import box_entry, suspension_rays


def test_long_thin_box_contact_is_on_actual_top_face():
    world = BulletWorld()
    ground = BulletRigidBodyNode("one-side")
    ground.addShape(BulletBoxShape(Vec3(.4, 40., .05)))
    ground.setTransform(TransformState.makePos(Vec3(-.84, 0., -.05)))
    world.attachRigidBody(ground)
    start = Vec3(-.6425960063934326, 1.095295786857605, .6961512565612793)
    end = Vec3(-.9158802032470703, 1.0999619960784912, -.1927773356437683)
    hit, = suspension_rays(world, BulletRigidBodyNode("chassis"), ((start, end),))
    expected = -start.z / (end.z - start.z)
    assert hit.node == ground
    assert hit.fraction == pytest.approx(expected, abs=2e-8)
    assert hit.point == pytest.approx(tuple(start + (end - start) * expected), abs=1e-7)
    assert hit.point[2] == pytest.approx(0., abs=1e-7)
    assert hit.normal == (0., 0., 1.)


def test_box_entry_does_not_depend_on_native_reported_candidates():
    world = BulletWorld()
    body = BulletRigidBodyNode("obstacle")
    body.addShape(BulletBoxShape(Vec3(2.024, 2.024, 2.024)))
    body.setTransform(TransformState.makePos(Vec3(0., 2.024, -3.)))
    world.attachRigidBody(body)
    start, end = Vec3(-2.027535, 1.323740, -4.894639), Vec3(2.506727, 1.292858, -2.102663)
    hit, = suspension_rays(world, BulletRigidBodyNode("chassis"), ((start, end),))
    expected = (-float(body.getShape(0).getHalfExtentsWithMargin().x) - start.x) / (end.x - start.x)
    assert hit.node == body
    assert hit.fraction == pytest.approx(expected, abs=2e-8)
    assert hit.normal == (-1., 0., 0.)


@pytest.mark.parametrize("start,end,expected", (
    ((0., 0., 2.), (0., 0., -2.), (.375, (0., 0., 1.))),
    ((0., 0., -2.), (0., 0., 2.), (.375, (0., 0., -1.))),
    ((2., 0., 0.), (-2., 0., 0.), (.25, (1., 0., 0.))),
    ((0., 0., 0.), (0., 0., 2.), None),
    ((2., 0., 2.), (2., 0., -2.), None),
    ((0., 0., 2.), (0., 0., 1.), None),
    ((0., 0., .5), (0., 0., -2.), (0., (0., 0., 1.))),
))
def test_finite_entry_and_inside_parallel_boundaries(start, end, expected):
    assert box_entry(start, end, (1., 1., .5)) == expected


def test_compound_box_uses_each_current_shape_pose_and_preserves_margin():
    world = BulletWorld()
    body = BulletRigidBodyNode("compound")
    shape = BulletBoxShape(Vec3(.4, 40., .05))
    shape.setMargin(.002)
    local = TransformState.makePosHpr(Vec3(.3, -.2, .4), Vec3(0., 0., 20.))
    body.addShape(shape, local)
    body.addShape(BulletBoxShape(Vec3(.1)), TransformState.makePos(Vec3(8., 0., 0.)))
    world.attachRigidBody(body)
    for position in ((2., 100., .8), (2., 0., .8)):
        body.setTransform(TransformState.makePosHpr(Vec3(*position), Vec3(15., 3., 0.)))
        pose = body.getTransform().compose(local)
        start = pose.getMat().xformPoint(Vec3(.1, 1., 1.))
        end = pose.getMat().xformPoint(Vec3(.1, 1., -1.))
        hit, = suspension_rays(world, BulletRigidBodyNode("chassis"), ((start, end),))
        expected_point = pose.getMat().xformPoint(Vec3(.1, 1., .05))
        expected_normal = pose.getQuat().xform(Vec3(0., 0., 1.))
        assert hit.point == pytest.approx(tuple(expected_point), abs=1e-5)
        assert hit.normal == pytest.approx(tuple(expected_normal), abs=1e-6)
        assert hit.fraction == pytest.approx(.475, abs=1e-6)


def test_same_world_nearest_occluder_and_mask_are_preserved():
    world = BulletWorld()
    chassis = BulletRigidBodyNode("chassis")
    chassis.setMass(1200.)
    chassis.addShape(BulletBoxShape(Vec3(1., 1., .1)))
    chassis.setTransform(TransformState.makePos(Vec3(0., 0., 1.)))
    world.attachRigidBody(chassis)
    ground = BulletRigidBodyNode("plane")
    ground.addShape(BulletPlaneShape(Vec3(0., 0., 1.), 0.))
    world.attachRigidBody(ground)
    invisible = BulletRigidBodyNode("masked-box")
    invisible.addShape(BulletBoxShape(Vec3(1., 1., .05)))
    invisible.setTransform(TransformState.makePos(Vec3(0., 0., 1.5)))
    invisible.setIntoCollideMask(BitMask32.allOff())
    world.attachRigidBody(invisible)
    rays = ((Vec3(0., 0., 2.), Vec3(0., 0., -1.)),)
    hit, = suspension_rays(world, chassis, rays)
    assert hit.node == ground
    blocker = BulletRigidBodyNode("dynamic-blocker")
    blocker.setMass(10.)
    blocker.addShape(BulletBoxShape(Vec3(1., 1., .1)))
    blocker.setTransform(TransformState.makePos(Vec3(0., 0., .5)))
    world.attachRigidBody(blocker)
    hit, = suspension_rays(world, chassis, rays)
    assert hit.node == blocker
    assert not hit.node.isStatic()
