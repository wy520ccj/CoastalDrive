"""原完整电子控制逐位对照，保留冻结记录类型和所有反馈字段。"""

import random
import struct
from dataclasses import fields, is_dataclass, replace

import pytest
from panda3d.bullet import BulletRigidBodyNode
from panda3d.core import TransformState, Vec3
from vehicle_controls_reference import Brakes as ReferenceBrakes
from vehicle_controls_reference import StabilityControl as ReferenceStability
from vehicle_controls_reference import TractionControl as ReferenceTraction

from vehicle_brakes import Brakes
from vehicle_config import CAR
from vehicle_stability import StabilityControl
from vehicle_state import WheelContactState, WheelDynamicsState
from vehicle_traction import TractionControl


def encoded(value):
    if is_dataclass(value):
        return type(value), tuple((field.name, encoded(getattr(value, field.name))) for field in fields(value))
    if isinstance(value, tuple):
        return tuple(encoded(part) for part in value)
    if isinstance(value, float):
        return float, struct.pack('d', value)
    return type(value), value


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('response', [0., .025])
@pytest.mark.parametrize('continuous', [False, True])
@pytest.mark.parametrize('share', [0., .5, 1.])
def test_full_native_electronics_match_frozen_reference(enabled, response, continuous, share):
    config = replace(CAR, front_drive_share=share,
        braking=replace(CAR.braking, abs_enabled=enabled, response_time=response),
        traction=replace(CAR.traction, tcs_enabled=enabled),
        stability=replace(CAR.stability, esc_enabled=enabled, continuous_reference=continuous))
    old_brakes, brakes = ReferenceBrakes(config.braking), Brakes(config.braking)
    old_traction, traction = ReferenceTraction(config.traction, config.driven_wheels), TractionControl(config.traction, config.driven_wheels)
    old_stability, stability = ReferenceStability(config), StabilityControl(config)
    body = BulletRigidBodyNode('control-feedback')
    body.setMass(config.mass)
    body.setInertia(Vec3(600., 1600., 1700.))
    rng = random.Random(7301)
    for tick in range(80):
        body.setTransform(TransformState.makeHpr(Vec3(rng.uniform(-30, 30), rng.uniform(-8, 8), rng.uniform(-8, 8))))
        body.setLinearVelocity(Vec3(rng.uniform(-5, 5), rng.uniform(-50, 50), 0.))
        body.setAngularVelocity(Vec3(0., 0., rng.uniform(-1., 1.)))
        wheels = tuple(WheelDynamicsState(omega=rng.uniform(-160, 160),
            longitudinal_speed=rng.uniform(-50, 50), sample_support=rng.choice([True, False]),
            sample_tick=tick, steering=rng.uniform(-30, 30),
            rolling_radius=None if tick % 2 else rng.uniform(.29, .34)) for _ in range(4))
        contacts = tuple(WheelContactState(True, (-.8 if i % 2 else .8, 1.3 if i < 2 else -1.3, -.4),
            tuple(Vec3(.1, .2, 1.).normalized()), 3000., rng.uniform(0., 6000.), .2, .1, None,
            'grass' if i % 2 else 'asphalt') for i in range(4))
        requests = tuple(rng.choice([0, 0., .4, 1]) for _ in range(4))
        pedal, direction, braking = rng.choice([0, 0., .3, 1]), rng.choice([-1, 0, 1]), rng.choice([False, True])
        previous = brakes.states
        assert encoded(brakes.advance(requests, wheels, config.wheel_radius, 1/120)) == encoded(
            old_brakes.advance(requests, wheels, config.wheel_radius, 1/120))
        assert encoded(brakes.states) == encoded(old_brakes.states)
        assert all(new is not old for new, old in zip(brakes.states, previous))
        assert encoded(traction.advance(pedal, direction, braking, wheels, config.wheel_radius, 1/120)) == encoded(
            old_traction.advance(pedal, direction, braking, wheels, config.wheel_radius, 1/120))
        steering = rng.uniform(-30, 30)
        assert encoded(stability.advance(body, wheels, contacts, requests, steering, 1/120)) == encoded(
            old_stability.advance(body, wheels, contacts, requests, steering, 1/120))
