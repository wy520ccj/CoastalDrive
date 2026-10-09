"""数值进程边界必须保留浮点位型和记录结构，拒绝不完整或不匹配的数据。"""

import math
import random
import struct
from dataclasses import replace

import pytest
from physics_packet_kernels import decode, encode, layout

from physics_wire import _layout, from_bytes, input_bytes, result_bytes
from simulation import Control, Simulation
from vehicle_state import WheelDynamicsState
from vehicle_tire_step import TireAdvanceResult


def test_numeric_packet_preserves_double_bits_and_nested_container_types():
    rng = random.Random(713)
    numbers = [struct.unpack('<d',rng.randbytes(8))[0] for _ in range(4096)]
    numbers += [0.,-0.,math.inf,-math.inf]
    original = {'数值':tuple(numbers),'状态':[None,False,True,-2**63,2**63-1,'asphalt',''],
                '轮胎':WheelDynamicsState(omega=-0.,deformation_x=.123)}
    restored = from_bytes(encode(_layout,original))
    assert isinstance(restored['数值'],tuple)
    assert isinstance(restored['状态'],list)
    assert restored['状态'] == original['状态']
    assert restored['轮胎'] == original['轮胎']
    assert struct.pack('<d',restored['轮胎'].omega) == struct.pack('<d',-0.)
    assert [struct.pack('<d',value) for value in restored['数值']] == [struct.pack('<d',value) for value in numbers]


def test_complete_body_packet_uses_same_panda_pose_tensor_and_solver_result():
    sim = Simulation(track='coastal',traffic_count=0)
    try:
        sim.step(Control(throttle=.3,steering=.1))
        car = sim.player
        request = car.prepare_control(Control(throttle=.4,steering=-.2))
        stages = car.physics_stages(request,1/240,tire_substeps=1,complete_tires=True)
        original = next(stages)
        restored = replace(from_bytes(input_bytes(original)),config=original.config,world_source=original.world_source)
        assert tuple(restored.body.pose.getPos()) == tuple(original.body.pose.getPos())
        assert tuple(restored.body.pose.getQuat()) == tuple(original.body.pose.getQuat())
        assert restored.body.inverse_inertia == original.body.inverse_inertia
        result = original.solve()
        assert restored.solve() == result
        assert isinstance(result,TireAdvanceResult)
        assert from_bytes(result_bytes(result)) == result
        stages.close()
    finally:
        sim.close()


def test_truncation_version_layout_and_unknown_types_are_explicit_errors():
    payload = encode(_layout,WheelDynamicsState())
    for end in range(len(payload)):
        with pytest.raises(ValueError):
            from_bytes(payload[:end])
    with pytest.raises(ValueError,match='多余'):
        from_bytes(payload+b'\0')
    with pytest.raises(ValueError,match='版本'):
        from_bytes(b'BAD1'+payload[4:])
    with pytest.raises(ValueError,match='布局'):
        from_bytes(payload[:4]+b'\xff'*8+payload[12:])
    with pytest.raises(ValueError,match='类型'):
        from_bytes(payload[:12]+b'\xff')
    with pytest.raises(TypeError):
        encode(_layout,object())
    with pytest.raises(OverflowError):
        encode(_layout,2**63)
    recursive = []
    recursive.append(recursive)
    with pytest.raises(RecursionError):
        encode(_layout,recursive)


def test_packet_record_missing_fields_and_layout_mismatch_raise():
    incomplete = WheelDynamicsState.__new__(WheelDynamicsState)
    with pytest.raises(ValueError,match='缺字段'):
        encode(_layout,incomplete)
    with pytest.raises(ValueError):
        layout((WheelDynamicsState,),(),1)
    with pytest.raises(TypeError):
        layout((str,),(('x',),),1)
    other = layout((WheelDynamicsState,),(('omega',),),123)
    with pytest.raises(ValueError,match='布局'):
        decode(other,encode(_layout,WheelDynamicsState()))
