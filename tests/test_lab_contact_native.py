"""批量内核对旧正式公式逐位验证，覆盖真实有限边缘、微小运动及原生数组边界。"""

from dataclasses import fields

import numpy as np
import pytest
from lab_contact_reference import finite_gradients_reference, tire_ports_reference
from test_finite_radial_contact import contact_case
from test_unsprung_joint import hardware
from wheel_contact_kernels import finite_radial_gradients, unsprung_tire_ports

from unsprung_drivetrain import tire_ports
from unsprung_motion import rotation_increment
from vehicle_designs import REFERENCE_DESIGN


def assert_bits(actual, expected):
    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    assert actual.tobytes() == expected.tobytes()


@pytest.mark.parametrize("normal_offsets,material_axes,guide_bias", [
    (a,b,c) for a in (False,True) for b in (False,True) for c in (False,True)])
def test_four_wheel_ports_are_bitwise_equal_to_original_formula(normal_offsets,material_axes,guide_bias):
    rng = np.random.default_rng(17)
    graph,_contacts,_partition = hardware(REFERENCE_DESIGN,steering=7.,trail=.03,steer_rate=.4)
    for _ in range(100):
        arrays = [rng.normal(size=(4,6))[:,::2] for _ in range(6)]
        offsets,tangents,laterals,normals,steering,axes = arrays
        trails = rng.uniform(-.05,.05,size=4)
        extra = {"normal_offsets": rng.normal(size=(4,3)) if normal_offsets else None,
                 "material_axes": axes if material_axes else None,
                 "wheel_velocity_bias": rng.normal(size=(4,3)) if guide_bias else None}
        expected = tire_ports_reference(graph,offsets,tangents,laterals,normals,steering,trails,**extra)
        actual = tire_ports(graph,offsets,tangents,laterals,normals,steering,trails,**extra)
        for field in fields(actual):
            a,b = getattr(actual,field.name),getattr(expected,field.name)
            if a is None:
                assert b is None
            else:
                assert_bits(a,b)


@pytest.mark.parametrize("vertical", [-1e-5,-1e-11,-0.,0.,1e-11,1e-5])
@pytest.mark.parametrize("speed", [0.,5.,-5.])
@pytest.mark.parametrize("altitude", [0.,1.])
def test_finite_gradients_keep_exact_plane_or_edge_work_and_contact_basis(vertical,speed,altitude):
    world,ground,bump,context = contact_case()
    try:
        context.centers = context.centers+np.array((0.,0.,altitude))
        context.target = context.roads.query(context.centers,context.rotation[:,2],context.hardware.axes)
        rng = np.random.default_rng(23)
        for spin in (np.zeros(3),np.array((.1,-.2,.3)),rng.normal(size=3)):
            h = context.dt
            velocity = np.r_[0.,speed,vertical,spin,np.zeros(10)]
            graph = context.hardware
            wheel = graph.mechanical.wheel_jacobians@velocity[:10]
            middle_rotation = rotation_increment(.5*h*spin)
            end_rotation = rotation_increment(h*spin)
            middle_axes = graph.axes@middle_rotation.T
            end_axes = graph.axes@end_rotation.T
            # 此处保留任意平均轮轴输入，独立核对整个有限梯度公式；正式路径由完整A/B覆盖。
            average = .5*(graph.axes+end_axes)
            middle = context.roads.query(context.centers+.5*h*wheel,middle_rotation@context.rotation[:,2],middle_axes)
            end = context.roads.query(context.centers+h*wheel,end_rotation@context.rotation[:,2],end_axes)
            planes,same,touch = np.zeros((4,3)),np.zeros(4),np.zeros(4)
            for i,(first,last) in enumerate(zip(context.target.hits,end.hits,strict=True)):
                touch[i] = last is not None
                if first is not None and last is not None and first.node==last.node and first.plane is not None and first.plane==last.plane:
                    planes[i],same[i] = first.plane[0],1.
            expected = finite_gradients_reference(middle,end,context.target,graph,middle_axes,average,wheel,spin,h,context.config)
            result = (np.empty((4,16)),np.empty(4),np.empty((4,3)),np.empty((4,3)),np.empty((4,3)))
            finite_radial_gradients((middle.normals,middle_axes,graph.axes,average,wheel,spin,
                graph.mechanical.wheel_arms,graph.mechanical.guides,context.target.deflection,end.deflection,
                planes,same,touch),result,h,context.config.wheel_radius,context.config.wheel_width/2,
                context.config.wheel_shoulder_radius,context.config.wheel_crown_height)
            for a,b in zip(result,expected,strict=True):
                assert_bits(a,b)
    finally:
        world.removeRigidBody(bump)
        world.removeRigidBody(ground)


def native_ports_input():
    graph,_contacts,_partition = hardware(REFERENCE_DESIGN)
    arms,guides,axes,brakes = graph.mechanical.wheel_arms,graph.mechanical.guides,graph.axes,graph.brakes
    values = (arms,guides,axes,brakes,np.zeros((4,3)),np.tile((0.,1.,0.),(4,1)),
              np.tile((1.,0.,0.),(4,1)),guides,np.zeros((4,3)),np.zeros(4),None,None)
    output = (np.empty((4,3,16)),np.empty((4,3)),np.empty((4,3)))
    return values,output


@pytest.mark.parametrize("failure", ["float32","wrong_shape","readonly_output","bad_count"])
def test_native_boundary_rejects_invalid_buffers_without_overwriting(failure):
    values,output = native_ports_input()
    values = list(values)
    for target in output:
        target.fill(123.)
    if failure=="float32":
        values[0] = values[0].astype(np.float32)
    elif failure=="wrong_shape":
        values[0] = values[0][:3]
    elif failure=="readonly_output":
        output[0].flags.writeable = False
    else:
        values.pop()
    with pytest.raises((ValueError,BufferError)):
        unsprung_tire_ports(tuple(values),output)
    assert all(np.all(value==123.) for value in output)


def test_finite_gradient_rejects_degenerate_normal_before_any_world_integration():
    graph,_contacts,_partition = hardware(REFERENCE_DESIGN)
    normal = np.zeros((4,3))
    inputs = (normal,graph.axes,graph.axes,graph.axes,np.zeros((4,3)),np.zeros(3),
              graph.mechanical.wheel_arms,graph.mechanical.guides,np.zeros(4),np.zeros(4),
              normal,np.zeros(4),np.zeros(4))
    output = (np.empty((4,16)),np.empty(4),np.empty((4,3)),np.empty((4,3)),np.empty((4,3)))
    with pytest.raises(ArithmeticError,match="空间梯度退化"):
        finite_radial_gradients(inputs,output,1/240,.33,.12,.025,.01)
