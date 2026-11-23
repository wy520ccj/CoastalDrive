"""面候选和四棱坐标对独立旧公式逐位核对，保留边界资格与零符号。"""

from itertools import product

import numpy as np
import pytest
from lab_box_reference import wheel_support
from wheel_contact_kernels import box_edge_frames, box_face_candidates

from vehicle_designs import REFERENCE_DESIGN


def assert_bits(actual,expected):
    assert actual.dtype == expected.dtype
    assert actual.shape == expected.shape
    assert actual.tobytes() == expected.tobytes()


@pytest.mark.parametrize("dtype", [np.float32,np.float64])
@pytest.mark.parametrize("scale", [0.,1e-11,1.,1e6])
def test_face_witnesses_and_eligibility_match_original_formula(dtype,scale):
    rng = np.random.default_rng(149)
    config = REFERENCE_DESIGN
    parameters = config.wheel_radius,config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height
    for _ in range(100):
        center = (rng.normal(size=3)*scale).astype(dtype)
        axis = rng.normal(size=3).astype(dtype)
        axis /= np.linalg.norm(axis)
        half = rng.uniform(.001,1.,size=3).astype(dtype)
        tolerance = 128*np.finfo(float).eps*max(1.,np.linalg.norm(center),max(half))
        outputs = (np.empty((6,6))[:,::2],np.empty((6,6))[:,::2],np.empty(12)[::2],
                   np.empty((6,6))[:,::2],np.empty(12)[::2])
        box_face_candidates(tuple(np.asarray(a,dtype=float) for a in (center,axis,half)),outputs,*parameters,tolerance)
        expected = [[] for _ in outputs]
        for index in range(3):
            for sign in (-1.,1.):
                normal = sign*np.eye(3)[index]
                wheel = center+wheel_support(normal,axis,config)
                distance = float(np.dot(normal,wheel)-half[index])
                road = wheel-distance*normal
                eligible = float(all(abs(road[j])<=half[j]+tolerance for j in range(3) if j!=index))
                for rows,value in zip(expected,(normal,wheel,distance,road,eligible)):
                    rows.append(value)
        for actual,rows in zip(outputs,expected):
            assert_bits(actual,np.asarray(rows))


@pytest.mark.parametrize("free", [0,1,2])
@pytest.mark.parametrize("dtype", [np.float32,np.float64])
def test_four_edges_keep_order_coordinates_and_signed_zeros(free,dtype):
    rng = np.random.default_rng(151)
    fixed = [j for j in range(3) if j!=free]
    for index in range(100):
        center = rng.normal(size=6).astype(dtype)[::2]
        half = rng.uniform(0.,2.,size=6).astype(dtype)[::2]
        if index%10==0:
            center[:] = (-0.,0.,-0.)
            half[:] = (0.,-0.,0.)
        outputs = (np.empty((8,6))[:,::2],np.empty((4,6))[:,::2],np.empty((4,4))[:,::2])
        box_edge_frames(tuple(np.asarray(a,dtype=float) for a in (center,half)),outputs,free)
        bases,edges,deltas = [],[],[]
        for signs in product((-1.,1.),repeat=2):
            bases.extend(np.eye(3)[fixed]*np.asarray(signs)[:,None])
            edge = np.zeros(3)
            edge[fixed] = np.asarray(signs)*half[fixed]
            edges.append(edge)
            deltas.append((center[fixed]-edge[fixed])*signs)
        for actual,rows in zip(outputs,(bases,edges,deltas)):
            assert_bits(actual,np.asarray(rows))


@pytest.mark.parametrize("ulps", [-2,-1,0,1,2])
def test_face_membership_at_tolerance_boundary(ulps):
    config = REFERENCE_DESIGN
    axis = np.array((1.,0.,0.))
    half = np.array((.3,.5,.1))
    tolerance = 128*np.finfo(float).eps
    normal = -np.eye(3)[2]
    offset = wheel_support(normal,axis,config)
    center = np.zeros(3)
    center[0] = half[0]+tolerance-offset[0]
    for _ in range(abs(ulps)):
        center[0] = np.nextafter(center[0],-np.inf if ulps<0 else np.inf)
    outputs = (np.empty((6,3)),np.empty((6,3)),np.empty(6),np.empty((6,3)),np.empty(6))
    box_face_candidates((center,axis,half),outputs,config.wheel_radius,config.wheel_width/2,
                        config.wheel_shoulder_radius,config.wheel_crown_height,tolerance)
    wheel = center+offset
    distance = float(np.dot(normal,wheel)-half[2])
    road = wheel-distance*normal
    assert_bits(outputs[3][4],road)
    assert bool(outputs[4][4]) == all(abs(road[j])<=half[j]+tolerance for j in (0,1))


@pytest.mark.parametrize("kernel", [box_face_candidates,box_edge_frames])
@pytest.mark.parametrize("problem", ["count","shape","dtype","readonly"])
def test_candidate_buffer_boundaries_raise_explicit_errors(kernel,problem):
    inputs = [np.zeros(3),np.array((1.,0.,0.))]
    outputs = (np.empty((8,3)),np.empty((4,3)),np.empty((4,2)))
    constants = (0,)
    if kernel is box_face_candidates:
        inputs.append(np.ones(3))
        outputs = (np.empty((6,3)),np.empty((6,3)),np.empty(6),np.empty((6,3)),np.empty(6))
        constants = (.3,.1,.02,.003,1e-13)
    if problem=="count":inputs.pop()
    elif problem=="shape":inputs[0] = np.zeros(2)
    elif problem=="dtype":inputs[0] = np.zeros(3,dtype=np.float32)
    else:outputs[0].flags.writeable = False
    with pytest.raises((ValueError,BufferError)):
        kernel(tuple(inputs),outputs,*constants)


@pytest.mark.parametrize("free", [-1,3])
def test_edge_axis_rejects_invalid_index(free):
    with pytest.raises(ValueError):
        box_edge_frames((np.zeros(3),np.ones(3)),(np.empty((8,3)),np.empty((4,3)),np.empty((4,2))),free)
