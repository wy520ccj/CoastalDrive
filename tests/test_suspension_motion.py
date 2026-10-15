"""安装曲线的独立虚功/切线/耗散、常比极限与原始几何留出。"""

import copy
from dataclasses import asdict, replace

import numpy as np
import pytest
from suspension_motion_reference import constant_document, document, rejected_document
from test_unsprung_dynamics import GUIDES, partition

from suspension_bench import fit_bench, record_coverage, source_note, validate_metadata
from suspension_installation import installation_curve
from unsprung_contact import normal_block, normal_material, suspension_damping, suspension_potential
from unsprung_dynamics import assemble_unsprung
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document, grouped_parameters

BASE=replace(REFERENCE_DESIGN,unsprung_enabled=True,suspension_antiroll_rates=(0.,0.),suspension_stop_rates=(0.,)*4)


def config():
    return fit_bench(document(),BASE)[0]


def material(q,u,car):
    return normal_material(q,u,np.zeros(4),np.zeros(4),.01,car,np.zeros(4),np.zeros(4))


def test_linear_limit_including_explicit_endpoint_tangent_extrapolation():
    rows=tuple((q,.8*q,.75*q) for q in (-.2,0.,.2))
    spring,damper=installation_curve(rows)
    for q in (-.4,-.13,0.,.17,.4):
        assert spring.at(q)==pytest.approx((.8*q,.8,0.),abs=1e-14)
        assert damper.at(q)==pytest.approx((.75*q,.75,0.),abs=1e-14)
    car=replace(BASE,suspension_coil_enabled=True,suspension_spring_preloads=(960.,)*4)
    curved=replace(car,suspension_installation_curves=(rows,)*4)
    for q in (-.04,.03,.17):
        a,b=material(np.full(4,q),np.full(4,.2),car),material(np.full(4,q),np.full(4,.2),curved)
        assert a.suspension_potential==pytest.approx(b.suspension_potential,abs=1e-10)
        assert a.suspension_force==pytest.approx(b.suspension_force,abs=1e-10)
        assert a.suspension_tangent==pytest.approx(b.suspension_tangent,abs=1e-10)


def test_monotone_geometry_and_continuous_ratios_without_overshoot():
    car=config()
    axes=installation_curve(car.suspension_installation_curves[0])
    for axis in axes:
        for i in range(len(axis.q)-1):
            samples=[axis.at(q) for q in np.linspace(axis.q[i],axis.q[i+1],51)]
            assert all(axis.displacement[i]-1e-14<=value[0]<=axis.displacement[i+1]+1e-14 for value in samples)
            assert min(value[1] for value in samples)>=0.
        for q in axis.q[1:-1]:
            assert axis.at(q-1e-10)[1]==pytest.approx(axis.at(q+1e-10)[1],abs=1e-8)


def test_complete_force_is_energy_gradient_and_stiffness_contains_geometric_term():
    car=config()
    q=np.array((.021,.073,.122,.173))
    result=material(q,np.zeros(4),car)
    damping,_=suspension_damping(q,np.zeros(4),car)
    tangent=(result.suspension_tangent-np.diag(damping))/.01
    for i in range(4):
        perturb=np.eye(4)[i]*1e-7
        up,fp=suspension_potential(q+perturb,car)
        um,fm=suspension_potential(q-perturb,car)
        assert (up-um)/2e-7==pytest.approx(result.spring_force[i],rel=1e-8)
        assert (fp-fm)/2e-7==pytest.approx(tangent[:,i],rel=1e-8,abs=1e-5)
        axis=installation_curve(car.suspension_installation_curves[i])[0]
        ratio=axis.at(q[i])[1]/axis.reference_ratio
        omitted_geometry=car.suspension_spring_rates[i]*ratio**2
        assert tangent[i,i]-omitted_geometry>1000.
    # 用独立高阶积分核对实际轮心虚功，不靠求解器能量残差自证。
    nodes,weights=np.polynomial.legendre.leggauss(8)
    a,b=.021,.041
    force_integral=sum(w*suspension_potential(np.full(4,(a+b)/2+(b-a)/2*x),car)[1][0]
                       for x,w in zip(nodes,weights,strict=True))*(b-a)/2
    energy_change=(suspension_potential(np.full(4,b),car)[0]-suspension_potential(np.full(4,a),car)[0])/4
    assert force_integral==pytest.approx(energy_change,rel=1e-13)


