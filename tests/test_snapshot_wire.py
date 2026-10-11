"""完整会话快照与事件按原浮点位型传输，重复引用不重复编码。"""

import pickle
from dataclasses import replace

import pytest

from driving_modes import DrivingMode
from impact_events import ContactState, ImpactEvent
from session import Session
from session_process import _decode_frame, _encode_frame, _output
from simulation import Control
from snapshot_wire import decode_snapshots, encode_snapshots
from vehicle_designs import GR86_DESIGN


@pytest.mark.parametrize('mode',list(DrivingMode))
def test_frame_codec_preserves_complete_physics_events_rules_and_repeated_references(mode):
    session = Session(23,track='endless',road_shape='hills',driving_mode=mode,vehicle_config=GR86_DESIGN)
    try:
        session.start(countdown=False)
        for _ in range(4):
            session.simulation.step(Control(steering=.02,throttle=.3))
        session.sync_snapshots()
        output = _output(session)
        event = ImpactEvent(7,4,2,(3,4),'metal_barrier',123.,80.,3.,-0.,
                            (1.,-0.,2.),(.3,.4,.5),'front',2)
        contact = ContactState((3,4),'metal_barrier',4,123.,3.,-0.,
                               (1.,-0.,2.),(.3,.4,.5),'front',2)
        current = replace(output.current,impacts=(event,),contacts=(contact,))
        previous = replace(current,tick=3,time=current.time-1/120)
        output = replace(output,history=(previous,current),previous=previous,current=current,
                         impacts=(event,))
        restored = _decode_frame(_encode_frame(output))
        assert restored == output
        assert restored.previous is restored.history[0]
        assert restored.current is restored.history[1]
        # 逐记录重编码验证None、单精度读数、double位型及完整力学账没有变。
        assert encode_snapshots((restored.history,restored.impacts)) == encode_snapshots((output.history,output.impacts))
        assert pickle.loads(pickle.dumps(restored.current)) == current
        # 同拍不同对象不能按tick合并，避免把调用方的变化丢掉。
        different = replace(current,events=('不同同拍快照',))
        restored = _decode_frame(_encode_frame(replace(output,previous=different)))
        assert restored.previous.events == different.events
        assert restored.current.events == current.events
    finally:
        session.close()


def test_native_snapshot_codec_keeps_signed_zero_nan_and_epoch():
    session = Session(track='test',vehicle_config=GR86_DESIGN)
    try:
        state = replace(session.current,contact_epoch=99,
                        player=replace(session.current.player,speed=-0.,acceleration=float('nan')))
        restored = decode_snapshots(encode_snapshots((state,)))[0]
        assert restored.contact_epoch == 99
        assert encode_snapshots((restored,)) == encode_snapshots((state,))
        payload = _encode_frame(_output(session))
        with pytest.raises(ValueError,match='截断'):
            _decode_frame(payload[:5])
    finally:
        session.close()


def test_repeated_frame_transmits_no_duplicate_physics_and_cache_survives_eviction_and_restart():
    session = Session(track='test',vehicle_config=GR86_DESIGN)
    sent, received = {}, {}
    try:
        original = _output(session)
        first = _encode_frame(original,sent)
        assert _decode_frame(first,received) == original
        repeat = _encode_frame(original,sent)
        assert len(repeat)<len(first)/4
        restored = _decode_frame(repeat,received)
        assert restored.current is original.current or restored.current == original.current
        for index in range(40):
            session.simulation.step(Control(throttle=.3))
            session.sync_snapshots()
            output = _output(session)
            assert _decode_frame(_encode_frame(output,sent),received) == output
            assert len(sent)<=16 and len(received)<=16
            assert tuple(sent) == tuple(received)
        session.menu()
        session.start(seed=17,countdown=False)
        output = _output(session)
        restored = _decode_frame(_encode_frame(output,sent),received)
        assert restored.current == output.current and restored.current.tick==0
        assert restored.current.contact_epoch != original.current.contact_epoch
    finally:
        session.close()
