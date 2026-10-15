"""真实六向支持和原包围盒gap逐位核对，覆盖筛选阈值两侧。"""

from dataclasses import replace
from itertools import product

import numpy as np
import pytest
from lab_radial_reference import surface_reference
from wheel_contact_kernels import box_axis_supports, radial_box_bounds

from box_radial_geometry import wheel_support
from radial_geometry import RadialSurface
from vehicle_designs import REFERENCE_DESIGN


def assert_bits(actual, expected):
    assert actual.dtype == expected.dtype
    assert actual.shape == expected.shape
    assert actual.tobytes() == expected.tobytes()


def bounds_reference(center, axis, half, config):
    minimum = np.asarray([center[j]+wheel_support(np.eye(3)[j],axis,config)[j] for j in range(3)])
    maximum = np.asarray([center[j]+wheel_support(-np.eye(3)[j],axis,config)[j] for j in range(3)])
    return np.maximum(np.maximum(minimum-half,-half-maximum),0.)


@pytest.mark.parametrize("scale", [0.,1e-11,1.,1e6])
@pytest.mark.parametrize("crown", [0.,.003,.006])
def test_six_axis_supports_and_bounds_match_original_bits(scale, crown):
    rng = np.random.default_rng(127)
    config = replace(REFERENCE_DESIGN,wheel_crown_height=crown)
    parameters = config.wheel_radius,config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height
    for index in range(100):
        center = rng.normal(size=6)[::2]
        center *= scale
        axis = rng.normal(size=6)[::2]
        axis *= (1e-8,1.,1e8)[index%3]
        if index==0:
            axis[:] = (1.,-0.,0.)
        half = np.array((.24,0.,.45,0.,.005,0.))[::2]
        normals,wheels = np.empty((6,6))[:,::2],np.empty((6,6))[:,::2]
        box_axis_supports((center,axis),(normals,wheels),*parameters)
        old_normals,old_wheels = [],[]
        for direction in range(3):
            for sign in (-1.,1.):
                normal = sign*np.eye(3)[direction]
                old_normals.append(normal)
                old_wheels.append(center+wheel_support(normal,axis,config))
        assert_bits(normals,np.asarray(old_normals))
        assert_bits(wheels,np.asarray(old_wheels))
        gap = np.empty(6)[::2]
        radial_box_bounds((center,axis,half),(gap,),*parameters)
        assert_bits(gap,bounds_reference(center,axis,half,config))


@pytest.mark.parametrize("direction", [0,1,2])
@pytest.mark.parametrize("ulps", [-2,-1,0,1,2])
def test_actual_box_query_keeps_old_bounds_decision_at_reach_threshold(direction, ulps):
    config = REFERENCE_DESIGN
    axis,half = np.array((1.,0.,0.)),np.array((.24,.45,.005))
    lower = wheel_support(np.eye(3)[direction],axis,config)[direction]
    position = half[direction]+config.wheel_radius+config.suspension_travel-lower
    for _ in range(abs(ulps)):
        position = np.nextafter(position,-np.inf if ulps<0 else np.inf)
    center = np.zeros(3)
    center[direction] = position
    gap = np.empty(3)
    radial_box_bounds((center,axis,half),(gap,),config.wheel_radius,config.wheel_width/2,
                      config.wheel_shoulder_radius,config.wheel_crown_height)
    assert_bits(gap,bounds_reference(center,axis,half,config))
    surface = RadialSurface("box",np.eye(3),np.zeros(3),tuple(product(*((-h,h) for h in half))),None,None,0.,tuple(half))
    actual,expected = tuple(surface.query(center,axis,config)),tuple(surface_reference(surface,center,axis,config))
    assert len(actual) == len(expected)
    for a,b in zip(actual,expected):
        assert a[0].hex() == b[0].hex()
        assert_bits(a[1],b[1])
        assert_bits(a[2],b[2])
        assert a[3] == b[3]


@pytest.mark.parametrize("kernel", [box_axis_supports,radial_box_bounds])
@pytest.mark.parametrize("problem", ["count","shape","dtype","readonly","zero_axis"])
def test_native_axis_and_bounds_array_boundaries_keep_explicit_errors(kernel, problem):
    inputs = [np.zeros(3),np.array((1.,0.,0.))]
    outputs = (np.empty((6,3)),np.empty((6,3)))
    if kernel is radial_box_bounds:
        inputs.append(np.ones(3))
        outputs = (np.empty(3),)
    if problem == "count":
        inputs.pop()
    elif problem == "shape":
        inputs[0] = np.zeros(2)
    elif problem == "dtype":
        inputs[0] = np.zeros(3,dtype=np.float32)
    elif problem == "readonly":
        outputs[0].flags.writeable = False
    else:
        inputs[1][:] = 0.
    error = ZeroDivisionError if problem == "zero_axis" else (ValueError,BufferError)
    with pytest.raises(error):
        kernel(tuple(inputs),outputs,.33,.11,.01,.003)
