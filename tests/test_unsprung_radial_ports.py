"""轴对称包络的法向虚功；倾斜/加载状态不能凭滚动产生径向储能。"""

import numpy as np
import pytest
from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, Vec3

from unsprung_drivetrain import drivetrain_ports, tire_ports
from unsprung_dynamics import assemble_unsprung, cross_matrix, partition_vehicle
from unsprung_geometry import read_unsprung_geometry
from vehicle_designs import REFERENCE_DESIGN


def rotation(axis, angle):
    skew = cross_matrix(np.eye(3)[axis])
    return np.eye(3)+np.sin(angle)*skew+(1-np.cos(angle))*skew@skew


def tilted_query():
    config = REFERENCE_DESIGN
    world,body,road = BulletWorld(),BulletRigidBodyNode("query-body"),BulletRigidBodyNode("road")
    road.addShape(BulletPlaneShape(Vec3(0,0,1),0))
    road.setIntoCollideMask(BitMask32.bit(0))
    world.attachRigidBody(road)
    centers = np.array(((-.84,1.1,-.3),(.84,1.1,-.3),(-.84,-1.1,-.3),(.84,-1.1,-.3)))
    mass = partition_vehicle(config.mass,np.diag(config.body_inertia),(40.,)*4,centers)
    basis = rotation(0,.035)@rotation(1,-.025)
    position = np.array((0.,0.,.61))
    mechanical = assemble_unsprung(mass,basis,np.zeros(4),((0.,0.,1.),)*4,np.zeros(10))
    centers = position+mechanical.wheel_arms
    axes = np.tile(basis[:,0],(4,1))
    hardware = drivetrain_ports(mechanical,axes,basis[:,1],basis[:,1],np.tile(basis[:,1],(3,1)),0.,config)
    geometry = read_unsprung_geometry(world,body,centers,basis[:,2],axes,config)
    return world,body,road,position,centers,basis,hardware,geometry,config


def test_loaded_tilted_radial_envelope_is_independent_of_wheel_spin():
    world,_body,road,_pos,_centers,_basis,hardware,g,_config = tilted_query()
    try:
        legacy = tire_ports(hardware,g.offsets,g.tangents,g.laterals,g.normals,np.zeros((4,3)),np.zeros(4))
        actual = tire_ports(hardware,g.offsets,g.tangents,g.laterals,g.normals,np.zeros((4,3)),np.zeros(4),
                            normal_offsets=g.normal_offsets)
        assert max(abs(legacy.normal[:,12:]).flat)>1e-5
        assert np.array_equal(actual.normal[:,10:],np.zeros((4,6)))
        speed = np.r_[np.zeros(12),12.,24.,48.,96.]
        assert np.array_equal(actual.normal@speed,np.zeros(4))
        # 有限传动与切向滚动仍有惯性/速度端口，修法向不能断开Fx/Fy或轮端质量。
        assert np.array_equal(actual.longitudinal,legacy.longitudinal)
        assert np.array_equal(actual.lateral,legacy.lateral)
        assert np.linalg.norm(actual.longitudinal[:,12:])>.1
    finally:
        world.removeRigidBody(road)


@pytest.mark.parametrize("axis",[0,1,2])
def test_normal_port_matches_independent_actual_road_geometry_rotation(axis):
    world,body,road,pos,centers,basis,hardware,g,config = tilted_query()
    try:
        ports = tire_ports(hardware,g.offsets,g.tangents,g.laterals,g.normals,np.zeros((4,3)),np.zeros(4),
                           normal_offsets=g.normal_offsets)
        epsilon = 1e-5
        delta = []
        for sign in (1,-1):
            change = rotation(axis,sign*epsilon)
            trial = read_unsprung_geometry(world,body,(centers-pos)@change.T+pos,
                change@basis[:,2],hardware.axes@change.T,config)
            delta.append(trial.deflection)
        derivative = (delta[0]-delta[1])/(2*epsilon)
        assert derivative==pytest.approx(-ports.normal[:,3+axis],abs=1e-8)
    finally:
        world.removeRigidBody(road)
