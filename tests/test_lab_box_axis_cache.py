"""Box轴向不变量复用对原支持偏移、完整证明和包围盒逐位核对。"""

import struct
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from lab_box_reference import box_section_reference as reference_section
from wheel_contact_kernels import (
    box_axis_cache_info,
    box_axis_supports,
    box_face_candidates,
    radial_box_bounds,
)

from box_radial_geometry import _axis_curvature, box_section, wheel_support
from vehicle_designs import REFERENCE_DESIGN


def assert_bits(a,b):
    assert a.dtype==b.dtype and a.shape==b.shape
    assert a.tobytes()==b.tobytes()


def assert_section(actual,expected):
    if expected is None:
        assert actual is None
        return
    assert actual[0].hex()==expected[0].hex()
    for a,b in zip(actual[1:4],expected[1:4]):assert_bits(a,b)
    assert actual[4]==expected[4]


@pytest.fixture(autouse=True)
def fresh_constants():
    box_axis_cache_info(True);_axis_curvature.cache_clear()
    yield
    box_axis_cache_info(True);_axis_curvature.cache_clear()


@pytest.mark.parametrize('crown',[0.,.003,.006])
@pytest.mark.parametrize('scale',[0.,1e-11,1.,1e6])
def test_raw_offsets_keep_negative_zero_and_match_all_original_face_and_bound_bits(crown,scale):
    config = replace(REFERENCE_DESIGN,wheel_crown_height=crown)
    constants = config.wheel_radius,config.wheel_width/2,config.wheel_shoulder_radius,crown
    rng = np.random.default_rng(193)
    for index in range(100):
        center = rng.normal(size=6)[::2]*scale
        axis = rng.normal(size=6)[::2]*(1e-8,1.,1e8)[index%3]
        if index%10==0:axis[:] = (1.,-0.,0.)
        half = np.array((.24,.45,.005))
        normals,wheels = np.empty((6,6))[:,::2],np.empty((6,6))[:,::2]
        box_axis_supports((center,axis),(normals,wheels),*constants)
        expected_normals = np.array([sign*np.eye(3)[j] for j in range(3) for sign in (-1.,1.)])
        expected_offsets = np.array([wheel_support(normal,axis,config) for normal in expected_normals])
        expected_wheels = center+expected_offsets
        assert_bits(normals,expected_normals);assert_bits(wheels,expected_wheels)
        gap = np.empty(6)[::2]
        radial_box_bounds((center,axis,half),(gap,),*constants)
        old_gap = np.maximum(np.maximum(expected_wheels[1::2].diagonal()-half,-half-expected_wheels[::2].diagonal()),0.)
        assert_bits(gap,old_gap)
        outputs = (np.empty((6,6))[:,::2],np.empty((6,6))[:,::2],np.empty(12)[::2],np.empty((6,6))[:,::2],np.empty(12)[::2])
        box_face_candidates((center,axis,half),outputs,*constants,1e-13)
        assert_bits(outputs[0],expected_normals);assert_bits(outputs[1],expected_wheels)
        for row,(normal,wheel) in enumerate(zip(expected_normals,expected_wheels)):
            distance = np.dot(normal,wheel)-half[row//2]
            road = wheel-distance*normal
            assert outputs[2][row].tobytes()==distance.tobytes()
            assert_bits(outputs[3][row],road)
            assert outputs[4][row]==all(abs(road[j])<=half[j]+1e-13 for j in range(3) if j!=row//2)
        assert box_axis_cache_info()['hits']>=2


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
@pytest.mark.parametrize('scalar',[float,np.float32,np.float64])
def test_full_proof_cold_warm_and_changed_center_keep_original_scalar_types(dtype,scalar):
    config = SimpleNamespace(wheel_radius=scalar(.33),wheel_width=scalar(.22),
                             wheel_shoulder_radius=scalar(.01),wheel_crown_height=scalar(.003))
    rng = np.random.default_rng(197)
    for _ in range(100):
        center = np.array((0.,rng.uniform(-.7,.7),rng.uniform(.25,.4)),dtype=dtype)
        axis = np.array((1.,rng.uniform(-.05,.05),rng.uniform(-.05,.05)),dtype=dtype)
        half = np.array((.24,.45,.005))
        for _ in range(2):
            assert_section(box_section(center,axis,half,config),reference_section(center,axis,half,config))
            center[1] = np.nextafter(center[1],dtype(np.inf))


def test_complete_parameter_bits_axis_bits_and_eviction_do_not_reuse_wrong_constants():
    parameters = (.33,.11,.01,.003)
    axis = np.array((1.,0.,0.))
    key = axis.dtype.str,axis.tobytes(),struct.pack('=4d',*parameters)
    def calculate(value,params=parameters):
        outputs=np.empty((6,3)),np.empty((6,3))
        box_axis_supports((np.zeros(3),value),outputs,*params)
        return outputs
    original = calculate(axis)
    for a,b in zip(original,calculate(axis)):assert_bits(a,b)
    assert box_axis_cache_info()['hits']==1
    for changed in (np.array((1.,-0.,0.)),np.array((1.,np.nextafter(0.,1.),0.))):
        calculate(changed)
    calculate(axis,(.33,.11,-0.,.003));calculate(axis,(.33,.11,0.,.003))
    assert box_axis_cache_info()['misses']==5
    for index in range(520):
        changed = np.array((1.,.001+index*1e-5,0.))
        calculate(changed)
        normalized = changed/np.linalg.norm(changed)
        _axis_curvature(normalized.dtype.str,normalized.tobytes(),*parameters,key[2],0)
    assert box_axis_cache_info()['capacity']==_axis_curvature.cache_info().currsize==512
    misses = box_axis_cache_info()['misses']
    rebuilt = calculate(axis)
    assert box_axis_cache_info()['misses']==misses+1
    for a,b in zip(original,rebuilt):assert_bits(a,b)


def test_returned_witness_arrays_remain_independent_and_writable():
    center,axis,half = np.array((0.,0.,.32)),np.array((1.,0.,0.)),np.array((.24,.45,.005))
    expected = reference_section(center,axis,half,REFERENCE_DESIGN)
    assert expected is not None
    first = box_section(center,axis,half,REFERENCE_DESIGN)
    for array in first[1:4]:array[:] = 71.
    assert_section(box_section(center,axis,half,REFERENCE_DESIGN),expected)


@pytest.mark.parametrize('kernel',[box_axis_supports,radial_box_bounds,box_face_candidates])
@pytest.mark.parametrize('problem',['count','shape','dtype','readonly'])
def test_native_axis_constant_buffer_errors(kernel,problem):
    inputs,outputs,constants = [np.zeros(3),np.array((1.,0.,0.))],(np.empty((6,3)),np.empty((6,3))),(.33,.11,.01,.003)
    if kernel is radial_box_bounds:
        inputs.append(np.ones(3));outputs = (np.empty(3),)
    elif kernel is box_face_candidates:
        inputs.append(np.ones(3))
        outputs = (np.empty((6,3)),np.empty((6,3)),np.empty(6),np.empty((6,3)),np.empty(6))
        constants += (1e-13,)
    if problem=='count':inputs.pop()
    elif problem=='shape':inputs[0] = np.zeros(2)
    elif problem=='dtype':inputs[0] = inputs[0].astype(np.float32)
    else:outputs[0].flags.writeable = False
    with pytest.raises((ValueError,BufferError)):
        kernel(tuple(inputs),outputs,*constants)
    assert box_axis_cache_info()['hits']==box_axis_cache_info()['misses']==0
