"""完整四轮准备/装配与冻结旧计算逐字段位型对照，不用轨迹容差掩盖差异。"""

import random
from dataclasses import fields, is_dataclass, replace

import pytest
from tire_publish_reference import reference_publish
from wheel_contact_kernels import tire_prepare_frames, tire_publish

from rotor_dynamics import cross, dot
from tire_compliance import deformation_frame
from tire_coupling import ContactFrame
from vehicle_config import CAR
from vehicle_state import WheelDynamicsState
from wheel_dynamics import Mobility, WheelStep


def exact(left, right):
    assert type(left) is type(right)
    if is_dataclass(left):
        for field in fields(left):
            exact(getattr(left, field.name), getattr(right, field.name))
    elif isinstance(left, tuple):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            exact(a, b)
    else:
        assert left.hex() == right.hex() if isinstance(left, float) else left == right


def test_complete_frame_geometry_and_responses_match_old_double_precision():
    rng = random.Random(64307)
    for _ in range(256):
        matrix = tuple(tuple(rng.uniform(-.001, .001) for _ in range(3)) for _ in range(3))
        raw = tuple((rng.uniform(-35, 35), bool(i % 2), float(i*2000), .7,
                     tuple(rng.uniform(-1, 1) for _ in range(3)),
                     tuple(rng.uniform(-1, 1) for _ in range(3)),
                     tuple(rng.uniform(-2, 2) for _ in range(3))) for i in range(4))
        actual = tire_prepare_frames(CAR, ContactFrame, Mobility, matrix, raw)
        for frame, (angle, supported, load, mu, tangent, normal, point) in zip(actual, raw):
            elastic = deformation_frame(tangent, normal)
            tangent, axle, normal = elastic
            hub = tuple(point[a] + normal[a]*CAR.wheel_radius for a in range(3))
            mx, my = cross(hub, tangent), cross(point, axle)
            rx, ry, rt = tuple(tuple(dot(row, vector) for row in matrix) for vector in (mx, my, axle))
            mobility = Mobility(1/CAR.mass+dot(mx, rx), dot(mx, ry), dot(mx, rt),
                                1/CAR.mass+dot(my, ry), dot(my, rt), dot(axle, rt))
            expected = ContactFrame(angle, supported, load, mu, tangent, axle, point, hub, mobility, elastic, rx, ry, rt)
            exact(frame, expected)


@pytest.mark.parametrize('tangent,normal', [((1., 0., 0.), (0., 0., 0.)), ((0., 0., 1.), (0., 0., 1.))])
def test_degenerate_frame_reports_original_arithmetic_failure(tangent, normal):
    with pytest.raises(ZeroDivisionError):
        deformation_frame(tangent, normal)
    matrix = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
    raw = ((0., True, 1., .7, tangent, normal, (0., 0., 0.)),)*4
    with pytest.raises(ZeroDivisionError):
        tire_prepare_frames(CAR, ContactFrame, Mobility, matrix, raw)


@pytest.mark.parametrize('rotor', [False, True])
@pytest.mark.parametrize('compliance', [False, True])
@pytest.mark.parametrize('accumulate', [False, True])
@pytest.mark.parametrize('reverse', [False, True])
def test_complete_publish_keeps_all_fields_types_and_actual_panda_impulses(rotor, compliance, accumulate, reverse):
    rng = random.Random(65001)
    config = replace(CAR, finite_drivetrain=True, wheel_rotor_transport=rotor, tire_compliance=compliance)
    rear = replace(config, mass=config.mass*1.1, longitudinal_stiffness=config.longitudinal_stiffness*.8)
    for turn in range(80):
        frames, steps, old = [], [], []
        for i in range(4):
            elastic = deformation_frame(tuple(rng.uniform(-1, 1) for _ in range(3)), (0., 0., 1.))
            tangent, axle, _normal = elastic
            point = tuple(rng.uniform(-2, 2) for _ in range(3))
            frames.append(ContactFrame(0 if i == 0 else rng.uniform(-35, 35), bool(i % 2), float(i*2000), .7,
                tangent, axle, point, point, Mobility(0., 0., 0., 0., 0., 0.), elastic,
                (0.,)*3, (0.,)*3, (0.,)*3, axle if rotor else None, config.wheel_radius if rotor else None))
            values = {field.name: rng.uniform(-100, 100) for field in fields(WheelStep)
                      if isinstance(getattr(WheelStep(0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., ''), field.name), float)}
            values.update(mode='static' if turn % 2 else 'airborne',
                          patch_kappa=.03, patch_alpha=None,
                          gyro_torque=tuple(rng.uniform(-100, 100) for _ in range(3)),
                          steering_torque=tuple(rng.uniform(-100, 100) for _ in range(3)))
            steps.append(WheelStep(**values))
            previous = WheelDynamicsState()
            history = {field.name: rng.uniform(-100, 100) for field in fields(previous)
                       if isinstance(getattr(previous, field.name), float)}
            history.update(gyro_angular_impulse=tuple(rng.uniform(-1, 1) for _ in range(3)),
                           steering_angular_impulse=tuple(rng.uniform(-1, 1) for _ in range(3)),
                           longitudinal_angular_impulse=tuple(rng.uniform(-1, 1) for _ in range(3)),
                           lateral_angular_impulse=tuple(rng.uniform(-1, 1) for _ in range(3)))
            old.append(replace(previous, **history))
        args = (config, rear, tuple(frames), tuple(steps), tuple(old),
                tuple(rng.uniform(-1000, 1000) for _ in range(4)), ((0., 0., 0.),)*4,
                tuple(rng.uniform(-1000, 1000) for _ in range(4)), (15.,)*4, (4.,)*4,
                tuple(rng.uniform(-3, 3) for _ in range(3)), 1/240, turn, accumulate, reverse)
        actual = tire_publish(WheelDynamicsState(), *args)
        exact(actual, reference_publish(*args))
