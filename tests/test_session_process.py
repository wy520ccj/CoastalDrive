"""独立会话必须保持完整物理、暂停边界和真实相机查询。"""

import time

import pytest

from controls import ConstantController
from driving_modes import DrivingMode
from session import Phase, Session
from session_process import SessionProcess
from simulation import Control
from vehicle_designs import vehicle_design


class FailingController:
    def sample(self, state, dt):
        raise ValueError('权威控制器原始失败')


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
    finally:
        remote.close()
