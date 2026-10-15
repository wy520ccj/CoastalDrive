"""完整四轮材料与独立旧正式公式逐位核对，覆盖曲线节点、松弛与接触边界。"""

import struct
from dataclasses import fields, replace
from itertools import product

import numpy as np
import pytest
from damper_bench_reference import document
from lab_normal_reference import normal_material as reference_material
from mechanical_kernels import unsprung_normal_material, unsprung_normal_parameters

from suspension_bench import fit_bench
from suspension_installation import installation_curve
from unsprung_contact import _normal_parameters, normal_material
from vehicle_designs import REFERENCE_DESIGN


def assert_material_bits(actual,expected):
    for field in fields(actual):
        a,b = getattr(actual,field.name),getattr(expected,field.name)
        if isinstance(a,np.ndarray):
            assert a.dtype == b.dtype,field.name
            assert a.shape == b.shape,field.name
            assert a.tobytes() == b.tobytes(),(field.name,a,b)
        else:
            assert struct.pack('!d',a) == struct.pack('!d',b),(field.name,a,b)


@pytest.fixture(scope="module")
def fitted():
    config,report = fit_bench(document(),replace(REFERENCE_DESIGN,unsprung_enabled=True))
    assert report['passed']
    return config


@pytest.mark.parametrize("coil,installation,nonlinear",
                         [flags for flags in product((False,True),repeat=3) if flags[0] or not flags[1]])
def test_complete_four_wheel_material_matches_old_bits(fitted,coil,installation,nonlinear):
    config = replace(fitted,suspension_coil_enabled=coil,
                     suspension_spring_preloads=fitted.suspension_spring_preloads if coil else (0.,)*4,
                     suspension_installation_curves=fitted.suspension_installation_curves if installation else None,
                     suspension_damper_curves=fitted.suspension_damper_curves if nonlinear else None)
    rng = np.random.default_rng(157)
    for index in range(200):
        arrays = [rng.normal(size=8)[::2]*scale for scale in (.3,2.,.04,.04,2e5,600.)]
        arrays[4][:] = abs(arrays[4])
        arrays[5][:] = abs(arrays[5])
        if index%10==0:
            for a in arrays:a[:] = (0.,-0.,0.,-0.)
        dt = (1/240,1e-6,.1)[index%3]
        arguments = (*arrays[:4],dt,config,*arrays[4:])
        assert_material_bits(normal_material(*arguments),reference_material(*arguments))


@pytest.mark.parametrize("offset", [-1,0,1])
def test_nodes_extrapolation_release_and_contact_switch_keep_bits(fitted,offset):
    positions = sorted({value for rows in fitted.suspension_installation_curves for value,_,_ in rows})
    positions += [-.6,.6,-fitted.suspension_travel,fitted.suspension_travel]
    for position in positions:
        if offset:position = np.nextafter(position,-np.inf if offset<0 else np.inf)
        q = np.full(4,position)
        for node in fitted.suspension_damper_curves[0]:
            ratios = np.array([installation_curve(rows)[1].at(position)[1]/installation_curve(rows)[1].reference_ratio
                               for rows in fitted.suspension_installation_curves])
            speed = node[0]/ratios
            positive = np.array((0.,-0.,.01,-.01))
            arguments = (q,speed,positive,-positive,1/240,fitted,np.full(4,2e5),np.full(4,600.))
            assert_material_bits(normal_material(*arguments),reference_material(*arguments))
    plain = replace(fitted,suspension_installation_curves=None,suspension_damper_curves=None,
                    suspension_antiroll_rates=(0.,-0.),suspension_stop_rates=(0.,)*4)
    q = -np.array(plain.suspension_spring_preloads)/plain.suspension_spring_rates
    previous = np.full(4,.01+(1/240)*2e5*.01/600.)
    if offset:
        q = np.nextafter(q,-np.inf if offset<0 else np.inf)
        previous = np.nextafter(previous,-np.inf if offset<0 else np.inf)
    arguments = (q,np.array((0.,-0.,1.,-1.)),np.full(4,.01),previous,1/240,plain,np.full(4,2e5),np.full(4,600.))
    assert_material_bits(normal_material(*arguments),reference_material(*arguments))


