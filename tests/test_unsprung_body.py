"""实际Bullet质量/惯量/形状、导向和共同机械冲量核对。"""

from itertools import product

import numpy as np
import pytest
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, Point3, TransformState, Vec3
from test_unsprung_dynamics import CENTERS, GUIDES, LOCKED, MASSES

from suspension import stiffness_matrix
from unsprung_body import (
    NativeWheelGuides,
    SprungBodyFrame,
    apply_joint_forces,
    quaternion_rotation,
)
from unsprung_drivetrain import drivetrain_ports, tire_ports
from unsprung_dynamics import assemble_unsprung, partition_vehicle
from unsprung_joint import solve_unsprung_joint
from vehicle_collision import chassis_shapes
from vehicle_designs import REFERENCE_DESIGN


def native_vehicle(gravity=(0.,0.,0.), pose=None, masses=MASSES, displacement=(0.,)*4):
    world = BulletWorld()
    world.setGravity(Vec3(*gravity))
    partition = partition_vehicle(1200.,LOCKED,masses,CENTERS)
    frame = SprungBodyFrame.from_partition(partition)
    body = BulletRigidBodyNode("sprung-test")
    body.setIntoCollideMask(BitMask32.bit(1))
    body.setDeactivationEnabled(False)
    body.setLinearDamping(0.)
    body.setAngularDamping(0.)
    frame.install(body,REFERENCE_DESIGN,pose or TransformState.makeIdentity())
    world.attachRigidBody(body)
    guides = NativeWheelGuides(world,body,frame,displacement)
    return world,body,frame,guides


def test_full_principal_inertia_and_design_pose_preserve_real_collision_geometry():
    pose = TransformState.makePosHpr(Vec3(3.,-2.,4.),Vec3(27.,-13.,19.))
    world,body,frame,guides = native_vehicle(pose=pose)
    p = frame.partition
    assert np.max(np.abs(np.asarray(p.inertia)-np.diag(np.diag(p.inertia))))>1.
    assert body.getMass()+sum(point.getMass() for point in guides.points) == 1200.
    assert body.getMass() == p.mass
    for (shape,original),i in zip(chassis_shapes(REFERENCE_DESIGN),range(body.getNumShapes())):
        old = original.getMat()*pose.getMat()
        new = body.getShapeTransform(i).getMat()*body.getTransform().getMat()
        half = shape.getHalfExtentsWithoutMargin()
        for signs in product((-1.,1.),repeat=3):
            vertex = Point3(*(np.asarray(tuple(half))*signs))
            assert tuple(new.xformPoint(vertex)) == pytest.approx(tuple(old.xformPoint(vertex)),abs=2e-6)
    assert np.asarray(frame.reference_pose(body).getMat()) == pytest.approx(np.asarray(pose.getMat()),abs=5e-7)
    position,rotation = frame.read(body)
    original_rotation = quaternion_rotation(pose.getQuat())
    assert rotation == pytest.approx(original_rotation,abs=2e-7)
    assert position == pytest.approx(np.asarray(tuple(pose.getPos()))+original_rotation@p.center,abs=5e-7)
    inverse = body.getInvInertiaTensorWorld()
    actual = np.array([[inverse.getCell(i,j) for j in range(3)] for i in range(3)])
    expected = original_rotation@np.linalg.inv(p.inertia)@original_rotation.T
    assert actual == pytest.approx(expected,abs=3e-10)
    guides.close()
    assert world.getNumConstraints() == 0 and world.getNumRigidBodies() == 1
    world.removeRigidBody(body)
    assert world.getNumRigidBodies() == 0


def test_native_five_bodies_fall_together_without_spurious_relative_motion():
    pose = TransformState.makePos(Vec3(0.,0.,10.))
    world,body,_frame,guides = native_vehicle(gravity=(0.,0.,-9.81),pose=pose,masses=(40.,)*4)
    assert world.getNumRigidBodies() == 5 and world.getNumConstraints() == 4
    for _ in range(24):
        world.doPhysics(1/240,0,1/240)
    _centers,speeds,travel,relative,transverse = guides.read()
    assert tuple(body.getLinearVelocity()) == pytest.approx((0.,0.,-.981),abs=5e-7)
    assert speeds == pytest.approx(np.tile((0.,0.,-.981),(4,1)),abs=5e-7)
    assert travel == pytest.approx(np.zeros(4),abs=1e-6)
    assert relative == pytest.approx(np.zeros(4),abs=5e-7)
    assert transverse == pytest.approx(np.zeros((4,2)),abs=5e-7)
    guides.close()


def test_native_guides_transmit_real_lateral_impulse_and_keep_vertical_freedom():
    world,body,frame,guides = native_vehicle(masses=(40.,)*4)
    # 四轮相同侧向冲量，不产生偏航；总体动量而非父体单独质量决定平动。
    for point in guides.points:
        point.applyCentralImpulse(Vec3(30.,0.,0.))
    world.doPhysics(1/240,0,1/240)
    _centers,speeds,_travel,_relative,_transverse = guides.read()
    momentum = frame.partition.mass*np.asarray(tuple(body.getLinearVelocity()))+40.*speeds.sum(axis=0)
    assert momentum == pytest.approx((120.,0.,0.),abs=2e-5)
    assert abs(body.getLinearVelocity().x)>.08
    # 轴向冲量作用在一个真实轮心，不把其速度强设成车身速度。
    before = guides.points[0].getLinearVelocity().z
    guides.points[0].applyCentralImpulse(Vec3(0.,0.,4.))
    world.doPhysics(1/240,0,1/240)
    assert guides.points[0].getLinearVelocity().z-before == pytest.approx(.1,abs=2e-5)
    guides.close()


