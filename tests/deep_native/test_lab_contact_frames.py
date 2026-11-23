"""四轮接触准备对原路径/标量算术及完整真实查询逐位核对。"""

from dataclasses import fields

import numpy as np
import pytest
from lab_contact_frames_reference import FiniteRadialContact as ReferenceContact
from test_finite_radial_contact import contact_case
from wheel_contact_kernels import finite_contact_averages, finite_contact_frames, rotated_path

from tire_compliance import project_deformation
from unsprung_contact_geometry import _average_axes, _material_frame
from unsprung_motion import FiniteSuspensionMotion


def bits(a,b):
    assert a.dtype==b.dtype and a.shape==b.shape and a.strides==b.strides
    assert a.tobytes()==b.tobytes(),(a,b)


def arranged(value,order):
    if order in ('C','F'):return np.array(value,order=order)
    if order=='reverse':return value[:,::-1].copy()[:,::-1]
    storage=np.empty((4,value.shape[1]*2),dtype=value.dtype)
    storage[:,::2]=value
    return storage[:,::2]


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
@pytest.mark.parametrize('order',['C','F','strided'])
def test_four_original_rotated_paths_keep_types_zero_angle_and_layout(dtype,order):
    rng=np.random.default_rng(211)
    for index in range(120):
        axes=arranged(rng.normal(size=(4,3)).astype(dtype),order)
        angular=(rng.normal(size=6)[::2]*(0.,1e-150,1e-9,.1,1.,1e6)[index%6]).astype(dtype)
        speed=np.linalg.norm(angular)
        h=(1/240,0.,np.float32(.003),-.01)[index%4]
        expected=(np.asarray([rotated_path(tuple(axis),tuple(angular/speed),h*speed,1.)[1] for axis in axes])
                  if speed else axes)
        actual=_average_axes(axes,angular,speed,h)
        bits(actual,expected)
        if not speed:assert actual is axes


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
@pytest.mark.parametrize('scalar',[float,np.float32,np.float64])
def test_material_frame_matches_original_sum_power_steering_and_layout(dtype,scalar):
    rng=np.random.default_rng(223)
    for order in ('C','F','strided','reverse'):
        for index in range(50):
            previous=arranged((rng.normal(size=(4,3))*(0.,1e-150,.01,1.,1e6)[index%5]).astype(dtype),order)
            axes=[arranged(rng.normal(size=(4,3)),order) for _ in range(3)]
            steering=arranged(rng.normal(size=(4,3)),order)
            target,initial=rng.normal(size=4),rng.normal(size=4)
            scales=np.abs(rng.normal(size=4))+.01
            if index%5==0:target=initial.copy()
            h=(1/240,np.float32(.003),-.01)[index%3]
            stiffness=scalar((0.,2e5,1e12)[index%3])
            normal=-(target-initial)/(h*scales)
            projected=[project_deformation(value,tuple(map(tuple,frame)),stiffness)
                       for value,frame in zip(previous,zip(*axes))]
            expected=(np.asarray([p[0] for p in projected]),np.asarray([p[1] for p in projected]),
                      np.column_stack((steering[:,:2],normal)))
            for a,b in zip(_material_frame(previous,*axes,target,initial,scales,steering,h,stiffness),expected):bits(a,b)


@pytest.mark.parametrize('finite',[False,True])
@pytest.mark.parametrize('bias',[False,True])
@pytest.mark.parametrize('h',[1/240,1e-5])
def test_complete_real_plane_box_contact_keeps_every_field_and_cache_boundary(finite,bias,h):
    world,ground,bump,current=contact_case()
    try:
        current.dt=h
        current.deformation=np.array(((.002,-.003,.0001),)*4)
        current.steering=np.array(((0.,0.,.03),)*4)
        current.trails=np.full(4,.004)
        if bias:current.wheel_velocity_bias=np.array(((.001,-.002,.003),)*4)
        if finite:
            position=current.centers[0]-current.hardware.mechanical.wheel_arms[0]
            current.finite_motion=FiniteSuspensionMotion(position,current.rotation,current.centers,np.zeros(4),
                current.hardware.mechanical,np.zeros((4,3)) if not bias else current.wheel_velocity_bias,h)
        old=ReferenceContact(current.roads,current.hardware,current.centers,current.rotation,current.hardware.axes,
            current.deformation,current.steering,current.trails,h,current.config,current.on_asphalt,
            wheel_velocity_bias=current.wheel_velocity_bias,finite_motion=current.finite_motion)
        velocity=np.zeros(16);velocity[1]=5.;velocity[3:6]=(.1,-.02,.03)
        for _ in range(2):
            actual,expected=current.evaluate(velocity),old.evaluate(velocity)
            assert actual.geometry.hits==expected.geometry.hits
            for field in fields(actual.geometry)[1:]:bits(getattr(actual.geometry,field.name),getattr(expected.geometry,field.name))
            for field in fields(actual.contacts):
                a,b=getattr(actual.contacts,field.name),getattr(expected.contacts,field.name)
                if a is None:assert b is None
                else:bits(a,b)
            for field in fields(actual)[2:]:bits(getattr(actual,field.name),getattr(expected,field.name))
            assert current.evaluate(velocity.copy()) is actual
            velocity[7]=np.nextafter(velocity[7],np.inf)
    finally:
        world.removeRigidBody(bump);world.removeRigidBody(ground)


def arguments(kernel):
    if kernel is finite_contact_averages:
        return [np.ones((4,3)),np.array((1.,0.,0.))],((4,3),),(.03,)
    return [np.ones((4,3)) for _ in range(4)]+[np.ones(4) for _ in range(3)]+[np.ones((4,3))],((4,2),(4,),(4,3)),(.003,1e5)


@pytest.mark.parametrize('kernel',[finite_contact_averages,finite_contact_frames])
@pytest.mark.parametrize('problem',['count','shape','dtype','readonly'])
def test_contact_buffer_errors_are_explicit(kernel,problem):
    inputs,shapes,constants=arguments(kernel)
    outputs=tuple(np.empty(shape) for shape in shapes)
    if problem=='count':inputs.pop()
    elif problem=='shape':inputs[0]=np.zeros(3)
    elif problem=='dtype':inputs[0]=inputs[0].astype(np.float32)
    else:outputs[0].flags.writeable=False
    with pytest.raises((ValueError,BufferError)):kernel(tuple(inputs),outputs,*constants)


@pytest.mark.parametrize('kernel',[finite_contact_averages,finite_contact_frames])
def test_strided_outputs_preserve_storage_gaps_and_readonly_inputs(kernel):
    inputs,shapes,constants=arguments(kernel)
    for value in inputs:value.flags.writeable=False
    storage=tuple(np.full((*shape[:-1],shape[-1]*2),71.) for shape in shapes)
    outputs=tuple(value[...,::2] for value in storage)
    expected=tuple(np.empty(shape) for shape in shapes)
    kernel(tuple(inputs),outputs,*constants);kernel(tuple(inputs),expected,*constants)
    for value,a,b in zip(storage,outputs,expected):
        assert a.tobytes()==b.tobytes()
        assert np.all(value[...,1::2]==71.)


def test_zero_speed_keeps_original_axes_identity():
    axes=np.array(((1.,-0.,0.),)*4,order='F')
    assert _average_axes(axes,np.zeros(3),0.,1/240) is axes
