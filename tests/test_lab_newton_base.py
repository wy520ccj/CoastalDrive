"""Newton基点复用不减差分，并对真实有限接触与完整原解逐位核对。"""

from dataclasses import fields

import numpy as np
import pytest
import test_unsprung_joint as case
from lab_newton_base_reference import solve_unsprung_joint as reference_solve
from test_finite_radial_contact import contact_case
from test_lab_crossover_diagnostics import DIAGNOSTIC
from test_lab_surface_cache import assert_geometry

from unsprung_contact_geometry import FiniteRadialContact
from unsprung_joint import solve_unsprung_joint
from vehicle_designs import REFERENCE_DESIGN


@pytest.mark.parametrize('gyro',[False,True])
@pytest.mark.parametrize('motion',[False,True])
@pytest.mark.parametrize('bias',[False,True])
def test_real_finite_contact_reuses_only_current_base_and_matches_all_original_fields(monkeypatch,gyro,motion,bias):
    world,ground,bump,context=contact_case()
    try:
        def run(solver):
            calls=[]
            namespace=solver.__globals__
            original=namespace['normal_material']
            def material(*args,**kwargs):calls.append(True);return original(*args,**kwargs)
            def selected(*args,**kwargs):
                hardware=args[0]
                kwargs['finite_contact']=FiniteRadialContact(context.roads,hardware,context.centers,np.eye(3),
                    hardware.axes,np.zeros((4,3)),np.zeros((4,3)),np.full(4,.003),args[-2],args[-1],lambda x,y:True,
                    wheel_velocity_bias=kwargs['wheel_velocity_bias'],finite_motion=kwargs['finite_motion'])
                return solver(*args,**kwargs,native_body_gyro=gyro)
            with monkeypatch.context() as scope:
                scope.setitem(namespace,'normal_material',material)
                scope.setattr(case,'solve_unsprung_joint',selected)
                result=case.solve(REFERENCE_DESIGN,speed=5.,finite_geometry=motion,
                    guide_bias=np.full((4,3),.0002) if bias else None)[0]
            return result,len(calls)
        expected,old_count=run(reference_solve)
        actual,new_count=run(solve_unsprung_joint)
        assert DIAGNOSTIC.digest(actual)==DIAGNOSTIC.digest(expected)
        assert new_count<=old_count-(actual.iterations-1)
        assert_geometry(actual.contact_geometry.geometry,expected.contact_geometry.geometry)
        for field in fields(actual.contact_geometry)[2:]:
            a,b=getattr(actual.contact_geometry,field.name),getattr(expected.contact_geometry,field.name)
            assert a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()
        again,_count=run(solve_unsprung_joint)
        assert DIAGNOSTIC.digest(again)==DIAGNOSTIC.digest(expected)
    finally:
        world.removeRigidBody(bump);world.removeRigidBody(ground)
