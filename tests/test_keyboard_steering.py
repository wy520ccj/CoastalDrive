"""键盘方向盘输入、真实齿条及倒挡链路；不改模拟车辆的机械参数。"""

import time

import pytest

from controls import KeyboardController
from driver_assist import GAME_INPUT, SIMULATION_INPUT, DriverAssist
from driving_modes import DrivingMode
from session import Phase
from session_process import SessionProcess
from simulation import FIXED_DT
from vehicle_designs import GR86_DESIGN
from vehicle_steering import SteeringRack


def test_simulation_short_tap_moves_a_small_fraction_of_the_steering_wheel():
    keyboard = KeyboardController(SIMULATION_INPUT)
    assist = DriverAssist(GR86_DESIGN,SIMULATION_INPUT)
    rack = SteeringRack(GR86_DESIGN)
    keyboard.press('d')
    peak = 0.
    for tick in range(72):
        if tick == 12:
            keyboard.release('d')
        control = keyboard.sample(None,FIXED_DT)
        command = assist.command(control,100/3.6,1,True,FIXED_DT)
        peak = max(peak,abs(rack.advance(command.steering,FIXED_DT)))
        if tick == 11:
            assert control.steering == pytest.approx(.12)
            assert command.steering == pytest.approx(4.)
    assert 0 < peak < 1.2
    assert keyboard.steering == 0.


def test_long_hold_still_reaches_the_original_full_lock_and_sampling_is_time_based():
    results = []
    for hz in (60,120,240):
        keyboard = KeyboardController(SIMULATION_INPUT)
        keyboard.press('a')
        for _ in range(hz//4):
            keyboard.sample(None,1/hz)
        results.append(keyboard.steering)
        for _ in range(2*hz):
            keyboard.sample(None,1/hz)
        assert keyboard.steering == -1.
        keyboard.clear()
        assert keyboard.steering == 0.
    assert results == pytest.approx([-.3]*3)
    normal = KeyboardController(GAME_INPUT)
    normal.press('d')
    assert normal.sample(None,FIXED_DT).steering == 1.


def test_manual_reverse_uses_q_then_throttle_in_the_actual_session_process():
    remote = SessionProcess(track='test',driving_mode=DrivingMode.SIMULATION,
                            vehicle_config=GR86_DESIGN,physics_workers=0)
    try:
        remote.start(countdown=False)
        remote.keyboard.press('q')
        remote.keyboard.press('w')
        deadline = time.monotonic()+8
        while time.monotonic()<deadline:
            remote.frame(0)
            if remote.current.tick >= 240:
                break
            time.sleep(.005)
        remote.pause()
        assert remote.phase is Phase.PAUSED
        assert remote.current.tick >= 240
        assert remote.current.player.gear == -1
        assert remote.current.player.speed < -.5
    finally:
        remote.close()


@pytest.mark.parametrize('mode', (DrivingMode.GAME,DrivingMode.SIMULATION))
def test_keys_reach_running_physics_even_when_the_window_stops_requesting_frames(mode):
    remote = SessionProcess(track='test',driving_mode=mode,vehicle_config=GR86_DESIGN)
    try:
        remote.start(countdown=False)
        remote.frame(0)
        deadline = time.monotonic()+5
        while remote.progress()[0] < 12 and time.monotonic() < deadline:
            time.sleep(.005)
        remote.keyboard.press('d')
        remote.keyboard.press('w')
        # 不调用frame：输入必须由权威时钟直接读取，不能等待下个绘制请求。
        time.sleep(.1)
        remote.pause()
        assert remote.current.player.steering > 0
        assert remote.current.player.throttle > 0
        assert remote.keyboard.input_word.value == 0
        remote.keyboard.press('a')
        remote.keyboard.press('arrow_left')
        remote.keyboard.release('a')
        assert remote.keyboard.input_word.value & 4
        remote.keyboard.release('arrow_left')
        assert remote.keyboard.input_word.value == 0
    finally:
        remote.close()
