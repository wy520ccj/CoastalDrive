"""四轮簧下法向块的静载、自由落体、离地及独立势能/力学账。"""

from dataclasses import replace

import numpy as np
import pytest
from test_unsprung_dynamics import GUIDES, MASSES, partition

from unsprung_contact import normal_block
from unsprung_dynamics import assemble_unsprung
from vehicle_config import CAR

CONFIG = replace(CAR,suspension_spring_rates=(24000.,)*4,
                 suspension_compression_damping=(1800.,)*4,
                 suspension_extension_damping=(2400.,)*4,
                 suspension_antiroll_rates=(6000.,5000.))
NORMALS = np.array(((0.,0.,1.),)*4)
RADIAL = np.array((200000.,)*4)


def potential(q):
    return (sum(k*x*x/2 for k,x in zip(CONFIG.suspension_spring_rates,q))
            +sum(k*(q[i]-q[i+1])**2/2 for i,k in zip((0,2),CONFIG.suspension_antiroll_rates))
            +sum(k*max(abs(x)-CONFIG.suspension_travel,0.)**2/2 for k,x in zip(CONFIG.suspension_stop_rates,q)))


@pytest.mark.parametrize("q,tire,road,speed,ct", [
    ((.06,)*4,(.014,)*4,(0.,)*4,(0.,)*10,0.),
    ((.23,-.21,.19,-.03),(.03,.002,-.015,.01),(0.,.01,0.,-.025),(.1,.2,-.6,.2,-.1,.05,.2,-.3,.1,-.2),0.),
    ((.23,-.21,.19,-.03),(.03,.002,-.015,.01),(0.,.01,0.,-.025),(.1,.2,-.6,.2,-.1,.05,.2,-.3,.1,-.2),600.),
    ((0.,)*4,(-.1,)*4,(0.,)*4,(0.,)*10,600.),
    ((0.,)*4,(-.01,)*4,(0.,0.,.03,.02),(0.,)*10,600.),
])
def test_implicit_normal_has_unilateral_contact_and_closed_frozen_energy(q,tire,road,speed,ct):
    p = partition()
    mechanics = assemble_unsprung(p,np.eye(3),q,GUIDES,speed)
    gravity = mechanics.gravity_forces((0.,0.,-9.81))
    dt = 1/240
    result = normal_block(mechanics,speed,q,tire,NORMALS,RADIAL,(ct,)*4,gravity,road,dt,CONFIG)
    assert result.normal_force.min()>=0.
    assert result.energy_error == pytest.approx(0.,abs=2e-11)
    assert result.impulse_residual<1e-10
    assert result.suspension_damping_loss>=0. and result.tire_damping_loss>=0.
    assert result.elastic_numerical_loss>=-1e-10 and result.kinetic_numerical_loss>=0.
    assert result.compression == pytest.approx(np.array(q)+dt*result.velocity[6:],abs=1e-15)
    endpoint_wheel_velocity = np.array([result.velocity[:3]+np.cross(result.velocity[3:6],r)+n*result.velocity[6+i]
                                      for i,(r,n) in enumerate(zip(mechanics.wheel_arms,mechanics.guides))])
    expected = np.array(tire)+road-dt*np.sum(endpoint_wheel_velocity*NORMALS,axis=1)
    assert result.tire_deflection == pytest.approx(expected,abs=1e-15)
    change_ke = .5*(result.velocity@mechanics.mass_matrix@result.velocity-np.array(speed)@mechanics.mass_matrix@np.array(speed))
    change_pe = potential(result.compression)-potential(q)+.5*np.dot(RADIAL,np.maximum(expected,0.)**2-np.maximum(tire,0.)**2)
    losses = result.suspension_damping_loss+result.tire_damping_loss+result.elastic_numerical_loss+result.kinetic_numerical_loss
    assert change_ke+change_pe+losses == pytest.approx(dt*result.velocity@gravity+np.dot(result.normal_force,road),abs=2e-11)
    # 直接展开四轮端力矩，与算法返回的冲量独立比较。
    wheel_force = result.normal_force[:,None]*NORMALS
    force_body = np.r_[np.sum(wheel_force,axis=0),sum(np.cross(r,f) for r,f in zip(mechanics.wheel_arms,wheel_force))]
    generalized = np.r_[force_body,np.sum(wheel_force*mechanics.guides,axis=1)-result.suspension_force]
    assert result.generalized_impulse == pytest.approx(dt*generalized,abs=3e-14)


def test_static_sprung_and_unsprung_loads_are_distinct_and_sum_to_total_weight():
    p = partition()
    # 各轮分配同一簧上支撑；参考布局不均匀质量造成CG纵向偏移很小但必须保留。
    q = np.full(4,p.mass*9.81/(4*24000.))
    target_suspension = np.full(4,p.mass*9.81/4)
    target_normal = target_suspension+np.array(MASSES)*9.81
    delta = target_normal/RADIAL
    # 将本试验的轮心配置调整到簧上CG正下方对称布局，排除额外俯仰静载分配。
    symmetric = replace(p,wheel_arms=((-0.84,1.1,-.1),(.84,1.1,-.1),(-.84,-1.1,-.1),(.84,-1.1,-.1)))
    mechanics = assemble_unsprung(symmetric,np.eye(3),q,GUIDES,np.zeros(10))
    result = normal_block(mechanics,np.zeros(10),q,delta,NORMALS,RADIAL,(0.,)*4,
                          mechanics.gravity_forces((0.,0.,-9.81)),(0.,)*4,1/240,CONFIG)
    assert result.velocity == pytest.approx(np.zeros(10),abs=5e-16)
    assert result.suspension_force == pytest.approx(target_suspension,abs=1e-12)
    assert result.normal_force == pytest.approx(target_normal,abs=1e-12)
    assert sum(result.normal_force) == pytest.approx(1200.*9.81,abs=1e-11)


def test_all_airborne_free_fall_does_not_pin_wheels_to_road():
    p = partition()
    mechanics = assemble_unsprung(p,np.eye(3),np.zeros(4),GUIDES,np.zeros(10))
    dt = 1/240
    result = normal_block(mechanics,np.zeros(10),np.zeros(4),(-.5,)*4,NORMALS,RADIAL,(600.,)*4,
                          mechanics.gravity_forces((0.,0.,-9.81)),(0.,)*4,dt,CONFIG)
    assert result.velocity == pytest.approx(np.r_[(0.,0.,-9.81*dt),np.zeros(7)],abs=1e-15)
    assert result.normal_force == pytest.approx(np.zeros(4),abs=0.)
