"""由独立质点速度/受力展开核对簧下质量，不用同一算子生成期望。"""

import numpy as np
import pytest

from unsprung_dynamics import assemble_unsprung, partition_vehicle

MASSES = (38.,41.,40.,39.)
CENTERS = np.array(((-.84,1.1,-.10),(.84,1.1,-.10),(-.84,-1.1,-.10),(.84,-1.1,-.10)))
LOCKED = np.diag((1919.56,511.56,2290.))
GUIDES = ((0.,0.,1.),)*4


def partition():
    return partition_vehicle(1200.,LOCKED,MASSES,CENTERS)


def rotation():
    a,b = .31,-.27
    yaw = np.array(((np.cos(a),-np.sin(a),0.),(np.sin(a),np.cos(a),0.),(0.,0.,1.)))
    roll = np.array(((1.,0.,0.),(0.,np.cos(b),-np.sin(b)),(0.,np.sin(b),np.cos(b))))
    return yaw@roll


def test_mass_center_and_parallel_axis_reassemble_locked_vehicle():
    p = partition()
    center = np.asarray(p.center)
    assert p.mass+sum(p.wheel_masses) == 1200.
    assert p.mass*center+np.sum(np.array(MASSES)[:,None]*CENTERS,axis=0) == pytest.approx(np.zeros(3),abs=1e-14)
    # 对三个轴的转动逐个从分出的真实质量计算，含簧上CG的平行轴项。
    reconstructed = np.asarray(p.inertia).copy()
    for mass, r in [(p.mass,center),*zip(MASSES,CENTERS)]:
        for a in range(3):
            for b in range(3):
                reconstructed[a,b] += mass*((np.dot(r,r) if a==b else 0.)-r[a]*r[b])
    assert reconstructed == pytest.approx(LOCKED,abs=1e-12)


@pytest.mark.parametrize("inertia,masses", [(np.eye(3)*10.,MASSES), (np.diag((1000.,1000.,5000.)),MASSES),
                                           (LOCKED,(400.,)*4)])
def test_impossible_partition_is_rejected(inertia,masses):
    with pytest.raises(ValueError):
        partition_vehicle(1200.,inertia,masses,CENTERS)


def test_locked_energy_at_shifted_sprung_cg_equals_original_full_vehicle():
    p, r = partition(),rotation()
    ref_velocity, angular = np.array((.3,20.,-.1)),np.array((.4,-.2,.3))
    sprung_velocity = ref_velocity+np.cross(angular,r@p.center)
    velocity = np.r_[sprung_velocity,angular,np.zeros(4)]
    m = assemble_unsprung(p,r,np.zeros(4),GUIDES,velocity)
    expected = .5*1200.*np.dot(ref_velocity,ref_velocity)+.5*angular@(r@LOCKED@r.T)@angular
    assert m.kinetic_energy == pytest.approx(expected,abs=6e-11)
    assert np.linalg.eigvalsh(m.mass_matrix)[0] > 0.
    assert m.mass_matrix == pytest.approx(m.mass_matrix.T,abs=1e-12)


@pytest.mark.parametrize("displacement", [(0.,)*4,(.04,-.025,.02,-.03)])
def test_generalized_velocity_energy_and_virtual_force_power(displacement):
    p,r = partition(),rotation()
    velocity = np.array((.3,12.,-.2,.1,-.2,.4,.3,-.4,.2,.1))
    m = assemble_unsprung(p,r,displacement,GUIDES,velocity)
    arms = (np.asarray(p.wheel_arms)+np.array(displacement)[:,None]*np.array(GUIDES))@r.T
    actual_wheel_velocities = np.array([velocity[:3]+np.cross(velocity[3:6],arm)+r@guide*speed
                                      for arm,guide,speed in zip(arms,GUIDES,velocity[6:])])
    energy = .5*p.mass*np.dot(velocity[:3],velocity[:3])+.5*velocity[3:6]@(r@p.inertia@r.T)@velocity[3:6]
    energy += .5*np.sum(np.asarray(MASSES)[:,None]*actual_wheel_velocities**2)
    assert m.wheel_velocities == pytest.approx(actual_wheel_velocities,abs=1e-14)
    assert m.kinetic_energy == pytest.approx(energy,abs=2e-11)
    forces = np.array(((300.,40.,2700.),(-40.,50.,2900.),(20.,-30.,3100.),(-80.,20.,2800.)))
    assert velocity@m.wheel_forces(forces) == pytest.approx(np.sum(forces*actual_wheel_velocities),abs=1e-11)
    axial = np.array((500.,600.,700.,800.))
    internal = m.suspension_forces(axial)
    assert internal[:6] == pytest.approx(np.zeros(6),abs=1e-12)
    assert velocity@internal == pytest.approx(axial@velocity[6:],abs=1e-12)


