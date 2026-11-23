"""普通叉积逐位保留NumPy语义；观测对完整旧路径字段/真实状态逐位核对。"""

import numpy as np
import pytest
from lab_observation_reference import observe_unsprung as old_observe
from lab_observation_reference import read_mechanics as old_read
from test_lab_crossover_diagnostics import DIAGNOSTIC
from test_lab_jacobian_hint import experiment
from wheel_contact_kernels import ordinary_cross_rows

import unsprung_body
import vehicle_unsprung as vehicle
from unsprung_dynamics import ordinary_cross


def bits(a,b):
    assert a.dtype==b.dtype and a.shape==b.shape and a.strides==b.strides
    assert a.tobytes()==b.tobytes(),(a,b)


def arranged(values,layout):
    if values.ndim==1:
        if layout=='negative':return values[::-1].copy()[::-1]
        if layout=='strided':
            storage=np.empty(6,dtype=values.dtype);storage[::2]=values;return storage[::2]
        return values.copy()
    if layout in ('C','F'):return np.array(values,order=layout)
    if layout=='negative':return values[:,::-1].copy()[:,::-1]
    storage=np.empty((len(values),6),dtype=values.dtype);storage[:,::2]=values;return storage[:,::2]


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
@pytest.mark.parametrize('layout',['C','F','strided','negative'])
@pytest.mark.parametrize('shape',['v-v','v-r','r-v','r-r','one-r'])
def test_cross_keeps_ordinary_products_zero_sign_types_broadcast_and_layout(dtype,layout,shape):
    rng=np.random.default_rng(239)
    for index in range(40):
        a=rng.normal(size=(4,3));b=rng.normal(size=(4,3))
        if shape in ('v-v','v-r'):a=a[0]
        if shape in ('v-v','r-v'):b=b[0]
        if shape=='one-r':a=a[:1]
        scale=(0.,1e-11,.01,1.,1e6)[index%5]
        a,b=arranged((a*scale).astype(dtype),layout),arranged((b*scale).astype(dtype),layout)
        if index==0:a[...] = -0.;b[...] = 0.
        a.flags.writeable=b.flags.writeable=False
        first,second=a.tobytes(),b.tobytes()
        bits(ordinary_cross(a,b),np.cross(a,b))
        assert a.tobytes()==first and b.tobytes()==second


@pytest.mark.parametrize('dtype',[np.int32,np.float32,np.float64])
def test_cross_mixed_scalar_types_and_empty_rows_keep_original_results(dtype):
    rng=np.random.default_rng(241)
    for count in (0,1,4,9):
        a=(rng.normal(size=(count,3))*10).astype(dtype)
        b=rng.normal(size=3)
        bits(ordinary_cross(a,b),np.cross(a,b))
        bits(ordinary_cross(b,a),np.cross(b,a))


@pytest.mark.parametrize('scale',[1e-150,1e150])
def test_cross_finite_extreme_magnitudes_match_original_bits(scale):
    rng=np.random.default_rng(251)
    for _ in range(100):
        a,b=rng.normal(size=(4,3))*scale,rng.normal(size=(4,3))*scale
        bits(ordinary_cross(a,b),np.cross(a,b))


@pytest.mark.parametrize('problem',['count','shape','dtype','readonly','broadcast','negative-count'])
def test_native_buffer_and_row_count_errors_are_explicit(problem):
    inputs=[np.ones((4,3)),np.ones((1,3))];outputs=(np.empty((4,3)),);counts=(4,1)
    if problem=='count':inputs.pop()
    elif problem=='shape':inputs[0]=np.ones((4,2))
    elif problem=='dtype':inputs[0]=inputs[0].astype(np.float32)
    elif problem=='readonly':outputs[0].flags.writeable=False
    elif problem=='broadcast':counts=(4,3)
    else:counts=(-1,1)
    with pytest.raises((ValueError,BufferError)):ordinary_cross_rows(tuple(inputs),outputs,*counts)


def test_native_strided_output_preserves_gaps():
    a=np.arange(24,dtype=float).reshape(4,6)[:,::2];b=np.array(((.3,-.2,.1),))
    storage=np.full((4,6),71.);output=storage[:,::2]
    ordinary_cross_rows((a,b),(output,),4,1)
    assert output.tobytes()==np.cross(a,b).tobytes()
    assert np.all(storage[:,1::2]==71.)


@pytest.mark.parametrize('tick_count',[0,1,4])
def test_actual_observer_keeps_all_outputs_but_does_not_rebuild_dynamics(monkeypatch,tick_count):
    run=experiment()
    try:
        for _ in range(tick_count):run.step()
        car=run.experiment.simulation.player
        angles=tuple(s.steering for s in car.tires.states[:2])
        raw=vehicle.read_kinematics(car)
        old=old_read(car,angles)
        for a,b in zip(raw,old[:8]):bits(a,b)
        states,contacts,observation=car.tires.states,car._wheel_contacts,car._unsprung_observation
        def forbidden(*args,**kwargs):raise AssertionError('完成步观测不应装配未使用的完整力学')
        with monkeypatch.context() as scope:
            scope.setattr(vehicle,'assemble_unsprung',forbidden)
            actual=vehicle.observe_unsprung(car,run.current.tick)
        actual_values=DIAGNOSTIC.digest((actual,car.tires.states,car._wheel_contacts))
        car.tires.states,car._wheel_contacts,car._unsprung_observation=states,contacts,observation
        with monkeypatch.context() as scope:
            scope.setattr(unsprung_body,'ordinary_cross',np.cross)
            expected=old_observe(car,run.current.tick)
        assert DIAGNOSTIC.digest((expected,car.tires.states,car._wheel_contacts))==actual_values
        for a,b in zip(raw,vehicle.read_kinematics(car)):bits(a,b)
    finally:run.close()
