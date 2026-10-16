"""接触几何小向量范数对原NumPy逐位核对，完整接触证明仍走原算法。"""

from dataclasses import replace
from itertools import product

import numpy as np
import pytest
from lab_norm_box_reference import box_section as old_section
from lab_norm_radial_reference import RadialSurface as OldSurface
from test_lab_box_axis_cache import assert_section
from wheel_contact_kernels import box_edge_proof, ordinary_small_norm

from box_radial_geometry import _edge_proof, box_section
from radial_geometry import RadialSurface
from unsprung_dynamics import small_norm
from unsprung_motion import rotation_increment
from vehicle_designs import REFERENCE_DESIGN


def scalar_bits(a,b):
    assert type(a) is type(b)
    assert a.tobytes()==b.tobytes(),(a,b)


def arranged(vector,layout):
    if layout=='negative':return vector[::-1].copy()[::-1]
    if layout=='strided':
        storage=np.empty(2*len(vector),dtype=vector.dtype);storage[::2]=vector;return storage[::2]
    if layout=='broadcast':return np.broadcast_to(vector[:1],vector.shape)
    return vector.copy()


@pytest.mark.parametrize('dtype',[np.float16,np.float32,np.float64,np.int32,np.complex128])
@pytest.mark.parametrize('count',[2,3])
@pytest.mark.parametrize('layout',['C','strided','negative','broadcast'])
def test_small_norm_preserves_dtype_layout_readonly_and_signed_zero(dtype,count,layout):
    rng=np.random.default_rng(269)
    for index in range(120):
        vector=rng.normal(size=count)*(0.,1e-5,1.,1e2)[index%4]
        if index%8==0:vector[:]=-0.
        if dtype==np.complex128:vector=vector+1j*rng.normal(size=count)
        vector=arranged(vector.astype(dtype),layout)
        vector.flags.writeable=False;before=vector.tobytes()
        scalar_bits(small_norm(vector),np.linalg.norm(vector))
        assert vector.tobytes()==before


@pytest.mark.parametrize('count',[2,3])
def test_finite_subnormal_extreme_and_mixed_exponents_keep_original_squared_dot(count):
    rng=np.random.default_rng(271)
    for _ in range(3000):
        vector=np.ldexp(rng.uniform(-1.,1.,count),rng.integers(-538,511,count))
        scalar_bits(small_norm(vector),np.linalg.norm(vector))
    for value in (0.,-0.,np.nextafter(0.,1.),np.finfo(float).tiny):
        vector=np.full(count,value)
        scalar_bits(small_norm(vector),np.linalg.norm(vector))


@pytest.mark.parametrize('problem',['one','four','matrix','float32','endian','list'])
def test_native_norm_requires_explicit_small_double_buffer(problem):
    vector={'one':np.zeros(1),'four':np.zeros(4),'matrix':np.zeros((1,3)),
            'float32':np.zeros(3,dtype=np.float32),'endian':np.zeros(3,dtype='>f8'),'list':[0.,0.,0.]}[problem]
    with pytest.raises((TypeError,ValueError,BufferError)):ordinary_small_norm(vector)


@pytest.mark.parametrize('crown',[0.,.003])
@pytest.mark.parametrize('dtype',[np.float32,np.float64])
def test_complete_box_proof_matches_frozen_original_norms(crown,dtype):
    rng=np.random.default_rng(277)
    config=replace(REFERENCE_DESIGN,wheel_crown_height=crown)
    half=np.array((.24,.45,.005))
    for _ in range(100):
        center=np.array((0.,rng.uniform(-.7,.7),rng.uniform(.25,.4)),dtype=dtype)
        axis=np.array((1.,rng.uniform(-.08,.08),rng.uniform(-.08,.08)),dtype=dtype)
        assert_section(box_section(center,axis,half,config),old_section(center,axis,half,config))


def rows_bits(actual,expected):
    assert len(actual)==len(expected)
    for a,b in zip(actual,expected):
        scalar_bits(np.float64(a[0]),np.float64(b[0]))
        for first,last in zip(a[1:3],b[1:3]):
            assert first.dtype==last.dtype and first.shape==last.shape and first.tobytes()==last.tobytes()
        assert a[3]==b[3]


