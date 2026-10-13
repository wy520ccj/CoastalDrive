"""完整四轮小扰动质量阵的共同升沉模态对独立两质量特征方程。"""

from dataclasses import replace

import numpy as np
import pytest
from test_unsprung_dynamics import CENTERS, GUIDES, LOCKED

from suspension import stiffness_matrix
from unsprung_contact import normal_block
from unsprung_dynamics import assemble_unsprung, partition_vehicle
from vehicle_config import CAR


@pytest.mark.parametrize("wheel_mass", [25.,40.,65.])
def test_body_bounce_and_wheel_hop_match_two_mass_equation(wheel_mass):
    partition = partition_vehicle(1200.,LOCKED,(wheel_mass,)*4,CENTERS)
    mechanics = assemble_unsprung(partition,np.eye(3),np.zeros(4),GUIDES,np.zeros(10))
    spring, tire = 24000.,200000.
    # 投影到簧上升沉与四轮共同绝对升沉；相对行程q=zu-zs。
    subspace = np.zeros((10,2))
    subspace[2,0] = 1.
    subspace[6:,0],subspace[6:,1] = -1.,1.
    gradient_s = np.zeros((4,10))
    gradient_s[:,6:] = np.eye(4)
    gradient_t = mechanics.wheel_jacobians[:,2,:]
    stiffness = spring*gradient_s.T@gradient_s+tire*gradient_t.T@gradient_t
    mass_reduced = subspace.T@mechanics.mass_matrix@subspace
    stiffness_reduced = subspace.T@stiffness@subspace
    assert mass_reduced == pytest.approx(np.diag((1200.-4*wheel_mass,4*wheel_mass)),abs=1e-12)
    squared = np.sort(np.linalg.eigvals(np.linalg.solve(mass_reduced,stiffness_reduced)))
    # 单角的m_sω^4m_u-[ks*m_u+(ks+kt)*m_s]ω²+ks*kt=0。
    sprung = (1200.-4*wheel_mass)/4
    b = spring/sprung+(spring+tire)/wheel_mass
    c = spring*tire/(sprung*wheel_mass)
    expected = np.array(((b-np.sqrt(b*b-4*c))/2,(b+np.sqrt(b*b-4*c))/2))
    assert squared == pytest.approx(expected,rel=1e-13)
    assert np.sqrt(squared[1])>5*np.sqrt(squared[0])


def test_normal_step_is_full_vehicle_matrix_not_four_independent_corner_filters():
    p = partition_vehicle(1200.,LOCKED,(40.,)*4,CENTERS)
    config = replace(CAR,suspension_spring_rates=(24000.,)*4,
                     suspension_compression_damping=(1800.,)*4,
                     suspension_extension_damping=(1800.,)*4,
                     suspension_antiroll_rates=(6000.,5000.),suspension_stop_rates=(0.,)*4)
    m = assemble_unsprung(p,np.eye(3),np.zeros(4),GUIDES,np.zeros(10))
    dt, displacement = 1/240,np.array((.0001,0.,0.,0.))
    rates = np.array((200000.,)*4)
    step = normal_block(m,np.zeros(10),np.zeros(4),np.zeros(4),np.array(GUIDES),rates,np.zeros(4),
                        np.zeros(10),displacement,dt,config)
    # 与显式完整块矩阵直接解对照，路面移动后四轮都进入正压缩。
    js,jn = np.zeros((4,10)),m.wheel_jacobians[:,2,:]
    js[:,6:] = np.eye(4)
    ks = np.asarray(stiffness_matrix(config.suspension_spring_rates,config.suspension_antiroll_rates))
    active = step.tire_deflection>0.
    kt = np.diag(np.where(active,rates,0.))
    system = m.mass_matrix+dt*js.T@(dt*ks+1800.*np.eye(4))@js+dt*dt*jn.T@kt@jn
    expected = np.linalg.solve(system,dt*jn.T@kt@displacement)
    assert step.velocity == pytest.approx(expected,abs=1e-15)
    assert np.linalg.norm(step.velocity[3:5])>1e-7
    assert np.linalg.norm(step.velocity[7:])>1e-7
