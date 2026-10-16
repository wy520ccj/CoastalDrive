"""默认Jacobian更新始终满足冻结原物理方程与能量账，完整Newton可精确参照。"""

from dataclasses import replace

import numpy as np
import pytest
import test_unsprung_joint as case
from lab_newton_base_reference import solve_unsprung_joint as old_solve
from lab_solver_validation import model_for, verify_result
from test_finite_radial_contact import contact_case
from test_lab_crossover_diagnostics import DIAGNOSTIC
from test_lab_joint_reuse import SCENARIOS

from unsprung_contact_geometry import FiniteRadialContact
from unsprung_joint import solve_unsprung_joint
from vehicle_designs import REFERENCE_DESIGN


@pytest.mark.parametrize('changes,arguments',SCENARIOS)
@pytest.mark.parametrize('gyro',[False,True])
def test_default_updated_solver_satisfies_independent_original_model_and_ledger(monkeypatch,changes,arguments,gyro):
    checked=[]
    def solve(*args,**kwargs):
        kwargs['native_body_gyro']=gyro
        model=model_for(args,kwargs)
        result=solve_unsprung_joint(*args,**kwargs)
        checked.append(verify_result(model,result))
        return result
    monkeypatch.setattr(case,'solve_unsprung_joint',solve)
    first=case.solve(replace(REFERENCE_DESIGN,**changes),**arguments)[0]
    second=case.solve(replace(REFERENCE_DESIGN,**changes),**arguments)[0]
    assert len(checked)==2
    assert DIAGNOSTIC.digest(first)==DIAGNOSTIC.digest(second)


@pytest.mark.parametrize('gyro',[False,True])
@pytest.mark.parametrize('motion',[False,True])
@pytest.mark.parametrize('bias',[False,True])
def test_default_updated_solver_uses_real_finite_geometry_in_independent_model(monkeypatch,gyro,motion,bias):
    world,ground,bump,context=contact_case()
    try:
        checked=[]
        def selected(*args,**kwargs):
            hardware=args[0]
            kwargs['finite_contact']=FiniteRadialContact(context.roads,hardware,context.centers,np.eye(3),
                hardware.axes,np.zeros((4,3)),np.zeros((4,3)),np.full(4,.003),args[-2],args[-1],lambda x,y:True,
                wheel_velocity_bias=kwargs['wheel_velocity_bias'],finite_motion=kwargs['finite_motion'])
            kwargs['native_body_gyro']=gyro
            model=model_for(args,kwargs)
            result=solve_unsprung_joint(*args,**kwargs)
            checked.append(verify_result(model,result))
            return result
        monkeypatch.setattr(case,'solve_unsprung_joint',selected)
        result=case.solve(REFERENCE_DESIGN,speed=5.,finite_geometry=motion,
            guide_bias=np.full((4,3),.0002) if bias else None)[0]
        assert checked and result.contact_geometry is not None
    finally:
        world.removeRigidBody(bump);world.removeRigidBody(ground)


@pytest.mark.parametrize('changes,arguments',SCENARIOS)
def test_explicit_full_newton_preserves_complete_legacy_numeric_result(monkeypatch,changes,arguments):
    config=replace(REFERENCE_DESIGN,**changes)
    monkeypatch.setattr(case,'solve_unsprung_joint',old_solve)
    old=case.solve(config,**arguments)[0]
    def full(*args,**kwargs):return solve_unsprung_joint(*args,**kwargs,jacobian_updates=False)
    monkeypatch.setattr(case,'solve_unsprung_joint',full)
    new=case.solve(config,**arguments)[0]
    assert DIAGNOSTIC.digest(old)==DIAGNOSTIC.digest(new)


@pytest.mark.parametrize('failure',['singular','uphill'])
def test_stale_jacobian_is_rebuilt_when_its_direction_cannot_be_used(monkeypatch,failure):
    original=np.linalg.solve
    calls=[];residuals=[]
    namespace=solve_unsprung_joint.__globals__
    material=namespace['unsprung_contact_residual']
    def counted(*args,**kwargs):residuals.append(True);return material(*args,**kwargs)
    def injected(matrix,right):
        if matrix.shape==(34,34):
            calls.append(True)
            if len(calls)==2:
                if failure=='singular':raise np.linalg.LinAlgError('测试旧Jacobian退化')
                return -original(matrix,right)
        return original(matrix,right)
    checked=[]
    def selected(*args,**kwargs):
        model=model_for(args,kwargs)
        result=solve_unsprung_joint(*args,**kwargs)
        checked.append(verify_result(model,result))
        return result
    monkeypatch.setattr(np.linalg,'solve',injected)
    monkeypatch.setitem(namespace,'unsprung_contact_residual',counted)
    monkeypatch.setattr(case,'solve_unsprung_joint',selected)
    result=case.solve(REFERENCE_DESIGN)[0]
    assert checked and len(calls)>3 and result.iterations<30
    assert len(residuals)>=2*68


def test_singular_fresh_jacobian_propagates_original_failure(monkeypatch):
    original=np.linalg.solve
    def injected(matrix,right):
        if matrix.shape==(34,34):raise np.linalg.LinAlgError('测试完整Jacobian退化')
        return original(matrix,right)
    monkeypatch.setattr(np.linalg,'solve',injected)
    with pytest.raises(np.linalg.LinAlgError,match='测试完整Jacobian退化'):
        case.solve(REFERENCE_DESIGN)
