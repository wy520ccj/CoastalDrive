"""独立会话必须保持完整物理、暂停边界和真实相机查询。"""

import time
from collections import deque
from types import SimpleNamespace

import pytest

from controls import ConstantController
from driving_modes import DrivingMode
from race import GameMode
from session import Phase, Session
from session_clock import PRESENTATION_DELAY
from session_process import SessionProcess
from simulation import FIXED_DT, CarState, Control, Snapshot
from vehicle_designs import vehicle_design


@pytest.mark.parametrize('pending',[False,True])
def test_low_fps_frame_uses_new_reply_before_selecting_presentation_time(pending):
    """50ms绘制间隔仍应显示原33ms延迟的连续轨迹，不能一直停在上一帧回包位置。"""
    remote = SessionProcess.__new__(SessionProcess)
    older = Snapshot(120, 1., CarState((0., 20., .55)), ())
    fresh = tuple(Snapshot(tick, tick*FIXED_DT, CarState((0., 20*tick*FIXED_DT, .55)), ())
                  for tick in range(121, 131))
    sent = []
    remote.keyboard = SimpleNamespace(publish_input=lambda: None)
    remote.connection = SimpleNamespace(poll=lambda: False, send=sent.append)
    remote.process = SimpleNamespace(is_alive=lambda: True)
    remote.phase, remote.pending_frame = Phase.DRIVING, pending
    remote.history, remote.current = deque((older,), maxlen=12), older
    remote.received_impacts = []
    remote.output = SimpleNamespace(current=older, timeline_origin=0., dropped_time=0., dropped_epoch=0.)

    def receive_reply():
        remote.history.extend(fresh)
        remote.current = remote.output.current = fresh[-1]
        remote.pending_frame = False

    remote._finish_frame = receive_reply
    frame = remote.frame(.05, sampled_at=1.05+PRESENTATION_DELAY)
    assert sent == ([] if pending else [('frame', ())])
    assert frame.time == pytest.approx(1.05, abs=1e-12)
    assert frame.player.position[1] == pytest.approx(21., abs=1e-12)
    assert remote.current is fresh[-1]


class FailingController:
    def sample(self, state, dt):
        raise ValueError('权威控制器原始失败')


def test_receive_timeout_keeps_the_same_pending_request():
    remote = SessionProcess.__new__(SessionProcess)
    remote.pending_frame = True
    remote.connection = SimpleNamespace(poll=lambda timeout: False)
    with pytest.raises(TimeoutError, match='未返回结果'):
        remote._finish_frame()
    assert remote.pending_frame


def test_sector_practice_options_reach_physics_process(tmp_path, monkeypatch):
    from challenge_catalog import ROAD_CHALLENGES
    from sector_chase import CHASE_COURSES

    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    mode = GameMode.TIME_TRIAL
    remote = SessionProcess(track='coastal', driving_mode=DrivingMode.GAME)
    try:
        remote.start(mode=mode, countdown=False, challenge_spec=ROAD_CHALLENGES[mode],
                     sector_chase=True, practice_sector=2)
        remote.pause()
        status = remote.highway.snapshot.engineering
        assert status.chase == CHASE_COURSES[mode] and status.practice_sector == 2
        remote.finish()
        status = remote.highway.snapshot.engineering
        assert not status.result.official and not status.trace_path
    finally:
        remote.close()


@pytest.mark.parametrize('mode', [DrivingMode.GAME, DrivingMode.SIMULATION])
def test_autonomous_session_matches_local_completed_ticks_and_pause(mode):
    options = {'track':'test', 'driving_mode':mode,
               'vehicle_config':vehicle_design('gr86-2022-premium-6mt').config}
    local, remote = Session(17, **options), SessionProcess(17, **options)
    try:
        local.start(countdown=False)
        remote.start(countdown=False)
        remote.set_controller(ConstantController(Control(throttle=.3)))
        deadline = time.monotonic() + 10
        while remote.frame(0).tick < 12 and time.monotonic() < deadline:
            time.sleep(.005)
        remote.pause()
        assert remote.phase == Phase.PAUSED and remote.current.tick >= 12
        for _ in range(remote.current.tick):
            local.simulation.step(Control(throttle=.3))
        assert local.simulation.snapshot() == remote.current
        assert remote.frame(1) == remote.current
        start, end = (0, 0, 2), (0, -10, 2)
        assert tuple(local.simulation.camera_position(start, end)) == tuple(remote.camera_position(start, end, 0.))
        stopped = remote.current.tick
        remote.resume()
        deadline = time.monotonic() + 10
        while remote.frame(0).tick <= stopped and time.monotonic() < deadline:
            time.sleep(.005)
        remote.pause()
        assert remote.current.tick > stopped
        remote.menu()
        assert remote.phase == Phase.MENU
        remote.start(seed=23, countdown=False)
        assert remote.current.tick == 0
    finally:
        local.close()
        remote.close()
        remote.close()


def test_failed_authority_returns_original_error_and_closes_pending_request():
    remote = SessionProcess(track='test',driving_mode=DrivingMode.GAME,
                            vehicle_config=vehicle_design('gr86-2022-premium-6mt').config)
    try:
        remote.start(countdown=False)
        remote.set_controller(FailingController())
        deadline = time.monotonic()+5
        with pytest.raises(ValueError,match='权威控制器原始失败'):
            while time.monotonic()<deadline:
                remote.frame(0)
                time.sleep(.005)
        assert not remote.pending_frame
        remote.menu()
        assert remote.phase == Phase.MENU
        remote.set_controller(remote.keyboard)
        remote.start(countdown=False)
        deadline = time.monotonic()+5
        while remote.frame(0).tick < 4 and time.monotonic() < deadline:
            time.sleep(.005)
        assert remote.current.tick >= 4
    finally:
        remote.close()
    assert remote.closed
    assert remote.process._closed


def test_mode_switch_and_new_start_discard_old_history_and_keep_full_hard_traffic():
    remote = SessionProcess(track='highway',driving_mode=DrivingMode.GAME,physics_workers=0,
                            vehicle_config=vehicle_design('gr86-2022-premium-6mt').config)
    try:
        assert remote.simulation.traffic_models == ('TrafficVehicle',)*8
        remote.set_driving_mode(DrivingMode.SIMULATION)
        remote.start(seed=23,countdown=False)
        assert remote.simulation.traffic_models == ('Vehicle',)*8
        assert list(remote.history) == [remote.current]
        assert remote.current.tick == 0
        assert remote.vehicle_config.finite_drivetrain
        remote.menu()
        remote.set_driving_mode(DrivingMode.GAME)
        remote.start(seed=0,countdown=False)
        assert remote.simulation.traffic_models == ('TrafficVehicle',)*8
    finally:
        remote.close()


def test_switching_back_to_shared_keyboard_keeps_the_authoritative_controller_and_clears_input():
    remote = SessionProcess(track='test',driving_mode=DrivingMode.GAME)
    try:
        remote.start(countdown=False)
        remote.set_controller(ConstantController(Control(throttle=.3)))
        remote.keyboard.press('w')
        remote.set_controller(remote.keyboard)
        assert remote.controller is remote.keyboard
        assert remote.keyboard.input_word.value == 0
        remote.frame(0)
        time.sleep(.1)
        remote.pause()
        assert remote.current.player.throttle == 0
        remote.finish()
        snapshot = remote.highway.snapshot
        remote.retry_challenge_score()
        assert remote.phase == Phase.RESULTS and remote.highway.snapshot == snapshot
    finally:
        remote.close()
