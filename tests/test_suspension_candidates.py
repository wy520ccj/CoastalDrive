"""高速第3333拍的真实候选漏检与单子步完整机械回归。"""

import json
from pathlib import Path

import pytest
from panda3d.core import Quat, TransformState, Vec3

from simulation import Simulation
from suspension import SuspensionInput
from suspension_contacts import cylinder_suspension_rays
from suspension_kinematics import SupportPlane
from tire_coupling import ContactFrame
from tire_drivetrain import advance_drivetrain
from vehicle_config import CAR
from vehicle_parameters import load_vehicle_config
from vehicle_suspension import WorldSurface
from wheel_dynamics import Mobility

DATA = Path(__file__).parent / 'data/highway-contact-r11'


def tuples(value):
    if isinstance(value, list):
        return tuple(tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: tuples(item) for key, item in value.items()}
    return value


def test_real_road_face_remains_a_candidate_without_query_cache():
    record = tuples(json.loads((DATA / 'input.json').read_text(encoding='utf-8')))
    query = record['query']
    sim = Simulation(record['seed'], track='highway', traffic_count=0)
    try:
        hit, = cylinder_suspension_rays(sim._world, sim.player._chassis, query['rays'], query['axes'],
            query['radius'], query['width'], query['shoulder'], query['crown'], ray_origin=query['ray_origin'],
            envelope=sim.player.suspension.envelope)
        assert hit is not None
        assert hit.node.getName() == 'highway-road'
        assert hit.normal == (0., 0., 1.)
        assert hit.point[2] + query['ray_origin'][2] == pytest.approx(hit.node.getShape(0).getMargin(), abs=1e-12)
    finally:
        sim.close()


def test_saved_four_wheel_substep_keeps_support_and_vertical_momentum():
    record = tuples(json.loads((DATA / 'input.json').read_text(encoding='utf-8')))
    config = load_vehicle_config(DATA / 'config.json', CAR)
    rear = load_vehicle_config(DATA / 'rear-config.json', CAR)
    sim = Simulation(record['seed'], track='highway', traffic_count=0)
    try:
        pose = record['solver_chassis']
        sim.player._chassis.setTransform(TransformState.makePosQuatScale(
            Vec3(*pose['position']), Quat(*pose['orientation']), Vec3(1)))
        planes = []
        for values in record['planes']:
            surface = WorldSurface(**values.pop('surface'), world=sim._world, chassis=sim.player._chassis,
                                   envelope=sim.player.suspension.envelope)
            planes.append(SupportPlane(**values, surface=surface))
        system = SuspensionInput(**record['suspension'], config=config, kinematics=tuple(planes))
        arguments = record['arguments']
        frames = []
        for values in arguments.pop('frames'):
            values['mobility'] = Mobility(**values['mobility'])
            frames.append(ContactFrame(**values))
        result = advance_drivetrain(**arguments, frames=tuple(frames), config=config, rear_config=rear, suspension=system)
        assert result.suspension_system.touching == (True,) * 4
        assert all(force > 0. for force in result.suspension.axial_force)
        # 自由速度已含外载；这里独立核对真实轮胎/悬架冲量与车身竖向动量变化。
        dt = arguments['dt']
        impulse = dt * sum(force * gradient[2] for force, gradient in
                           zip(result.suspension.axial_force, result.suspension_system.gradients))
        impulse += dt * sum(wheel.fx * frame.tangent[2] + wheel.fy * frame.axle[2]
                            for wheel, frame in zip(result.wheels, frames))
        momentum = config.mass * (result.velocity[2] - arguments['velocity'][2])
        assert momentum == pytest.approx(impulse, rel=0., abs=1e-12)
    finally:
        sim.close()
