"""同子步准备结果只在完整相同输入复用，可变数组与后续真实几何保持独立。"""

from dataclasses import replace

import numpy as np
import pytest
from lab_initial_geometry_reference import FiniteRadialContact as OriginalContact
from physics.unsprung_step_checkpoint import numeric_geometry
from test_finite_radial_contact import contact_case
from test_lab_crossover_diagnostics import DIAGNOSTIC
from test_lab_surface_cache import assert_geometry, layout

from unsprung_contact_geometry import FiniteRadialContact


def arrays(geometry):
    return (geometry.deflection,geometry.offsets,geometry.normals,geometry.tangents,geometry.laterals,geometry.normal_offsets)


def arguments(context,old_axes):
    return (context.roads,context.hardware,context.centers,context.rotation,old_axes,context.deformation,
            context.steering,context.trails,context.dt,context.config,context.on_asphalt,
            context.wheel_velocity_bias,context.finite_motion)


@pytest.mark.parametrize('variant',['same','turn','F','strided','reverse','negative-zero','ulp','unprepared'])
def test_prepared_geometry_matches_complete_old_constructor_and_all_moving_queries(monkeypatch,variant):
    world,ground,bump,context=contact_case()
    try:
        axes=context.hardware.axes.copy()
        if variant=='turn':axes[0]=(np.cos(.01),np.sin(.01),0.)
        elif variant in ('F','strided','reverse'):axes=layout(axes,variant)
        elif variant=='negative-zero':axes[0,1]=-0.
        elif variant=='ulp':axes[0,1]=np.nextafter(0.,1.)
        args=arguments(context,axes)
        seed=context.roads.query(context.centers,context.rotation[:,2],context.hardware.axes)
        original=FiniteRadialContact.__new__(FiniteRadialContact)
        OriginalContact.__init__(original,*args)
        calls=[];query=context.roads.query
        def traced(*values,**kwargs):calls.append(values);return query(*values,**kwargs)
        with monkeypatch.context() as scope:
            scope.setattr(context.roads,'query',traced)
            current=FiniteRadialContact(*args,target_geometry=None if variant=='unprepared' else seed)
        assert len(calls)==(0 if variant=='same' else 2 if variant=='unprepared' else 1)
        assert_geometry(current.initial,original.initial);assert_geometry(current.target,original.target)
        assert 'target_geometry' not in current.__dict__
        assert set(current.__dict__)-{'query_cache'}==set(original.__dict__)-{'query_cache'}
        for initial,target,prepared in zip(arrays(current.initial),arrays(current.target),arrays(seed)):
            assert not np.shares_memory(initial,target)
            assert not np.shares_memory(initial,prepared) and not np.shares_memory(target,prepared)
        for value in arrays(seed):value[:]=71.
        assert_geometry(current.initial,original.initial);assert_geometry(current.target,original.target)
        for velocity in (np.zeros(16),np.array((0.,5.,0.,.1,-.2,.3,*([0.]*10))),
                         np.array((0.,0.,1e-11,0.,0.,0.,*([0.]*10)))):
            actual,expected=current.evaluate(velocity),original.evaluate(velocity)
            assert_geometry(actual.geometry,expected.geometry)
            assert DIAGNOSTIC.digest(replace(actual,geometry=numeric_geometry(actual.geometry)))==DIAGNOSTIC.digest(
                replace(expected,geometry=numeric_geometry(expected.geometry)))
    finally:world.removeRigidBody(bump);world.removeRigidBody(ground)


@pytest.mark.parametrize('invalid',['dtype','shape'])
def test_changed_axis_contract_keeps_original_query_error(monkeypatch,invalid):
    world,ground,bump,context=contact_case()
    try:
        seed=context.roads.query(context.centers,context.rotation[:,2],context.hardware.axes)
        axes=context.hardware.axes.astype(np.float32) if invalid=='dtype' else context.hardware.axes[:3]
        args=arguments(context,axes);failures=[];query=context.roads.query;calls=[]
        def traced(*values,**kwargs):calls.append(values);return query(*values,**kwargs)
        with monkeypatch.context() as scope:
            scope.setattr(context.roads,'query',traced)
            for prepared in (False,True):
                before=len(calls)
                with pytest.raises(ValueError) as error:
                    if prepared:FiniteRadialContact(*args,target_geometry=seed)
                    else:OriginalContact.__init__(FiniteRadialContact.__new__(FiniteRadialContact),*args)
                assert len(calls)==before+1;failures.append(str(error.value))
        assert failures[0]==failures[1]
    finally:world.removeRigidBody(bump);world.removeRigidBody(ground)
