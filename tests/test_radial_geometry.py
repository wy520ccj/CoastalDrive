"""有符号深度的解析圆几何、见证点/力方向和真实有限面切换。"""

import math
from itertools import product

import numpy as np
import pytest
from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, TransformState, Vec3
from radial_contact_kernels import signed_distance

from radial_geometry import RadialRoads
from vehicle_designs import REFERENCE_DESIGN

BOX = tuple(product((-.24,.24),(-.45,.45),(-.005,.005)))


@pytest.mark.parametrize("y,z",[(0.,.315),(0.,.4),(-.55,.31),(-.57,.31),(-.6,.31)])
def test_signed_box_depth_matches_independent_circle_edge_and_face_geometry(y,z):
    distance,normal,wheel,road = signed_distance((0.,y,z),(1.,0.,0.),BOX,.33,.22,.01,.003,0.)
    edge_distance = math.hypot(max(-.45-y,0.),z-.005)
    expected = edge_distance-.33
    assert distance==pytest.approx(expected,abs=2e-9)
    assert np.linalg.norm(normal)==pytest.approx(1.,abs=1e-12)
    assert np.array(wheel)-road==pytest.approx(distance*np.array(normal),abs=2e-10)
    assert road[2]==pytest.approx(.005,abs=1e-10)
    assert abs(road[1])<=.45+1e-10


def test_signed_query_retains_translation_and_axis_orientation_covariance():
    center,axis = np.array((0.,-.55,.31)),np.array((1.,0.,0.))
    baseline = signed_distance(tuple(center),tuple(axis),BOX,.33,.22,.01,.003,0.)
    # 绕轮轴旋转也是刚体变换；真实有限面一起旋转，不把场景坐标当材料量。
    angle = .13
    rotation = np.array(((1.,0.,0.),(0.,math.cos(angle),-math.sin(angle)),(0.,math.sin(angle),math.cos(angle))))
    shift = np.array((95.,2.,3.))
    result = signed_distance(tuple(rotation@center+shift),tuple(rotation@axis),
        tuple(map(tuple,np.asarray(BOX)@rotation.T+shift)),.33,.22,.01,.003,0.)
    assert result[0]==pytest.approx(baseline[0],abs=2e-9)
    assert result[1]==pytest.approx(rotation@baseline[1],abs=1e-5)
    assert result[3]==pytest.approx(rotation@baseline[3]+shift,abs=1e-6)


def test_ground_and_finite_bump_select_continuous_largest_real_compression():
    world,body = BulletWorld(),BulletRigidBodyNode("query-body")
    ground = BulletRigidBodyNode("ground")
    ground.addShape(BulletPlaneShape(Vec3(0,0,1),0))
    ground.setIntoCollideMask(BitMask32.bit(0))
    bump = BulletRigidBodyNode("bump")
    shape = BulletBoxShape(Vec3(.24,.45,.005)); shape.setMargin(0.)
    bump.addShape(shape); bump.setTransform(TransformState.makePos(Vec3(0.,.45,.005)))
    bump.setIntoCollideMask(BitMask32.bit(0))
    world.attachRigidBody(ground); world.attachRigidBody(bump)
    roads = RadialRoads(world,body,REFERENCE_DESIGN)
    actual_top = bump.getTransform().getPos().z+shape.getHalfExtentsWithoutMargin().z
    previous = None
    seen = set()
    try:
        for y in np.linspace(-.14,-.06,81):
            center = np.array((0.,y,.315))
            result = roads.query(np.tile(center,(4,1)),(0.,0.,1.),((1.,0.,0.),)*4)
            # 独立圆/角点深度与无限平面深度取最大，切换没有几何能量跳变。
            expected = max(.33-.315,.33-math.hypot(y,.315-.01))
            assert result.deflection[0]==pytest.approx(expected,abs=2e-9)
            if result.hits[0].node==bump:
                distance = math.hypot(y,.315-actual_top)
                assert result.normals[0]==pytest.approx((0.,y/distance,(.315-actual_top)/distance),abs=2e-13)
            if previous is not None:
                assert abs(result.deflection[0]-previous)<=.001
            previous = result.deflection[0]
            seen.add(result.hits[0].node.getName())
        assert seen=={"ground","bump"}
    finally:
        world.removeRigidBody(bump); world.removeRigidBody(ground)
