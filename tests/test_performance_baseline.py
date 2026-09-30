"""启动性能时间线只记录观测，不改变游戏状态。"""

import pytest

from performance_baseline import StartupTrace


def test_startup_trace_keeps_process_and_stage_durations():
    stamps = iter((2_000_000_000, 2_500_000_000, 3_000_000_000))
    trace = StartupTrace(1_000_000_000, clock_ns=lambda: next(stamps))
    trace.mark("window_initialized")
    trace.mark("first_rendered_frame")
    trace.mark("main_menu_usable")
    report = trace.finish()

    assert report["time_to_first_frame_s"] == 1.5
    assert report["time_to_menu_usable_s"] == 2.0
    assert report["timeline"][1] == {
        "event": "window_initialized", "since_process_start_s": 1.0, "since_previous_s": 1.0
    }
    with pytest.raises(RuntimeError, match="时间线已经结束"):
        trace.mark("ignored_after_finish")
    assert len(trace.events) == 4


def test_transition_trace_without_process_start_has_only_stage_gaps():
    stamps = iter((10, 20))
    trace = StartupTrace(clock_ns=lambda: next(stamps))
    trace.mark("drive_transition_started")
    trace.mark("traffic_vehicles_loaded")
    report = trace.finish()

    assert report["time_to_first_frame_s"] is None
    assert report["time_to_menu_usable_s"] is None
    assert report["timeline"][1]["since_previous_s"] == 0.0
