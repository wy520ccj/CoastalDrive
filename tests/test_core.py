import json
import math
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from controls import ConstantController, KeyboardController
from session import FixedStepper, Phase, Session
from simulation import FIXED_DT, CarState, Control, Simulation, forward, heading_for, interpolate
from vehicle_config import CAR


def driving():
    session = Session(17)
    session.start(countdown=False)
    session.frame(0)
    return session


def test_render_rates_use_identical_simulation():
    results = []
    for fps in (30, 60, 144):
        session = driving()
        session.set_controller(ConstantController(Control(0.15, 0.6)))
        for _ in range(10 * fps):
            session.frame(1 / fps)
        assert session.current.tick == 1200
        results.append(session.current)
        session.close()
    assert results[0] == results[1] == results[2]


def test_headless_ten_thousand_steps_without_renderer_imports():
    src = Path(__file__).resolve().parents[1] / "src"
    code = """
import sys
from simulation import Simulation, Control
s=Simulation(9)
for _ in range(10000): s.step(Control(throttle=.5))
assert s.snapshot().tick==10000
# Phase 2 may import panda3d.bullet/core; the display application must stay absent.
assert not any(n.startswith(('direct.showbase','direct.gui','application','scene')) for n in sys.modules)
s.close();s.close()
print('HEADLESS_OK')
"""
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=src, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "HEADLESS_OK" in result.stdout


