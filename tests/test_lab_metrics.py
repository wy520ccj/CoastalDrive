"""独立解析轨迹核验工程指标及拒绝条件，真实快照核验采样阶段。"""

import math
from dataclasses import replace

import pytest

from lab_experiment import LabExperiment, LabOptions
from lab_metrics import mfdd, yaw_gain
from lab_signals import sample_signals
from vehicle_state import VehicleCommand


def braking_trace(deceleration=6.7):
    # 刻意让速度阈值落在采样之间，轨迹由解析解而非待测指标生成。
    times = [index/120 for index in range(math.ceil(27.13/deceleration*120)+1)]
    rows = [{"time": time, "horizontal_speed": max(0., 27.13-deceleration*time)} for time in times]
    positions = [(0., 27.13*min(time, 27.13/deceleration)
                  -.5*deceleration*min(time, 27.13/deceleration)**2, 2.+.1*time) for time in times]
    return rows, positions


def test_mfdd_recovers_distance_averaged_deceleration_and_ignores_vertical_motion():
    rows, positions = braking_trace()
    result = mfdd(rows, positions, "braking", "stopped")
    assert result["value"] == pytest.approx(6.7, abs=2e-5)
    assert result["window"]["start_s"] == pytest.approx(.2*27.13/6.7, abs=1e-12)
    assert result["window"]["end_s"] == pytest.approx(.9*27.13/6.7, abs=1e-12)
    for mode, reason in (("manual", "time_limit"), ("braking", "collision"), ("braking", "failed")):
        assert mfdd(rows, positions, mode, reason)["value"] is None
    assert mfdd(rows[:2], positions[:2], "braking", None)["value"] is None


def test_mfdd_refuses_reacceleration_inside_braking_interval():
    rows, positions = braking_trace()
    rows[180]["horizontal_speed"] = rows[179]["horizontal_speed"]+.2
    assert "增速" in mfdd(rows, positions, "split_braking", "stopped")["note"]


def test_yaw_gain_uses_actual_roadwheel_angle_and_right_turn_sign():
    rows = [{"time": index/120, "horizontal_speed": 20., "steering": 2.,
             "yaw": -3.*math.radians(2.)} for index in range(481)]
    result = yaw_gain(rows, "step_steer", .5, "time_limit")
    assert result["value"] == pytest.approx(3.)
    for row in rows:
        row["steering"] = -2.
        row["yaw"] *= -1
    assert yaw_gain(rows, "step_steer", .5, "time_limit")["value"] == pytest.approx(3.)
    assert yaw_gain(rows[:100], "step_steer", .5, None)["value"] is None
    rows[-1]["horizontal_speed"] = 21.
    assert yaw_gain(rows, "step_steer", .5, "time_limit")["value"] is None


def test_signals_pair_force_budget_with_force_phase_and_keep_undefined_contact():
    run = LabExperiment(LabOptions(duration=.1))
    try:
        player = run.current.player
        force = replace(player.wheel_dynamics[0], fx=3., fy=4., force_grip=4., sample_grip=999.,
                        road_support=True, force_contact_tick=17, sample_tick=18, alpha=.2)
        contact = replace(player.wheel_contacts[0], normal_load=321.)
        snapshot = replace(run.current, player=replace(player,
            wheel_dynamics=(force, *player.wheel_dynamics[1:]),
            wheel_contacts=(contact, *player.wheel_contacts[1:])))
        values = sample_signals(snapshot, VehicleCommand(), run.start_time)
        assert values["utilization_fl"] == 1.25  # 不夹到1，不使用sample_grip。
        assert values["sample_load_fl"] == 321. and values["alpha_fl"] == .2
        assert values["force_tick_fl"] == 17 and values["sample_tick_fl"] == 18
        force = replace(force, road_support=False, force_grip=0.)
        snapshot = replace(snapshot, player=replace(snapshot.player,
            wheel_dynamics=(force, *player.wheel_dynamics[1:]), velocity=(0., 0., 0.)))
        values = sample_signals(snapshot, VehicleCommand(), run.start_time)
        assert values["utilization_fl"] is None and values["beta"] is None
    finally:
        run.close()
