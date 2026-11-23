"""原完整预测逐位对照，并核对陀螺复用不越过一次共同解。"""

import copy
import pickle
from dataclasses import fields, is_dataclass

import numpy as np
import pytest
import test_unsprung_joint as joint_case
from lab_contact_prediction_reference import contact_prediction_reference
from test_finite_radial_contact import contact_case

import unsprung_joint
from unsprung_motion import FiniteSuspensionMotion
from vehicle_designs import REFERENCE_DESIGN


def assert_values(actual, expected):
    if is_dataclass(actual):
        for field in fields(actual):
            assert_values(getattr(actual,field.name),getattr(expected,field.name))
    elif isinstance(actual,np.ndarray):
        assert actual.dtype == expected.dtype
        assert actual.shape == expected.shape
        assert actual.tobytes() == expected.tobytes()
    elif isinstance(actual,(float,np.floating)):
        assert float(actual).hex() == float(expected).hex()
    elif isinstance(actual,(tuple,list)):
        assert len(actual) == len(expected)
        for a,b in zip(actual,expected):
            assert_values(a,b)
    else:
        assert actual == expected


@pytest.mark.parametrize("finite", [False,True])
@pytest.mark.parametrize("vertical", [-1e-5,-1e-11,-0.,0.,1e-11,1e-5])
def test_actual_finite_contact_predictions_match_former_full_formula(finite, vertical):
    world,ground,bump,context = contact_case()
    try:
        bias = np.array(((.01,-.02,.003),)*4)
        context.wheel_velocity_bias = bias
        if finite:
            context.finite_motion = FiniteSuspensionMotion(
                context.centers[0]-context.hardware.mechanical.wheel_arms[0],context.rotation,
                context.centers,np.array((.01,.02,-.01,-.02)),context.hardware.mechanical,bias,context.dt)
        reference = copy.copy(context)
        if finite:
            reference.finite_motion = copy.copy(context.finite_motion)
        velocity = np.zeros(16)
        velocity[1],velocity[2],velocity[3:6] = 5.,vertical,(.1,-.2,.3)
        assert_values(context.evaluate(velocity),contact_prediction_reference(reference,velocity))
    finally:
        world.removeRigidBody(bump)
        world.removeRigidBody(ground)


@pytest.mark.parametrize("finite", [False,True])
def test_identical_gyro_inputs_are_reused_only_within_one_joint_solve(monkeypatch, finite):
    original = unsprung_joint.native_gyro_impulse
    calls = []

    def gyro(inertia,angular,dt):
        calls.append(angular.tobytes())
        return original(inertia,angular,dt)

    def solve(*args,**kwargs):
        return unsprung_joint.solve_unsprung_joint(*args,**kwargs,native_body_gyro=True)

    monkeypatch.setattr(unsprung_joint,"native_gyro_impulse",gyro)
    monkeypatch.setattr(joint_case,"solve_unsprung_joint",solve)
    first = joint_case.solve(REFERENCE_DESIGN,finite_geometry=finite)[0]
    initial_calls = calls.copy()
    assert len(initial_calls) > 0
    assert len(initial_calls) == len(set(initial_calls))
    second = joint_case.solve(REFERENCE_DESIGN,finite_geometry=finite)[0]
    assert calls[len(initial_calls):] == initial_calls
    for result in (first,second):
        assert result.momentum_error < 1e-9
        assert result.force_error < 1e-5
        assert result.port_error < 1e-9
        assert abs(result.energy_error) < 3e-8
    def values(result):
        return {field.name:getattr(result,field.name) for field in fields(result)
                if field.name != "contact_geometry"}

    assert pickle.dumps(values(first),protocol=5) == pickle.dumps(values(second),protocol=5)