@pytest.mark.parametrize('kind',['plane','box'])
@pytest.mark.parametrize('layout',['C','F'])
def test_world_surface_transforms_and_normalization_match_frozen_original(kind,layout):
    frame=np.array(rotation_increment(np.array((.01,-.02,.03))),order=layout)
    half=(.24,.45,.005)
    arguments=('road',frame,np.array((0.,-.45,-.005)),tuple(product(*((-h,h) for h in half))),
               ((0.,0.,1.),0.) if kind=='plane' else None,None,0.,() if kind=='plane' else half)
    actual,expected=RadialSurface(*arguments),OldSurface(*arguments)
    for y in np.linspace(-.8,.8,50):
        center=np.array((0.,y,.32));axis=np.array((1.,.01,-.02))
        rows_bits(tuple(actual.query(center,axis,REFERENCE_DESIGN)),tuple(expected.query(center,axis,REFERENCE_DESIGN)))


def old_edge_proof(deltas,first_theta):
    rows=[]
    for delta in deltas:
        length=np.linalg.norm(delta)
        critical=np.sqrt(max(length*length-first_theta*first_theta,0.))
        minimum_dot=-np.linalg.norm(np.minimum(delta,0.)) if min(delta)<0. else min(delta)
        maximum_dot=np.linalg.norm(np.maximum(delta,0.)) if max(delta)>0. else max(delta)
        rows.append((critical,minimum_dot,maximum_dot))
    return np.asarray(rows)


@pytest.mark.parametrize('scalar',[np.float32,np.float64])
@pytest.mark.parametrize('layout',['C','F','strided','negative'])
def test_batched_edge_bounds_preserve_dot_sqrt_min_max_signs_and_curve_type(scalar,layout):
    rng=np.random.default_rng(281)
    for index in range(100):
        scale=(0.,1e-150,1e-10,1.,1e150)[index%5]
        deltas=rng.normal(size=(4,2))*scale
        if index==0:deltas[:]=((-0.,0.),(0.,-0.),(-0.,-0.),(0.,0.))
        if layout=='F':deltas=np.array(deltas,order='F')
        elif layout=='negative':deltas=deltas[:,::-1].copy()[:,::-1]
        elif layout=='strided':
            storage=np.empty((4,4));storage[:,::2]=deltas;deltas=storage[:,::2]
        deltas.flags.writeable=False;before=deltas.tobytes()
        theta=scalar(rng.uniform(0.,.3)*min(scale,1e10))
        a,b=_edge_proof(deltas,theta),old_edge_proof(deltas,theta)
        assert a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()
        assert deltas.tobytes()==before


@pytest.mark.parametrize('ulps',[-2,-1,0,1,2])
def test_edge_critical_value_at_original_zero_boundary(ulps):
    theta=np.float64(1.)
    for _ in range(abs(ulps)):theta=np.nextafter(theta,-np.inf if ulps<0 else np.inf)
    deltas=np.array(((1.,0.),(-1.,0.),(0.,1.),(0.,-1.)))
    assert _edge_proof(deltas,theta).tobytes()==old_edge_proof(deltas,theta).tobytes()


@pytest.mark.parametrize('problem',['count','shape','dtype','readonly','output-shape','output-dtype'])
def test_edge_native_buffer_contract_has_explicit_errors(problem):
    inputs=[np.ones((4,2))];outputs=[np.empty((4,3))]
    if problem=='count':inputs=[]
    elif problem=='shape':inputs[0]=np.ones((3,2))
    elif problem=='dtype':inputs[0]=inputs[0].astype(np.float32)
    elif problem=='readonly':outputs[0].flags.writeable=False
    elif problem=='output-shape':outputs[0]=np.zeros((4,2))
    else:outputs[0]=outputs[0].astype(np.float32)
    with pytest.raises((ValueError,BufferError)):box_edge_proof(tuple(inputs),tuple(outputs),.1)


def test_edge_native_output_keeps_caller_strides_and_gaps():
    deltas=np.array(((1.,2.),(-1.,2.),(1.,-2.),(-1.,-2.)))
    storage=np.full((4,6),71.);output=storage[:,::2]
    box_edge_proof((deltas,),(output,),.3)
    assert output.tobytes()==old_edge_proof(deltas,np.float64(.3)).tobytes()
    assert np.all(storage[:,1::2]==71.)
