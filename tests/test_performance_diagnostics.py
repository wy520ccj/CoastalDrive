"""性能诊断汇总必须按多次样本排序，避免用单次波动归因。"""

from performance.summarize_startup import summarize


def test_startup_summary_uses_medians_and_keeps_nested_scene_cost_separate():
    reports = []
    for menu, environment, drive in ((7.0, 5.0, 2.0), (8.0, 6.0, 2.5), (7.5, 5.5, 2.2)):
        reports.append({
            "time_to_menu_usable_s": menu,
            "drive_transition_s": drive,
            "timeline": [
                {"event": "process_start", "since_previous_s": None},
                {"event": "window_initialized", "since_previous_s": 0.5},
                {"event": "environment_assets_loaded", "since_previous_s": environment},
            ],
            "drive_transition": {"timeline": [
                {"event": "drive_transition_started", "since_previous_s": None},
                {"event": "environment_assets_loaded", "since_previous_s": drive},
            ]},
            "scene_stage_seconds": {
                "menu": {"build_slice": environment - 1.0, "add_environment": 1.0},
                "drive": {"build_slice": 0.2, "add_environment": drive - 0.2},
            },
        })

    result = summarize(reports)

    assert result["menu_usable_median_s"] == 7.5
    assert result["drive_transition_median_s"] == 2.2
    assert result["startup_stages"][0] == {
        "stage": "environment_assets_loaded", "median_s": 5.5
    }
    assert result["scene_substages"]["menu"][0] == {
        "stage": "build_slice", "median_s": 4.5
    }
