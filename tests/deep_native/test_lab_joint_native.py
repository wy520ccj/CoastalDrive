"""四轮材料与全部有限端口对旧公式逐位核对，保留模式和未写残差。"""

import math
import pickle

import numpy as np
import pytest
from lab_joint_residual_reference import contact_reference, port_reference
from mechanical_kernels import unsprung_contact_residual, unsprung_port_residual

from vehicle_designs import REFERENCE_DESIGN


def assert_bits(actual, expected):
    assert actual.dtype == expected.dtype
    assert actual.shape == expected.shape
    assert actual.tobytes() == expected.tobytes()


@pytest.mark.parametrize("scale", [0.,1e-11,1.,100.])
@pytest.mark.parametrize("dt", [1/120,1/240,1/960])
def test_batched_contact_keeps_original_material_modes_details_and_residuals(scale, dt):
    rng = np.random.default_rng(47)
    car = REFERENCE_DESIGN
    constants = (dt,car.tire_contact_stiffness,car.tire_contact_damping,car.tire_shape,car.tire_curvature,car.slip_speed)
    modes = set()
    for index in range(100):
        end = rng.normal(size=32)[::2]*scale
        forces = rng.normal(size=(4,4))[:,::2]*2000*scale
        previous = rng.normal(size=(4,4))[:,::2]*.001*scale
        speeds = rng.normal(size=(4,6))[:,::2]*scale
        radii = np.full(8,.33)[::2]
        rolling = np.array((index%2,0.,1.,0.,1.,0.,0.,0.))[::2]
        parameters = np.empty((4,6))[:,::2]
        parameters[:,0] = (0.,4000.,4000.,4000.)
        parameters[:,1:] = (80000.,90000.)
        if index%2 == 0:
            previous[3] = (0.,0.)
            speeds[3] = (0.,0.,0.)
        inputs = (end,forces,previous,speeds,radii,rolling,parameters)
        actual,expected = np.full(68,71.)[::2],np.full(34,71.)
        old = contact_reference(inputs,expected,*constants)
        new = unsprung_contact_residual(inputs,actual,*constants,math.hypot)
        assert_bits(actual,expected)
        assert pickle.dumps(new,protocol=5) == pickle.dumps(old,protocol=5)
        modes.update(result[-1] for result in new)
    assert "compliant-rolling" in modes and "compliant-sticking" in modes
    if scale >= 1.:
        assert "compliant-sliding" in modes


@pytest.mark.parametrize("ratio", [-3.2,0.,3.2])
@pytest.mark.parametrize("sync", [False,True])
@pytest.mark.parametrize("share", [0.,.5,1.])
def test_all_finite_port_branches_keep_order_boundaries_and_strided_arrays(ratio, sync, share):
    rng = np.random.default_rng(83)
    for index in range(100):
        torques = rng.normal(size=20)[::2]*1000
        speeds = rng.normal(size=20)[::2]*20
        response = rng.uniform(.01,2.,size=20)[::2]
        inertial = rng.normal(size=6)[::2]*100
        brakes = rng.uniform(0.,500.,size=8)[::2]
        maximum = np.array((100.,0.,200.,0.,300.,0.))[::2]
        biases = np.array((1.,0.,3.,0.))[::2]
        damping = np.array((.3,0.,2.,0.,.5,0.))[::2]
        if index%3 == 0:
            torques *= 0.
            speeds *= 0.
            brakes *= 0.
            maximum *= 0.
        elif index%3 == 1:
            biases[:] = (2.,1.)
        settings = (1/240,ratio,sync,share,3.9,.97,100.,80.)
        drive = ratio*(torques[1]-torques[2])
        inputs = (torques,speeds,response,inertial,brakes,maximum,biases,damping)
        actual,expected = np.full(68,71.)[::2],np.full(34,71.)
        port_reference(inputs,expected,settings,drive)
        unsprung_port_residual(inputs,actual,settings,drive)
        assert_bits(actual,expected)


@pytest.mark.parametrize("fails", [False,True])
def test_batch_keeps_original_hypot_callback_and_exception_boundary(monkeypatch, fails):
    original = math.hypot
    calls = []

    def hypot(x,y):
        calls.append((x.hex(),y.hex()))
        if fails and len(calls)==2:
            raise RuntimeError("测试材料范数边界")
        return original(x,y)

    monkeypatch.setattr(math,"hypot",hypot)
    inputs = (np.zeros(16),np.zeros((4,2)),np.zeros((4,2)),np.full((4,3),.2),
              np.full(4,.33),np.ones(4),np.tile((4000.,80000.,90000.),(4,1)))
    constants = (1/240,100000.,1000.,1.3,.9,.5)
    actual,expected = np.full(34,71.),np.full(34,71.)
    if fails:
        with pytest.raises(RuntimeError,match="测试材料范数边界"):
            contact_reference(inputs,expected,*constants)
    else:
        old = contact_reference(inputs,expected,*constants)
    old_calls = calls.copy()
    calls.clear()
    if fails:
        with pytest.raises(RuntimeError,match="测试材料范数边界"):
            unsprung_contact_residual(inputs,actual,*constants,math.hypot)
    else:
        new = unsprung_contact_residual(inputs,actual,*constants,math.hypot)
        assert pickle.dumps(new,protocol=5) == pickle.dumps(old,protocol=5)
    assert calls == old_calls
    assert_bits(actual,expected)


@pytest.mark.parametrize("kernel", ["contact","ports"])
@pytest.mark.parametrize("problem", ["count","shape","dtype","readonly"])
def test_native_residual_array_boundary_reports_errors(kernel, problem):
    output = np.empty(34)
    if kernel == "contact":
        inputs = [np.zeros(16),np.zeros((4,2)),np.zeros((4,2)),np.zeros((4,3)),np.ones(4),np.ones(4),np.ones((4,3))]
    else:
        inputs = [np.zeros(10),np.zeros(10),np.ones(10),np.zeros(3),np.ones(4),np.ones(3),np.ones(2),np.ones(3)]
    if problem == "count":
        inputs.pop()
    elif problem == "shape":
        inputs[0] = np.zeros(15)
    elif problem == "dtype":
        inputs[0] = inputs[0].astype(np.float32)
    else:
        output.flags.writeable = False
    with pytest.raises((ValueError,BufferError)):
        if kernel == "contact":
            unsprung_contact_residual(tuple(inputs),output,1/240,100000.,1000.,1.3,.9,.5,math.hypot)
        else:
            unsprung_port_residual(tuple(inputs),output,(1/240,3.2,False,.5,3.9,.97,100.,80.),0.)