def test_headless_cli_from_another_directory(tmp_path):
    main = Path(__file__).resolve().parents[1] / "src/main.py"
    result = subprocess.run(
        [sys.executable, str(main), "--headless", "--steps", "10000"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["tick"] == 10000


def test_seed_repeatability_and_restart():
    s = Simulation(5, track="highway", traffic_count=2)
    initial = s.snapshot()

    def run():
        for _ in range(300):
            s.step(Control(0.1, 0.4))
        return s.snapshot()

    first = run()
    s.reset(5)
    assert s.snapshot() == initial
    assert run() == first
    s.reset(6)
    s.step(Control())
    other = s.snapshot().traffic
    s.reset(5)
    s.step(Control())
    assert s.snapshot().traffic != other


def test_stepper_drop_and_fractional_remainder():
    stepper = FixedStepper()
    ticks = []
    assert stepper.advance(0.25, lambda: ticks.append(1)) == 8
    assert len(ticks) == 8
    assert stepper.dropped_time == pytest.approx(22 * FIXED_DT)
    assert stepper.remainder == pytest.approx(0)
    stepper.advance(FIXED_DT / 2, lambda: ticks.append(1))
    assert len(ticks) == 8
    stepper.advance(FIXED_DT / 2, lambda: ticks.append(1))
    assert len(ticks) == 9


@pytest.mark.parametrize("dt", [-1, float("inf"), float("nan")])
def test_invalid_frame_time(dt):
    with pytest.raises(ValueError):
        FixedStepper().advance(dt, lambda: None)


def test_snapshot_has_no_mutable_state_and_interpolation_does_not_write_back():
    s = Simulation()
    before = s.snapshot()
    with pytest.raises(FrozenInstanceError):
        before.player.speed = 10
    with pytest.raises(TypeError):
        before.player.position[0] = 0
    s.step(Control(throttle=1))
    after = s.snapshot()
    rendered = interpolate(before, after, 0.5)
    assert before.tick == 0
    assert rendered.player.position[1] == pytest.approx(after.player.position[1] / 2)
    assert s.snapshot() == after


@pytest.mark.parametrize("heading", [0, 30, -30, 90, -90, 180])
def test_forward_matches_real_panda_heading(heading):
    from panda3d.core import NodePath

    node = NodePath("orientation-test")
    node.setH(heading)
    assert forward(heading) == pytest.approx(tuple(node.getQuat().getForward()), abs=1e-6)
    x, y, _ = forward(heading)
    assert abs((heading_for(x, y) - heading + 180) % 360 - 180) < 1e-8


def test_right_steering_and_reverse_direction():
    s = Simulation(track="test")
    for _ in range(240):
        s.step(Control())
    for _ in range(360):
        s.step(Control(1, 0.5))
    assert s.snapshot().player.position[0] > 97
    assert s.snapshot().player.heading < -30
    s.reset()
    for _ in range(240):
        s.step(Control())
    for _ in range(360):
        s.step(Control(1, brake=1))
    car = s.snapshot().player
    assert car.speed < 0
    assert car.heading > 30


def test_brake_stops_before_reverse_and_beats_throttle(monkeypatch):
    s = Simulation()
    for _ in range(240):
        s.step(Control())
    for _ in range(240):
        s.step(Control(throttle=1))
    previous = s.snapshot().player.speed
    wheel_energy = sum(.5 * CAR.wheel_inertia * wheel.omega**2
                       for wheel in s.snapshot().player.wheel_dynamics)
    previous_capacity = s.player.powertrain.capacity
    previous_throttle = s.player.powertrain.throttle
    train = s.player.powertrain
    accept_step = train.accept_step
    shaft_steps = []

    def observe_shaft(result, dt):
        # 完整制动建立期间，逐子步独立核对输入轴角冲量，不把惯性传矩当作离合未释放。
        shaft_steps.append((train.shaft_omega, result.shaft_omega, dt,
                            result.clutch_torque, result.gear_reaction))
        accept_step(result, dt)

    monkeypatch.setattr(train, "accept_step", observe_shaft)
    s.step(Control(throttle=1, brake=1))
    assert s.snapshot().player.throttle == 0
    assert s.snapshot().player.brake > 0
    assert s.player.powertrain.throttle < previous_throttle
    expected = max(0., previous_capacity - CAR.clutch_capacity * FIXED_DT / CAR.clutch_release_time)
    assert s.player.powertrain.capacity == pytest.approx(expected, rel=0, abs=1e-11)
    # 首拍发动机/转子可继续传能；制动优先核对请求和真实有限释放，不强清轴速或转矩。
    assert abs(train.clutch_torque) <= train.capacity + 1e-9
    from driver_assist import GAME_INPUT

    for _ in range(round(1 / GAME_INPUT.brake_rise / FIXED_DT) - 1):
        s.step(Control(throttle=1, brake=1))
    assert s.snapshot().player.brake == pytest.approx(1)
    assert 0 < s.snapshot().player.speed < previous
    monkeypatch.setattr(train, "accept_step", accept_step)
    assert train.capacity == train.clutch_torque == 0
    for start, end, dt, clutch, gear in shaft_steps:
        assert CAR.input_shaft_inertia * (end - start) == pytest.approx(dt * (clutch - gear), abs=1e-11)
    # 离合断开后输入轴仍在减速，齿轮反力携带该轴储能；不强清驱动矩。
    assert shaft_steps[-1][1] < shaft_steps[-1][0]
    assert train.drive_torque > 0
    assert sum(.5 * CAR.wheel_inertia * wheel.omega**2
               for wheel in s.snapshot().player.wheel_dynamics) < wheel_energy
    for _ in range(1200):
        if abs(s.snapshot().player.speed) < 0.15:
            break
        s.step(Control(brake=1))
    else:
        pytest.fail("Car did not stop within ten seconds")
    for _ in range(40):
        s.step(Control(brake=1))
    assert abs(s.snapshot().player.speed) < 0.2
    assert s.snapshot().player.gear > 0
    # 先独立核对0.4s等待，随后从真正挂入倒挡开始计半秒起步。
    # 有限制动响应会影响释放瞬态，不能把剩余等待混进倒挡加速时间。
    wait_ticks = round(GAME_INPUT.reverse_delay / FIXED_DT)
    for tick in range(40, wait_ticks):
        s.step(Control(brake=1))
        if tick < wait_ticks - 1:
            assert s.snapshot().player.gear > 0
    assert s.player.powertrain.pending_gear == -1
    # 输入等待已完成；实际零容量挡位按现有卸载/停留时间切换，再计半秒倒车。
    dwell_ticks = math.ceil((CAR.shift_time-CAR.clutch_engage_time) / FIXED_DT)
    for _ in range(dwell_ticks):
        if s.snapshot().player.gear == -1:
            break
        assert s.player.powertrain.capacity == 0
        s.step(Control(brake=1))
    assert s.snapshot().player.gear == -1
    initial_reverse_pressure = s.player.brakes.states[0].pressure
    for _ in range(60):
        s.step(Control(brake=1))
    assert s.snapshot().player.speed < -0.5
    assert s.player.brakes.states[0].pressure < initial_reverse_pressure


def test_aliases_opposed_directions_and_priority():
    k = KeyboardController()
    k.press("w")
    k.press("arrow_up")
    k.release("w")
    assert k.sample(None, FIXED_DT).throttle == 1
    k.press("s")
    k.press("a")
    k.press("d")
    assert k.sample(None, FIXED_DT) == Control(brake=1)
    k.clear()
    assert k.sample(None, FIXED_DT) == Control()


def test_pause_focus_and_resume_drop_wall_time():
    s = driving()
    s.keyboard.press("w")
    s.frame(1 / 30)
    before = s.current
    s.focus_changed(False)
    assert s.phase == Phase.PAUSED
    for _ in range(600):
        s.frame(1 / 60)
    assert s.current == before
    assert s.keyboard.sample(None, FIXED_DT) == Control()
    s.focus_changed(True)
    assert s.phase == Phase.PAUSED
    s.resume()
    s.frame(10)
    assert s.current == before
    s.frame(FIXED_DT)
    assert s.current.tick == before.tick + 1
    assert s.stepper.dropped_time == 0


def test_countdown_freezes_car_and_pauses():
    s = Session()
    s.start()
    s.frame(0)
    s.keyboard.press("w")
    for _ in range(60):
        s.frame(1 / 60)
    assert s.current.tick == 0 and s.countdown_ticks == 240
    s.pause()
    s.frame(10)
    s.resume()
    s.frame(10)
    assert s.countdown_ticks == 240
    for _ in range(120):
        s.frame(1 / 60)
    assert s.phase == Phase.DRIVING
    assert s.current.tick == 0
    assert not s.keyboard.pressed


def test_twenty_restarts_reset_all_owned_state():
    s = driving()
    initial = s.current
    for _ in range(20):
        s.keyboard.press("w")
        s.frame(0.05)
        s.reset_player()
        assert not s.keyboard.pressed
        assert s.current.events == ("player_reset",)
        s.start(countdown=False)
        assert s.current == initial
        assert s.previous == initial
        assert not s.keyboard.pressed
        assert s.stepper.dropped_time == 0
        s.frame(0)


def test_switching_controller_clears_keyboard_input():
    s = driving()
    s.keyboard.press("w")
    s.set_controller(ConstantController(Control(brake=1)))
    assert not s.keyboard.pressed
    s.frame(FIXED_DT)
    s.set_controller(s.keyboard)
    assert s.controller.sample(None, FIXED_DT) == Control()


def test_menu_result_states_freeze_simulation():
    s = driving()
    s.keyboard.press("w")
    s.frame(0.05)
    before = s.current
    s.finish()
    s.frame(5)
    assert s.current == before and s.phase == Phase.RESULTS
    s.menu()
    s.frame(5)
    assert s.current == before and s.phase == Phase.MENU


@pytest.mark.parametrize("control", [{"steering": 2}, {"brake": -1}, {"throttle": float("nan")}])
def test_control_boundary(control):
    with pytest.raises(ValueError):
        Control(**control)


def test_fixed_step_contract_and_closed_world():
    s = Simulation()
    with pytest.raises(ValueError):
        s.step(Control(), 0.1)
    s.close()
    s.close()
    with pytest.raises(RuntimeError):
        s.step(Control())


def test_angle_interpolation_takes_short_arc():
    from dataclasses import replace

    state = Simulation().snapshot()
    a = replace(state, player=CarState((0, 0, 0), 179))
    b = replace(state, player=CarState((0, 0, 0), -179))
    assert math.isclose(interpolate(a, b, 0.5).player.heading, 180)


def test_resource_root_ignores_working_directory(tmp_path, monkeypatch):
    from paths import resource_root, user_data

    actual = resource_root()
    monkeypatch.chdir(tmp_path)
    assert resource_root() == actual
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert user_data() == tmp_path / "CoastalDrive"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "packaged/game.exe"))
    assert resource_root() == tmp_path / "packaged"