def test_displaced_guides_use_actual_force_levers_and_conserve_angular_impulse():
    world,body,frame,guides = native_vehicle(masses=(40.,)*4,displacement=(.08,)*4)
    centers = guides.read()[0]
    impulse = np.array((.3,0.,0.))
    initial_moment = np.cross(centers,impulse).sum(axis=0)
    for point in guides.points:
        point.applyCentralImpulse(Vec3(*impulse))
    guides.refresh_frames()
    world.doPhysics(1/240,0,1/240)
    centers,speeds,_q,_u,_xy = guides.read()
    position,rotation = frame.read(body)
    velocity,angular = np.asarray(tuple(body.getLinearVelocity())),np.asarray(tuple(body.getAngularVelocity()))
    actual = (np.cross(position,frame.partition.mass*velocity)
              +rotation@frame.partition.inertia@rotation.T@angular+40.*np.cross(centers,speeds).sum(axis=0))
    assert actual == pytest.approx(initial_moment,abs=2e-7)
    guides.close()


def test_native_collision_still_stops_whole_vehicle_with_four_real_masses_attached():
    world,body,frame,guides = native_vehicle(masses=(40.,)*4)
    wall = BulletRigidBodyNode("external-wall")
    wall.addShape(BulletBoxShape(Vec3(.1,4.,4.)))
    wall.setTransform(TransformState.makePos(Vec3(2.,0.,0.)))
    wall.setIntoCollideMask(BitMask32.bit(1))
    world.attachRigidBody(wall)
    body.setLinearVelocity(Vec3(3.,0.,0.))
    for point in guides.points:
        point.setLinearVelocity(Vec3(3.,0.,0.))
    collisions = 0
    for _ in range(120):
        guides.refresh_frames()
        world.doPhysics(1/240,0,1/240)
        collisions += sum(m.getNumManifoldPoints() for m in world.getManifolds()
                          if body in (m.getNode0(),m.getNode1()) and wall in (m.getNode0(),m.getNode1()))
    assert collisions>0
    assert frame.reference_pose(body).getPos().x<1.
    _centers,speeds,_q,_u,transverse = guides.read()
    momentum = frame.partition.mass*body.getLinearVelocity().x+40.*speeds[:,0].sum()
    assert momentum<50. and np.max(np.abs(transverse))<2e-5
    guides.close()
    world.removeRigidBody(wall)


def test_actual_native_static_support_matches_joint_without_chassis_velocity_repair():
    config,dt = REFERENCE_DESIGN,1/240
    masses = (40.,)*4
    ks = np.asarray(stiffness_matrix(config.suspension_spring_rates,config.suspension_antiroll_rates))
    q = np.linalg.solve(ks,np.full(4,(config.mass-sum(masses))*9.81/4))
    radial = np.full(4,200000.)
    delta = (ks@q+40.*9.81)/radial
    # 这里名义轮心-0.10m；参考行程零对应名义车身高度0.43m。
    pose = TransformState.makePos(Vec3(0.,0.,.43-delta[0]-q[0]))
    world,body,frame,guides = native_vehicle(gravity=(0.,0.,-9.81),pose=pose,masses=masses,displacement=q)
    position,rotation = frame.read(body)
    centers,_speeds,travel,relative,_transverse = guides.read()
    assert centers[:,2] == pytest.approx(.33-delta,abs=1e-7)
    z = np.zeros(16)
    z[10] = 250.
    mechanical = assemble_unsprung(frame.partition,rotation,travel,GUIDES,z[:10])
    graph = drivetrain_ports(mechanical,np.tile((1.,0.,0.),(4,1)),(0.,1.,0.),(0.,1.,0.),
                             ((0.,1.,0.),)*3,0.,config)
    contacts = tire_ports(graph,-centers[:,2,None]*np.array(GUIDES),np.tile((0.,1.,0.),(4,1)),
                          np.tile((1.,0.,0.),(4,1)),GUIDES,np.zeros((4,3)),np.zeros(4))
    old_down = graph.downstream@z
    known = np.r_[mechanical.gravity_forces((0.,0.,-9.81)),np.zeros(6)]
    step = solve_unsprung_joint(graph,contacts,z,old_down,q,delta,np.zeros((4,2)),np.zeros((4,2)),known,
        np.zeros(4),radial,np.full(4,500.),np.full(4,.7),np.zeros(4),30.,.12,0.,np.zeros(4),0.,False,dt,config)
    assert step.velocity == pytest.approx(z,abs=1e-11)
    assert step.normal.normal_force == pytest.approx(np.full(4,config.mass*9.81/4),abs=1e-9)
    apply_joint_forces(body,guides,graph,contacts,step,30.,.12,old_down,np.zeros(3),dt,config)
    world.doPhysics(dt,0,dt)
    _centers,_speeds,_travel,relative,_transverse = guides.read()
    assert tuple(body.getLinearVelocity()) == pytest.approx((0.,0.,0.),abs=1e-8)
    assert tuple(body.getAngularVelocity()) == pytest.approx((0.,0.,0.),abs=1e-8)
    assert relative == pytest.approx(np.zeros(4),abs=1e-8)
    assert tuple(body.getTransform().getPos()) == pytest.approx(position,abs=1e-8)
    guides.close()