def test_centrifugal_and_coriolis_terms_close_energy_and_momentum():
    p,r = partition(),rotation()
    velocity = np.array((.3,12.,-.2,.1,-.2,.4,.3,-.4,.2,.1))
    m = assemble_unsprung(p,r,(.04,-.025,.02,-.03),GUIDES,velocity)
    forces = np.array(((300.,40.,2700.),(-40.,50.,2900.),(20.,-30.,3100.),(-80.,20.,2800.)))
    axial = np.array((500.,600.,700.,800.))
    q = m.wheel_forces(forces)+m.suspension_forces(axial)
    acceleration = m.acceleration(q)
    assert velocity@(m.mass_matrix@acceleration)+.5*velocity@m.mass_derivative@velocity == pytest.approx(velocity@q,abs=1e-10)
    wheel_accelerations = []
    for i,arm in enumerate(m.wheel_arms):
        guide = m.guides[i]
        result = (acceleration[:3]+np.cross(acceleration[3:6],arm)+guide*acceleration[6+i]
                  +np.cross(velocity[3:6],np.cross(velocity[3:6],arm))
                  +2*np.cross(velocity[3:6],guide)*velocity[6+i])
        wheel_accelerations.append(result)
        # 理想导向约束反力垂直于可动方向；不能靠悬架补出轮端外力。
        reaction = MASSES[i]*result-forces[i]-axial[i]*guide
        assert np.dot(reaction,guide) == pytest.approx(0.,abs=1e-11)
    momentum_rate = p.mass*acceleration[:3]+np.sum(np.asarray(MASSES)[:,None]*wheel_accelerations,axis=0)
    angular_rate = m.world_inertia@acceleration[3:6]+np.cross(velocity[3:6],m.world_inertia@velocity[3:6])
    angular_rate += sum(np.cross(arm,mass*a) for arm,mass,a in zip(m.wheel_arms,MASSES,wheel_accelerations))
    assert momentum_rate == pytest.approx(np.sum(forces,axis=0),abs=1e-11)
    assert angular_rate == pytest.approx(sum(np.cross(arm,f) for arm,f in zip(m.wheel_arms,forces)),abs=1e-11)


def test_free_fall_and_single_wheel_relative_force_have_real_cross_coupling():
    p = partition()
    m = assemble_unsprung(p,np.eye(3),(.02,-.01,.03,-.015),GUIDES,np.zeros(10))
    acceleration = m.acceleration(m.gravity_forces((0.,0.,-9.81)))
    assert acceleration == pytest.approx(np.r_[(0.,0.,-9.81),np.zeros(7)],abs=2e-14)
    force = np.zeros(10)
    force[6] = 100.
    acceleration = m.acceleration(force)
    assert abs(acceleration[2])>.001 and abs(acceleration[3])>.001 and abs(acceleration[4])>.001
    assert all(abs(acceleration[i])>.001 for i in (7,8,9))


def test_mass_derivative_matches_independent_pose_and_stroke_difference():
    p,r = partition(),rotation()
    velocity = np.array((.3,12.,-.2,.1,-.2,.4,.3,-.4,.2,.1))
    displacement = np.array((.04,-.025,.02,-.03))
    epsilon = 1e-3
    w = velocity[3:6]
    norm = np.linalg.norm(w)
    axis = w/norm
    skew = np.array(((0.,-axis[2],axis[1]),(axis[2],0.,-axis[0]),(-axis[1],axis[0],0.)))
    def moved(dt):
        angle = norm*dt
        rotation_step = np.eye(3)+np.sin(angle)*skew+(1-np.cos(angle))*(skew@skew)
        return assemble_unsprung(p,rotation_step@r,displacement+dt*velocity[6:],GUIDES,velocity).mass_matrix
    # 五点差分降低姿态截断误差，较大间隔避免2000kg·m²相减的舍入占主导。
    difference = (-moved(2*epsilon)+8*moved(epsilon)-8*moved(-epsilon)+moved(-2*epsilon))/(12*epsilon)
    m = assemble_unsprung(p,r,displacement,GUIDES,velocity)
    assert m.mass_derivative == pytest.approx(difference,abs=3e-7)
