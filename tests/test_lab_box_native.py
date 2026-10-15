"""Box锥端点、52轮细化及完整全局证明对旧公式逐位核对。"""

from dataclasses import replace
from itertools import product

import numpy as np
import pytest
from lab_box_reference import box_section_reference, wheel_support
from wheel_contact_kernels import box_cone_refine, box_cone_samples

from box_radial_geometry import box_section
from vehicle_designs import REFERENCE_DESIGN


def assert_bits(actual, expected):
    assert actual.dtype == expected.dtype
    assert actual.shape == expected.shape
    assert actual.tobytes() == expected.tobytes()


def cone_reference(center,axis,basis,edge,angle,config):
    normal = np.cos(angle)*basis[0]+np.sin(angle)*basis[1]
    tangent = -np.sin(angle)*basis[0]+np.cos(angle)*basis[1]
    wheel = center+wheel_support(normal,axis,config)
    return normal,wheel,np.array((float(np.dot(normal,wheel-edge)),float(np.dot(tangent,wheel-edge))))


@pytest.mark.parametrize("free", [0,1,2])
@pytest.mark.parametrize("signs", list(product((-1.,1.),repeat=2)))
def test_cone_values_and_full_refinement_keep_bits_and_all_original_angles(free, signs):
    rng = np.random.default_rng(107)
    fixed = [i for i in range(3) if i!=free]
    config = REFERENCE_DESIGN
    constants = config.wheel_radius,config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height,np.pi/2
    for index in range(10):
        center = rng.normal(size=6)[::2]*(0. if index==0 else 10**rng.uniform(-11,3))
        axis = rng.normal(size=6)[::2]
        axis /= np.linalg.norm(axis)
        basis = np.zeros((2,6))[:,::2]
        basis[:] = np.eye(3)[fixed]*np.asarray(signs)[:,None]
        edge = np.zeros(6)[::2]
        edge[fixed] = np.asarray(signs)*(.45,.005)
        outputs = (np.full((3,6),71.)[:,::2],np.full((3,6),71.)[:,::2],np.full((3,4),71.)[:,::2])
        expected = [np.full(array.shape,71.) for array in outputs]
        angles = []

        def evaluate(angle,angles=angles,center=center,axis=axis,basis=basis,edge=edge):
            angles.append(angle.hex())
            return cone_reference(center,axis,basis,edge,angle,config)

        for row,angle in enumerate((0.,np.pi/2)):
            for array,value in zip(expected,evaluate(angle)):
                array[row] = value
        lo,hi = 0.,np.pi/2
        for _ in range(52):
            middle = (lo+hi)/2
            if evaluate(middle)[2][1]>0.:lo=middle
            else:hi=middle
        for array,value in zip(expected,evaluate((lo+hi)/2)):
            array[2] = value
        cosine_angles,sine_angles = [],[]

        def cosine(angle,records=cosine_angles):
            records.append(angle.hex())
            return np.cos(angle)

        def sine(angle,records=sine_angles):
            records.append(angle.hex())
            return np.sin(angle)

        inputs = center,axis,basis,edge
        box_cone_samples(inputs,outputs,*constants,cosine,sine)
        box_cone_refine(inputs,outputs,*constants,cosine,sine)
        assert len(angles) == 55
        assert cosine_angles == sine_angles == angles
        for a,b in zip(outputs,expected):
            assert_bits(a,b)


@pytest.mark.parametrize("free", [0,1,2])
@pytest.mark.parametrize("dtype", [np.float32,np.float64])
def test_complete_box_proof_keeps_original_result_or_refusal(free, dtype):
    rng = np.random.default_rng(113)
    fixed = [i for i in range(3) if i!=free]
    for index in range(100):
        config = replace(REFERENCE_DESIGN,wheel_crown_height=(0.,.003,.006)[index%3])
        center = np.zeros(6,dtype=dtype)[::2]
        center[free],center[fixed[0]],center[fixed[1]] = rng.uniform(-.02,.02),rng.uniform(-.7,.7),rng.uniform(.25,.4)
        axis = rng.normal(size=6).astype(dtype)[::2]*.1
        axis[free] = 1.
        half = np.zeros(3)
        half[free],half[fixed[0]],half[fixed[1]] = .24,.45,.005
        actual,expected = box_section(center,axis,half,config),box_section_reference(center,axis,half,config)
        if expected is None:
            assert actual is None
        else:
            assert actual[0].hex() == expected[0].hex()
            for a,b in zip(actual[1:4],expected[1:4]):
                assert_bits(a,b)
            assert actual[4] == expected[4]


@pytest.mark.parametrize("kernel", [box_cone_samples,box_cone_refine])
@pytest.mark.parametrize("problem", ["count","shape","dtype","readonly","callback"])
def test_native_box_reports_input_and_trigonometric_boundary_errors(kernel, problem):
    inputs = [np.zeros(3),np.array((1.,0.,0.)),np.eye(3)[1:],np.zeros(3)]
    outputs = (np.empty((3,3)),np.empty((3,3)),np.empty((3,2)))
    cosine,sine = np.cos,np.sin
    if problem == "count":
        inputs.pop()
    elif problem == "shape":
        inputs[0] = np.zeros(2)
    elif problem == "dtype":
        inputs[0] = np.zeros(3,dtype=np.float32)
    elif problem == "readonly":
        outputs[0].flags.writeable = False
    else:
        def cosine(angle):
            raise RuntimeError("测试三角函数边界")
    error = RuntimeError if problem == "callback" else (ValueError,BufferError)
    with pytest.raises(error):
        kernel(tuple(inputs),outputs,.33,.11,.01,.003,np.pi/2,cosine,sine)