@pytest.mark.parametrize("dtype", [np.float32,np.float64])
def test_public_input_precision_and_readonly_arrays_keep_original_semantics(fitted,dtype):
    arrays = [np.array(a,dtype=dtype) for a in ((.02,-.04,.12,-.25),(.3,-.6,0.,-0.),
              (.02,0.,-.01,.015),(.01,0.,-.02,.013),(2e5,1.8e5,2.4e5,2.2e5),(600.,700.,0.,800.))]
    for array in arrays:array.flags.writeable = False
    arguments = (*arrays[:4],1/240,fitted,*arrays[4:])
    assert_material_bits(normal_material(*arguments),reference_material(*arguments))


def test_parameter_cache_eviction_and_config_changes_never_reuse_vehicle_state(fitted):
    _normal_parameters.cache_clear()
    arguments = (np.zeros(4),np.array((1.,-.2,.3,-.4)),np.full(4,.02),np.full(4,.01),1/240)
    for index in range(40):
        config = replace(fitted,suspension_spring_preloads=(400.+index,)*4)
        suffix = (config,np.full(4,2e5),np.full(4,600.))
        assert_material_bits(normal_material(*arguments,*suffix),reference_material(*arguments,*suffix))
    assert _normal_parameters.cache_info().currsize == 32
    suffix = (fitted,np.full(4,2e5),np.full(4,600.))
    for _ in range(2):
        assert_material_bits(normal_material(*arguments,*suffix),reference_material(*arguments,*suffix))


@pytest.mark.parametrize("problem", ["count","shape","dtype","readonly","capsule"])
def test_native_material_buffer_boundary_errors(problem):
    parameters = unsprung_normal_parameters((4e4,)*4,(5e3,)*2,(2e5,)*4,.2,False,(0.,)*4,
                                            (1800.,)*4,(2400.,)*4,None,None,None)
    inputs = [np.zeros(4) for _ in range(6)]
    output = np.empty((13,4))
    if problem=='count':inputs.pop()
    elif problem=='shape':output = np.empty((12,4))
    elif problem=='dtype':inputs[0] = inputs[0].astype(np.float32)
    elif problem=='readonly':output.flags.writeable = False
    else:parameters = object()
    with pytest.raises((ValueError,BufferError)):
        unsprung_normal_material(parameters,tuple(inputs),output,1/240)


def test_native_material_strided_output_preserves_storage_gaps():
    parameters = unsprung_normal_parameters((4e4,)*4,(5e3,)*2,(2e5,)*4,.2,False,(0.,)*4,
                                            (1800.,)*4,(2400.,)*4,None,None,None)
    rng = np.random.default_rng(163)
    inputs = tuple(rng.normal(size=8)[::2] for _ in range(6))
    expected = np.empty((13,4))
    storage = np.full((26,8),71.)
    actual = storage[::2,::2]
    a = unsprung_normal_material(parameters,inputs,expected,1/240)
    b = unsprung_normal_material(parameters,inputs,actual,1/240)
    assert a == b and actual.tobytes() == expected.tobytes()
    assert np.all(storage[1::2]==71.) and np.all(storage[:,1::2]==71.)


@pytest.mark.parametrize("problem", ['pair','count','nodes','order','reference'])
def test_native_parameter_errors_release_partial_curve_storage(problem):
    axis = ((-.1,0.,.1),(-.08,0.,.08),(.8,)*3,.8)
    springs,dampers = (axis,)*4,(axis,)*4
    if problem=='pair':dampers = None
    elif problem=='count':springs = springs[:3]
    elif problem=='nodes':springs = (((0.,),(0.,),(1.,),1.),)*4
    elif problem=='order':springs = (((0.,0.),(0.,.1),(1.,1.),1.),)*4
    else:springs = ((*axis[:3],0.),)*4
    with pytest.raises((ValueError,ZeroDivisionError)):
        unsprung_normal_parameters((4e4,)*4,(5e3,)*2,(2e5,)*4,.2,True,(0.,)*4,
                                   (1800.,)*4,(2400.,)*4,springs,dampers,None)