@pytest.mark.parametrize("speed",(.23,-.23))
def test_damper_power_and_implicit_jacobian_include_motion_gradient(speed):
    car=config()
    q0=np.full(4,.031)
    u=np.full(4,speed)
    q=q0+.01*u
    result=material(q,u,car)
    for i in range(4):
        axis=installation_curve(car.suspension_installation_curves[i])[1]
        rd=axis.at(q[i])[1]
        c0=(car.suspension_compression_damping if speed>0 else car.suspension_extension_damping)[i]
        cd=c0/axis.reference_ratio**2
        assert result.suspension_force[i]-result.spring_force[i]==pytest.approx(cd*rd**2*speed,abs=1e-10)
        perturb=np.eye(4)[i]*1e-6
        plus=material(q0+.01*(u+perturb),u+perturb,car).suspension_force
        minus=material(q0+.01*(u-perturb),u-perturb,car).suspension_force
        assert (plus-minus)/2e-6==pytest.approx(result.suspension_tangent[:,i],rel=1e-8,abs=1e-5)
    assert result.suspension_damping==pytest.approx(.01*4*cd*(rd*speed)**2,rel=1e-13)


def test_nonlinear_normal_block_still_has_common_energy_ledger():
    car=config()
    q=np.array((.03,.04,.05,.06))
    v=np.r_[np.zeros(6),(.1,-.1,.2,-.2)]
    mechanics=assemble_unsprung(partition(),np.eye(3),q,GUIDES,v)
    step=normal_block(mechanics,v,q,np.full(4,.01),np.asarray(GUIDES),np.full(4,200000.),np.full(4,500.),
        mechanics.gravity_forces((0.,0.,-9.81)),np.zeros(4),1/240,car)
    assert step.energy_error==pytest.approx(0.,abs=1e-9)
    assert step.impulse_residual<1e-10 and step.suspension_damping_loss>=0.


def test_regressive_installation_can_have_negative_geometric_stiffness():
    rows=tuple((q,.8*q-1.2*q*q,.75*q) for q in (i/20 for i in range(-4,5)))
    car=replace(BASE,suspension_coil_enabled=True,suspension_spring_preloads=(40000.,)*4,
                suspension_installation_curves=(rows,)*4)
    q=np.full(4,.173)
    result=material(q,np.zeros(4),car)
    damping,_=suspension_damping(q,np.zeros(4),car)
    tangent=np.diag(result.suspension_tangent-np.diag(damping))/.01
    assert np.min(result.spring_force)>0.
    assert np.max(tangent)<0.


def test_geometry_holdout_is_required_and_cannot_change_fitted_component_data():
    good,report=fit_bench(document(),BASE)
    bad,rejected=fit_bench(rejected_document(),BASE)
    assert report["passed"] and not rejected["passed"]
    assert bad==good
    assert report["installation_validation"]["FL"]["max_position_error_m"][0]<.0002
    validate_metadata({"suspension_calibration":report})
    edited=copy.deepcopy(report)
    edited["parameters"]["suspension_installation_curves"][0][1][1]+=.001
    with pytest.raises(ValueError):validate_metadata({"suspension_calibration":edited})
    constant,_=fit_bench(constant_document(),BASE)
    assert constant.suspension_spring_rates==good.suspension_spring_rates
    assert constant.suspension_spring_preloads==good.suspension_spring_preloads
    legacy={"schema":"vehicle-engineering-v1","parameters":grouped_parameters(good)}
    del legacy["parameters"]["suspension"]["suspension_installation_curves"]
    assert config_from_document(legacy,good).suspension_installation_curves is None


def test_report_distinguishes_geometric_extrapolation_from_component_domain():
    car,report=fit_bench(document(),BASE)
    sample={**{f"travel_{wheel}":.22 for wheel in ("fl","fr","rl","rr")},
            **{f"travel_rate_{wheel}":.05 for wheel in ("fl","fr","rl","rr")}}
    result=record_coverage({"suspension_calibration":report},asdict(car),[sample])
    assert result["corners"]["FL"]["spring"]["installation_outside_samples"]==1
    assert result["corners"]["FL"]["compression"]["installation_outside_samples"]==1
    changed=asdict(car)
    changed["suspension_installation_curves"]=None
    assert "安装值已覆盖" in source_note({"suspension_calibration":report},"suspension_compression_damping",
        car.suspension_compression_damping,changed)
