"""有限实体接触的末状态、虚功、自旋对称与初值微小运动精度。"""

import numpy as np
import pytest
from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, TransformState, Vec3

from radial_geometry import RadialRoads
from unsprung_contact_geometry import FiniteRadialContact
from unsprung_drivetrain import drivetrain_ports
from unsprung_dynamics import assemble_unsprung, partition_vehicle
from vehicle_designs import REFERENCE_DESIGN


def contact_case():
    config = REFERENCE_DESIGN
    world,body = BulletWorld(),BulletRigidBodyNode("query-body")
    ground = BulletRigidBodyNode("ground")
    ground.addShape(BulletPlaneShape(Vec3(0,0,1),0))
    ground.setIntoCollideMask(BitMask32.bit(0));world.attachRigidBody(ground)
    bump = BulletRigidBodyNode("bump")
    shape = BulletBoxShape(Vec3(.24,.45,.005));shape.setMargin(0.)
    bump.addShape(shape);bump.setTransform(TransformState.makePos(Vec3(-.84,.45,.005)))
    bump.setIntoCollideMask(BitMask32.bit(0));world.attachRigidBody(bump)
    nominal = ((-.84,1.1,-.3),(.84,1.1,-.3),(-.84,-1.1,-.3),(.84,-1.1,-.3))
    mass = partition_vehicle(config.mass,np.diag(config.body_inertia),(40.,)*4,nominal)
    mechanical = assemble_unsprung(mass,np.eye(3),np.zeros(4),((0.,0.,1.),)*4,np.zeros(10))
    centers = mechanical.wheel_arms+np.array((0.,-.088-1.1,.315-mechanical.wheel_arms[0,2]))
    axes = np.tile((1.,0.,0.),(4,1))
    hardware = drivetrain_ports(mechanical,axes,(0.,1.,0.),(0.,1.,0.),((0.,1.,0.),)*3,0.,config)
    roads = RadialRoads(world,body,config)
    context = FiniteRadialContact(roads,hardware,centers,np.eye(3),axes,np.zeros((4,3)),
                                 np.zeros((4,3)),np.zeros(4),1/240,config,lambda x,y:True)
    return world,ground,bump,context


def test_new_finite_feature_participates_before_world_step_and_has_exact_normal_virtual_work():
    world,ground,bump,context = contact_case()
    try:
        velocity = np.zeros(16);velocity[1]=5.
        result = context.evaluate(velocity)
        assert context.initial.hits[0].node==ground
        assert result.geometry.hits[0].node==bump
        assert result.geometry.deflection[0]>context.initial.deflection[0]+.002
        predicted_work = -context.dt*result.scale*(result.contacts.normal@velocity+result.contacts.steering_velocity[:,2])
        assert predicted_work==pytest.approx(result.geometry.deflection-context.initial.deflection,abs=1e-10)
        assert np.array_equal(result.contacts.normal[:,10:],np.zeros((4,6)))
        assert np.linalg.norm(result.contacts.normal[:,:3],axis=1)==pytest.approx(np.ones(4),abs=1e-12)
        assert world.getNumRigidBodies()==2 and world.getNumConstraints()==0
    finally:
        world.removeRigidBody(bump);world.removeRigidBody(ground)


def test_finite_normal_geometry_is_not_changed_by_rotor_speeds():
    world,ground,bump,context = contact_case()
    try:
        velocity = np.zeros(16);velocity[1]=5.
        result = context.evaluate(velocity)
        changed = velocity.copy();changed[10:]=(100.,200.,30.,40.,50.,60.)
        assert context.evaluate(changed) is result
    finally:
        world.removeRigidBody(bump);world.removeRigidBody(ground)


def test_native_guide_bias_moves_real_predicted_contact_and_keeps_separate_virtual_work():
    world,ground,bump,context = contact_case()
    try:
        context.wheel_velocity_bias = np.array(((.01,-.02,.003),)*4)
        velocity = np.zeros(16);velocity[1]=5.;velocity[3:6]=(.1,-.2,.3)
        result = context.evaluate(velocity)
        surface = (result.contacts.normal@velocity+result.contacts.steering_velocity[:,2]
                   +result.contacts.guide_velocity[:,2])
        assert -context.dt*result.scale*surface==pytest.approx(
            result.geometry.deflection-context.initial.deflection,abs=1e-10)
        assert result.contacts.steering_velocity[:,2]==pytest.approx(np.zeros(4),abs=1e-15)
        assert result.geometry.hits[0].node==bump
    finally:
        world.removeRigidBody(bump);world.removeRigidBody(ground)


@pytest.mark.parametrize("vertical",[-1e-5,-1e-8,-1e-11,0.,1e-11,1e-8,1e-5])
def test_same_plane_small_motion_keeps_analytic_pressure_gradient_without_cancellation(vertical):
    world,ground,bump,context = contact_case()
    try:
        velocity = np.zeros(16);velocity[2]=vertical
        result = context.evaluate(velocity)
        assert result.contacts.normal[:,2]==pytest.approx(np.ones(4),abs=1e-12)
        assert result.scale==pytest.approx(np.ones(4),abs=1e-12)
        assert result.contacts.normal[:,[0,1]].max()==0.
    finally:
        world.removeRigidBody(bump);world.removeRigidBody(ground)
