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


def test_brake_stops_before_reverse_and_beats_throttle():
    s = Simulation()
    for _ in range(240):
        s.step(Control())
    for _ in range(240):
        s.step(Control(throttle=1))
    previous = s.snapshot().player.speed
    s.step(Control(throttle=1, brake=1))
    assert 0 < s.snapshot().player.speed < previous
    for _ in range(1200):
        if abs(s.snapshot().player.speed) < 0.15:
            break
        s.step(Control(brake=1))
    else:
        pytest.fail("Car did not stop within ten seconds")
    for _ in range(40):
        s.step(Control(brake=1))
    assert abs(s.snapshot().player.speed) < 0.2
    for _ in range(60):
        s.step(Control(brake=1))
    assert s.snapshot().player.speed < -0.5


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
