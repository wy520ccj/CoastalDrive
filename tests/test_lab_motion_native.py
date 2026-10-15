"""有限悬架与旋转小矩阵对原完整公式逐位核对，保留类型和布局。"""

from dataclasses import fields
from types import SimpleNamespace

import numpy as np
import pytest
from lab_motion_reference import FiniteSuspensionMotion as ReferenceMotion
from lab_motion_reference import rotation_increment as reference_rotation
from wheel_contact_kernels import finite_motion_vectors, rotation_increment_terms

from unsprung_motion import FiniteSuspensionMotion, _motion_vectors, rotation_increment


def assert_bits(actual,expected):
    assert actual.dtype == expected.dtype
    assert actual.shape == expected.shape
    assert actual.strides == expected.strides
    assert actual.tobytes() == expected.tobytes(),(actual,expected)


def arranged(values,order):
    if order in ('C','F'):return np.array(values,order=order)
    if order=='reverse':return np.array(values[:,::-1])[:,::-1]
    if order=='padded-F':
        storage = np.empty((8,3),dtype=values.dtype,order='F')
        storage[::2] = values
        return storage[::2]
    storage = np.empty((4,6),dtype=values.dtype)
    storage[:,::2] = values
    return storage[:,::2]


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
@pytest.mark.parametrize('scale',[0.,1e-150,1e-11,.03,1.,1e6])
@pytest.mark.parametrize('order',['C','strided','reverse'])
def test_rotation_keeps_original_trigonometry_rounding_and_matrix_layout(dtype,scale,order):
    rng = np.random.default_rng(167)
    for index in range(50):
        value = (rng.normal(size=3)*scale).astype(dtype)
        if index==0:value[:] = (-0.,0.,-0.)
        if order=='strided':
            storage = np.empty(6,dtype=dtype);storage[::2] = value;value = storage[::2]
        elif order=='reverse':value = value[::-1].copy()[::-1]
        assert_bits(rotation_increment(value),reference_rotation(value))


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
@pytest.mark.parametrize('order',['C','F','strided','padded-F','reverse'])
@pytest.mark.parametrize('jacobian_order',['C','F'])
def test_complete_finite_motion_keeps_all_fields_and_intermediate_matrix_rounding(dtype,order,jacobian_order):
    rng = np.random.default_rng(173)
    for index in range(50):
        position = (rng.normal(size=3)*(1e6 if index%3==0 else 1.)).astype(dtype)
        centers = arranged(position+rng.normal(size=(4,3)).astype(dtype),order)
        jacobian = np.array(rng.normal(size=(4,3,10)),dtype=dtype,order=jacobian_order)
        bias = arranged(rng.normal(size=(4,3)).astype(dtype)*.01,order)
        rotation = np.array(reference_rotation(rng.normal(size=3)*.1),order=jacobian_order)
        compression = (rng.normal(size=4)*.02).astype(dtype)
        velocity = rng.normal(size=32).astype(dtype)[::2]
        if index%10==0:velocity[:] = (0.,-0.)*8
        elif index%10==1:velocity[3:6] *= 1e-11
        mechanics = SimpleNamespace(wheel_jacobians=jacobian)
        args = position,rotation,centers,compression,mechanics,bias,(1/240,1e-6,.05)[index%3]
        current,old = FiniteSuspensionMotion(*args),ReferenceMotion(*args)
        for _ in range(2):
            actual,expected = current.evaluate(velocity),old.evaluate(velocity)
            for field in fields(actual):assert_bits(getattr(actual,field.name),getattr(expected,field.name))
            assert current.evaluate(velocity.copy()) is actual
            velocity[7] = np.nextafter(velocity[7],dtype(np.inf))


@pytest.mark.parametrize('order',['C','F','strided','padded-F','reverse'])
def test_motion_vectors_preserve_original_matrix_layout_and_ordinary_cross(order):
    rng = np.random.default_rng(179)
    for _ in range(100):
        centers = arranged(rng.normal(size=(4,3)),order)
        wheel = arranged(rng.normal(size=(4,3)),order)
        position,velocity = rng.normal(size=6)[::2],rng.normal(size=32)[::2]
        old_arms = centers-position
        change = .003*(wheel-velocity[:3])
        relative = wheel-velocity[:3]-np.cross(velocity[3:6],old_arms+change)
        for a,b in zip(_motion_vectors(position,centers,wheel,velocity,.003),(old_arms,change,relative)):
            assert_bits(a,b)


@pytest.mark.parametrize('kernel',[rotation_increment_terms,finite_motion_vectors])
def test_native_strided_outputs_preserve_storage_gaps(kernel):
    rng = np.random.default_rng(181)
    if kernel is rotation_increment_terms:
        inputs,shapes,constants = (rng.normal(size=6)[::2],),((9,3),),(.17,.03)
    else:
        inputs = (rng.normal(size=6)[::2],rng.normal(size=(4,6))[:,::2],rng.normal(size=(4,6))[:,::2],
                  rng.normal(size=12)[::2])
        shapes,constants = ((4,3),)*3,(.003,)
    for value in inputs:value.flags.writeable = False
    storage = tuple(np.full((rows,columns*2),71.) for rows,columns in shapes)
    outputs = tuple(array[:,::2] for array in storage)
    expected = tuple(np.empty(shape) for shape in shapes)
    kernel(inputs,outputs,*constants)
    kernel(inputs,expected,*constants)
    for array,a,b in zip(storage,outputs,expected):
        assert a.tobytes()==b.tobytes()
        assert np.all(array[:,1::2]==71.)


@pytest.mark.parametrize('kernel',[rotation_increment_terms,finite_motion_vectors])
@pytest.mark.parametrize('problem',['count','shape','dtype','readonly'])
def test_native_motion_buffer_errors_are_explicit(kernel,problem):
    inputs,outputs,constants = [np.zeros(3)],(np.empty((9,3)),),(0.,0.)
    if kernel is finite_motion_vectors:
        inputs = [np.zeros(3),np.zeros((4,3)),np.zeros((4,3)),np.zeros(6)]
        outputs,constants = (np.empty((4,3)),np.empty((4,3)),np.empty((4,3))),(.003,)
    if problem=='count':inputs.pop()
    elif problem=='shape':inputs[0] = np.zeros(2)
    elif problem=='dtype':inputs[0] = inputs[0].astype(np.float32)
    else:outputs[0].flags.writeable = False
    with pytest.raises((ValueError,BufferError)):
        kernel(tuple(inputs),outputs,*constants)
