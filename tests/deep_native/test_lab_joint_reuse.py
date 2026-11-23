"""共同解反力前缀复用与动量核对完整旧公式逐位核对。"""

from dataclasses import replace

import numpy as np
import pytest
import test_unsprung_joint as case
from lab_joint_reference import solve_unsprung_joint as reference_solve
from test_lab_crossover_diagnostics import DIAGNOSTIC
from wheel_contact_kernels import unsprung_momentum_values

from unsprung_joint import solve_unsprung_joint
from vehicle_designs import REFERENCE_DESIGN

SCENARIOS = [({'front_drive_share':share},{'sync':sync,'airborne':air}) for share in (0.,.5,1.)
             for sync in (False,True) for air in (False,True)]
SCENARIOS += [({}, {'speed':-10.,'ratio':-3.2}),({}, {'road':(.0002,-.0001,.0003,0.)}),
              ({}, {'finite_geometry':True}),({}, {'old_down_offset':(3.,-2.,1.)}),
              ({}, {'guide_bias':np.full((4,3),.0002)}),({}, {'wheel_error':np.full((4,3),.0002)})]


@pytest.mark.parametrize('changes,arguments',SCENARIOS)
@pytest.mark.parametrize('gyro',[False,True])
def test_full_newton_joint_matches_old_numeric_bits_and_does_not_share_cache_between_solves(monkeypatch,changes,arguments,gyro):
    config = replace(REFERENCE_DESIGN,**changes)

    def run(solver):
        def selected(*args,**kwargs):
            options={} if solver is reference_solve else {'jacobian_updates':False}
            return solver(*args,**kwargs,native_body_gyro=gyro,**options)

        monkeypatch.setattr(case,'solve_unsprung_joint',selected)
        return case.solve(config,**arguments)[0]

    expected = DIAGNOSTIC.digest(run(reference_solve))
    assert DIAGNOSTIC.digest(run(solve_unsprung_joint))==expected
    assert DIAGNOSTIC.digest(run(solve_unsprung_joint))==expected


@pytest.mark.parametrize('scale',[0.,1e-150,1.,1e6])
@pytest.mark.parametrize('reverse',[False,True])
def test_momentum_kernel_keeps_old_ufunc_order_zero_sign_and_tail(scale,reverse):
    rng = np.random.default_rng(191)
    for index in range(100):
        inputs = tuple(rng.normal(size=n*2)[::2]*scale for n in (16,16,4,16,16))
        if index==0:
            for array in inputs:array[:] = (0.,-0.)*(len(array)//2)
        for array in inputs:array.flags.writeable = False
        before = [array.tobytes() for array in inputs]
        dt = (1/240,1e-6,.1)[index%3]
        expected_reaction = inputs[0]-inputs[1]
        expected_reaction[12:] -= inputs[2]
        expected_momentum = inputs[4]-dt*(expected_reaction-inputs[3])
        storage = (np.full(32,71.),np.full(68,71.))
        outputs = tuple(array[::-2] if reverse else array[::2] for array in storage)
        unsprung_momentum_values(inputs,outputs,dt)
        assert outputs[0].tobytes()==expected_reaction.tobytes()
        assert outputs[1][:16].tobytes()==expected_momentum.tobytes()
        assert np.all(outputs[1][16:]==71.)
        for array in storage:
            gaps = array[::2] if reverse else array[1::2]
            assert np.all(gaps==71.)
        assert [array.tobytes() for array in inputs]==before


@pytest.mark.parametrize('problem',['count','shape','dtype','readonly'])
def test_momentum_kernel_invalid_buffer_boundary(problem):
    inputs = [np.zeros(n) for n in (16,16,4,16,16)]
    outputs = (np.empty(16),np.empty(34))
    if problem=='count':inputs.pop()
    elif problem=='shape':inputs[0] = np.zeros(15)
    elif problem=='dtype':inputs[0] = inputs[0].astype(np.float32)
    else:outputs[1].flags.writeable = False
    with pytest.raises((ValueError,BufferError)):
        unsprung_momentum_values(tuple(inputs),outputs,1/240)
