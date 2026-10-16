"""时间轴与工作方式切换的所有权；真实图形另由lab_ui_check验证。"""

from types import SimpleNamespace

import pytest

from lab_application import VehicleLab
from lab_experiment import LabOptions
from ui.lab_widgets import LabOptionMenu


def test_menu_hover_does_not_shrink_hitbox_or_change_text_size():
    item = {"frameSize": (0, .60, -.04, .04), "text_scale": (.038, .038),
            "frameColor": (1, 1, 1, 1)}
    menu = {"highlightColor": (.85, .91, .91, 1)}
    class HoverMenu(dict):
        highlightedIndex = None

    fake = HoverMenu(menu)
    for _ in range(20):
        LabOptionMenu._highlightItem(fake, item, 2)
        assert fake.highlightedIndex == 2
        assert item["frameSize"] == (0, .60, -.04, .04)
        assert item["text_scale"] == (.038, .038)
        LabOptionMenu._unhighlightItem(fake, item, (1, 1, 1, 1))
        assert fake.highlightedIndex is None
    assert item["frameColor"] == (1, 1, 1, 1)


def test_programmatic_slider_events_do_not_pause_computation_and_user_scrub_does():
    shown = []
    run = SimpleNamespace(paused=False)
    fake = SimpleNamespace(_seeking=False, pointer_pressed=False,
        run_state=run, timeline={"value": .25}, show_sample=shown.append, playing=True)
    VehicleLab.seek(fake)
    assert not run.paused and shown == []
    fake.pointer_pressed = True
    VehicleLab.seek(fake)
    assert run.paused and shown == [30]
    assert not fake.playing


def test_switch_requests_exit_and_cleanup_releases_world_once():
    calls = []
    fake = SimpleNamespace(next_workspace=None, userExit=lambda: calls.append("exit"))
    VehicleLab.back_to_game(fake)
    assert fake.next_workspace == "game" and calls == ["exit"]
    fake = SimpleNamespace(_closed=False, taskMgr=SimpleNamespace(remove=lambda _: None),
        ignoreAll=lambda: None, run_state=SimpleNamespace(close=lambda: calls.append("world-close")),
        scene=SimpleNamespace(close=lambda: calls.append("scene-close")),
        root=SimpleNamespace(destroy=lambda: None), destroy=lambda: calls.append("window-close"))
    VehicleLab.close_game(fake)
    VehicleLab.close_game(fake)
    assert calls.count("world-close") == 1
    assert calls.index("world-close") < calls.index("window-close")


@pytest.fixture(scope="module")
def workbench(tmp_path_factory):
    app = VehicleLab(offscreen=True, output=tmp_path_factory.mktemp("lab-ui"))
    app.taskMgr.remove("lab-update")
    yield app
    app.close_game()


def test_shortcuts_use_actual_mouse_focus_and_ignore_hidden_entries(workbench):
    app = workbench
    app.blur_entries()
    entry = app.entries["speed"]
    # 鼠标点击只更新PGEntry，不回写DirectEntry的focus选项。
    entry.guiItem.setFocus(True)
    assert entry["focus"] == 0 and entry.guiItem.getFocus()
    calls = []
    app.hotkey(lambda: calls.append("step"))
    assert calls == []
    entry.hide()
    app.hotkey(lambda: calls.append("step"))
    assert calls == ["step"]
    entry.show()
    app.blur_entries()


def test_closing_advanced_releases_real_focus_and_tab_skips_hidden_fields(workbench):
    app = workbench
    app.toggle_advanced()
    app.entries["duration"].guiItem.setFocus(True)
    app.cycle_entry(1)
    assert app.entries["cg"].guiItem.getFocus()
    app.toggle_advanced()
    assert not any(entry.guiItem.getFocus() for entry in app.entries.values())
    app.cycle_entry(-1)
    assert app.entries["mu"].guiItem.getFocus()
    app.blur_entries()


def test_modal_blocks_shortcuts_and_closes_other_input_panel(workbench):
    app = workbench
    app.manual_panel.show()
    app.manual_entries["gear"].guiItem.setFocus(True)
    app.toggle_advanced()
    assert app.manual_panel.isHidden()
    assert not app.manual_entries["gear"].guiItem.getFocus()
    calls = []
    app.hotkey(lambda: calls.append("pause"))
    assert calls == []
    app.escape()
    assert app.advanced_panel.isHidden()
    app.hotkey(lambda: calls.append("pause"))
    assert calls == ["pause"]


def test_engineering_configuration_status_changes_with_vehicle(workbench):
    from pathlib import Path

    app = workbench
    path = Path(__file__).resolve().parents[1]/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json"
    app.import_engineering(path)
    assert app.engineered_config.unsprung_enabled
    assert app.configuration_note.getText() == "工程模型 · 独立轮心"
    config = app.engineered_config
    app.vehicle_menu.set(app.vehicle_menu.selectedIndex)
    assert app.engineered_config is config
    app.vehicle_menu.set(3)
    assert app.engineered_config is None and app.parameter_metadata is None
    assert app.configuration_note.getText() == "车型默认 · 无独立轮心"
    assert "已解除" in app.notice.getText()


@pytest.mark.parametrize("maneuver", ("ride_bump", "ride_braking"))
def test_missing_wheel_model_blocks_start_and_preserves_previous_result(workbench, maneuver):
    app = workbench
    app.set_options(LabOptions(speed_kph=10, duration=1/120))
    app.start_experiment()
    app.toggle_pause()
    app.single_step()
    app.present_summary(app.run_state.summary())
    app.pin_baseline()
    baseline = app.baseline
    run = app.run_state
    value = app.metric.getText()
    assert app.candidate_value.getText() != "—"
    app.set_options(LabOptions(maneuver=maneuver, speed_kph=18, duration=.1, onset=.025))
    assert not app.start_button.guiItem.getActive()
    app.start_experiment()
    assert app.run_state is run and not run.closed
    assert app.baseline is baseline
    assert app.metric.getText() == app.candidate_value.getText() == value
    assert "记录 → 导入工程模型" in app.notice.getText()
    app.clear_baseline()
    assert app.baseline_value.getText() == "—"
    assert "已清除基线" in app.notice.getText()


def test_focusing_entry_highlights_it_and_blur_restores_color(workbench):
    app = workbench
    entry = app.entries["duration"]
    color = entry["frameColor"]
    entry.guiItem.setFocus(True)
    app.taskMgr.step()
    assert entry["frameColor"] != color
    app.blur_entries()
    app.taskMgr.step()
    assert entry["frameColor"] == color


def test_numeric_focus_closes_window_ime_but_does_not_call_graphics_buffer_api(monkeypatch):
    import lab_application

    calls = []
    class NumericWindow:
        def closeIme(self):
            calls.append("close-ime")

    monkeypatch.setattr(lab_application, "GraphicsWindow", NumericWindow)
    entry = {"frameColor": (1, 1, 1, 1), "state": "normal"}
    fake = SimpleNamespace(win=NumericWindow(), focused_parameter=None)
    VehicleLab.focus_parameter(fake, "duration", entry)
    assert calls == ["close-ime"] and fake.focused_parameter == "duration"
    fake.win = object()
    VehicleLab.focus_parameter(fake, "manual.gear", entry)
    assert calls == ["close-ime"] and fake.focused_parameter == "manual.gear"


def test_menu_open_cancel_and_every_maneuver_release_old_focus(workbench):
    from lab_experiment import MANEUVERS

    app = workbench
    app.advanced_panel.show()
    for mode, label in MANEUVERS.items():
        entry = app.entries["duration"]
        entry.guiItem.setFocus(True)
        app.maneuver_menu.showPopupMenu()
        assert not entry.guiItem.getFocus()
        app.maneuver_menu.hidePopupMenu()
        entry.guiItem.setFocus(True)
        app.maneuver_menu.set(label)
        assert not entry.guiItem.getFocus()
        options = app.default_options(mode)
        assert float(entry.get()) == options.duration
        assert float(app.entries["speed"].get()) == options.speed_kph
        assert float(app.entries["onset"].get()) == options.onset
    app.advanced_panel.hide()


def test_clicking_already_focused_entry_prepares_window_again(monkeypatch, workbench):
    app = workbench
    calls = []
    monkeypatch.setattr(app, "focus_parameter", lambda key, entry: calls.append(key))
    app.entries["speed"].guiItem.setFocus(True)
    app.click_parameter("speed", app.entries["speed"])
    app.click_parameter("speed", app.entries["speed"])
    assert calls == ["speed", "speed"]
    app.blur_entries()


def test_reset_restores_all_fields_for_current_maneuver_and_preserves_engineering_and_results(workbench):
    from pathlib import Path

    from lab_records import LabRecord

    app = workbench
    app.set_options(LabOptions(speed_kph=10, duration=1/120))
    app.start_experiment()
    app.single_step()
    app.record = LabRecord.from_run(app.run_state)
    app.pin_baseline()
    assert app.record.samples and app.baseline.samples and app.run_state is not None
    app.import_engineering(Path(__file__).resolve().parents[1]/
        "docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
    app.maneuver_menu.set("单侧凸起 / 制动")
    config, metadata = app.engineered_config, app.parameter_metadata
    run, record, baseline = app.run_state, app.record, app.baseline
    for entry in (*app.entries.values(), *app.manual_entries.values()):
        entry.enterText("invalid")
    app.entries["duration"].guiItem.setFocus(True)
    app.reset_parameters()
    assert app.read_options() == app.default_options("ride_braking")
    assert app.entries["cg"].get() == app.entries["tire_load"].get() == ""
    assert {key: entry.get() for key, entry in app.manual_entries.items()} == {
        "throttle": "0", "brake": "0", "gear": "1", "clutch": "100"}
    assert app.engineered_config is config and app.parameter_metadata is metadata
    assert app.run_state is run and app.record is record and app.baseline is baseline
    assert not any(entry.guiItem.getFocus() for entry in app.entries.values())
    assert "重新开始" in app.notice.getText()
    app.engineered_config = app.engineered_vehicle_id = app.parameter_metadata = None
    app.refresh_configuration_note()
    app.clear_baseline()


def test_invalid_text_opens_chinese_banner_and_focuses_exact_field(workbench):
    app = workbench
    app.set_options(LabOptions())
    app.entries["duration"].enterText("22wd")
    app.start_experiment()
    assert not app.notice.root.isHidden() and not app.advanced_panel.isHidden()
    assert app.entries["duration"].guiItem.getFocus()
    assert app.entries["duration"].get() == "22wd"
    assert "时长须填写数字" in app.notice.getText()
    assert "could not" not in app.notice.getText()
    app.set_options(LabOptions())
    app.notice.dismiss()
    app.advanced_panel.hide()
    app.blur_entries()


def test_bad_manual_input_does_not_close_or_replace_existing_world(workbench):
    app = workbench
    app.set_options(LabOptions(speed_kph=10, duration=.1))
    app.start_experiment()
    app.toggle_pause()
    original = app.run_state
    app.set_options(LabOptions(maneuver="manual", duration=.1))
    app.manual_entries["throttle"].enterText("bad")
    app.start_experiment()
    assert app.run_state is original and not original.closed
    assert "油门" in app.notice.getText() and not app.manual_panel.isHidden()
    app.manual_entries["throttle"].enterText("0")
    original.close()
    app.run_state = None
    app.manual_panel.hide()
    app.notice.dismiss()


def test_single_candidate_is_b_and_loaded_replay_pauses_and_steps_without_physics(workbench, tmp_path):
    from lab_records import LabRecord, export_record

    app = workbench
    app.set_options(LabOptions(speed_kph=10, duration=.025))
    app.start_experiment()
    app.toggle_pause()
    for _ in range(3):
        app.single_step()
    app.refresh_plots()
    assert app.plots[0].labels == ["B"]
    assert " B " in app.plots[0].readout.getText()
    app.record = LabRecord.from_run(app.run_state)
    app.run_state.close()
    app.run_state = None
    export_record(app.record, tmp_path/"loaded")
    app.import_record(tmp_path/"loaded")
    assert "已保存试验模型" in app.model_note.getText()
    assert "已载入保存的试验" in app.notice.getText()
    app.show_sample(0)
    app.toggle_playback()
    assert app.playing
    app.toggle_pause()
    assert not app.playing
    app.single_step()
    assert app.run_state is None and app.view_index == 1
    assert app.playhead == app.record.samples[1]["time"]


@pytest.mark.parametrize("document", ([], {"schema": "vehicle-engineering-v1", "parameters": []}))
def test_malformed_engineering_files_keep_current_config_and_show_chinese(workbench, tmp_path, document):
    import json

    app = workbench
    config = app.engineered_config
    path = tmp_path/"wrong.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    app.import_engineering(path)
    assert app.engineered_config is config
    assert not app.notice.root.isHidden()
    assert "工程配置载入失败" in app.notice.getText()
    app.notice.dismiss()


def test_long_parameter_help_is_scrollable_and_preview_camera_works(workbench):
    app = workbench
    app.parameter_help.show("suspension_installation_curves")
    lower = app.parameter_help.notes.getTightBounds(app.parameter_help.content)[0].z
    assert app.parameter_help.content_scroll["canvasSize"][2] < lower
    app.scroll_parameter_help(1)
    assert app.parameter_help.content_scroll.verticalScroll["value"] > 0
    app.parameter_help.hide()
    app.run_state = None
    app.record = None
    previous = app.camera.getPos()
    app.cycle_camera()
    assert app.camera.getPos() != previous


@pytest.mark.parametrize("mode,extra", (
    ("braking", set()), ("split_braking", {"right_mu"}),
    ("step_steer", {"steer", "onset"}), ("circle", {"steer", "onset"}),
    ("sine_steer", {"steer", "onset"}), ("constant_radius", {"radius"}),
    ("double_lane_change", set()),
    ("manual", {"steer", "manual.throttle", "manual.brake", "manual.gear", "manual.clutch"}),
    ("ride_bump", {"bump_height", "bump_length", "bump_distance"}),
    ("ride_braking", {"bump_height", "bump_length", "bump_distance", "onset"}),
))
def test_maneuver_only_enables_consumed_fields_and_ignores_inactive_invalid_text(workbench, mode, extra):
    from lab_experiment import MANEUVERS
    from lab_inputs import COMMON_FIELDS

    app = workbench
    app.set_options(LabOptions())
    app.maneuver_menu.set(MANEUVERS[mode])
    expected = COMMON_FIELDS | extra
    for key, entry in (*app.entries.items(), *(("manual."+key, entry)
                        for key, entry in app.manual_entries.items())):
        assert entry.guiItem.getActive() == (key in expected)
        if key not in expected:
            entry.enterText("22wd")
    assert app.read_options() == app.default_options(mode)
    assert ("目标车速" in app.field_labels["speed"].getText()) == (mode in (
        "constant_radius", "double_lane_change"))
    app.set_options(LabOptions())


def test_inactive_field_rejects_focus_and_tab_but_switching_back_restores_editing(workbench):
    app = workbench
    app.set_options(LabOptions(maneuver="step_steer"))
    app.advanced_panel.show()
    app.entries["steer"].guiItem.setFocus(True)
    app.maneuver_menu.set("直线制动")
    app.taskMgr.step()
    assert not app.entries["steer"].guiItem.getFocus()
    app.focus_parameter("steer", app.entries["steer"])
    assert not app.entries["steer"].guiItem.getFocus()
    seen = set()
    for _ in range(10):
        app.cycle_entry(1)
        seen.update(key for key, entry in app.entries.items() if entry.guiItem.getFocus())
    assert seen == {"speed", "mu", "duration", "cg", "tire_load"}
    app.maneuver_menu.set("阶跃转向")
    app.entries["steer"]["focus"] = 1
    assert app.entries["steer"].guiItem.getFocus()
    app.blur_entries()
    app.advanced_panel.hide()


def test_active_onset_must_precede_end_but_unused_onset_does_not_block_start(workbench):
    from lab_inputs import LabInputError

    app = workbench
    app.set_options(LabOptions(maneuver="step_steer", duration=.5, onset=.5))
    with pytest.raises(LabInputError, match="输入起始须小于"):
        app.read_options()
    app.maneuver_menu.set("直线制动")
    app.entries["onset"].enterText("bad")
    assert app.read_options().maneuver == "braking"
    app.set_options(LabOptions())


def test_manual_initial_inputs_can_be_confirmed_before_creating_world(workbench):
    app = workbench
    if app.run_state is not None:
        app.run_state.close()
    app.run_state = None
    record, baseline = app.record, app.baseline
    app.set_options(LabOptions(maneuver="manual", speed_kph=10, duration=.025))
    assert not app.manual_button.isHidden()
    app.show_manual()
    assert not app.manual_panel.isHidden()
    app.manual_entries["throttle"].enterText("25")
    app.manual_entries["brake"].enterText("0")
    app.manual_entries["gear"].enterText("1")
    app.manual_entries["clutch"].enterText("100")
    app.apply_manual()
    assert app.run_state is None and app.record is record and app.baseline is baseline
    assert "初始执行器输入已确认" in app.notice.getText()
    app.start_experiment()
    assert app.run_state.manual_command.throttle == .25
    assert app.run_state.manual_command.gear == 1
    app.run_state.close()
    app.run_state = None
    app.manual_entries["throttle"].enterText("0")
    app.manual_panel.hide()
    app.set_options(LabOptions())


def test_no_finite_drivetrain_does_not_parse_gear_or_clutch_and_requests_forward(workbench):
    from lab_inputs import active_fields

    app = workbench
    app.manual_entries["gear"].enterText("unused")
    app.manual_entries["clutch"].enterText("unused")
    command = app.read_manual_command(SimpleNamespace(finite_drivetrain=False, steering_degrees=90.))
    assert command.gear is command.clutch is None and command.direction == 1
    assert "manual.gear" not in active_fields("manual", finite_drivetrain=False)
    app.reset_parameters()


def test_ab_only_subtracts_matching_maneuver_and_distance_definition(workbench):
    app = workbench
    summary = {"stopping_distance_m": 10., "distance_m": 10., "simulation_seconds": 1.,
               "compute_seconds": .1, "options": {"maneuver": "braking"}}
    baseline = app.baseline
    app.baseline = SimpleNamespace(metadata={"summary": summary})
    app.present_summary({**summary, "stopping_distance_m": 12.})
    assert "+2.00" in app.result.getText()
    app.present_summary({**summary, "stopping_distance_m": None})
    assert "仅并列展示" in app.result.getText()
    app.present_summary({**summary, "options": {"maneuver": "split_braking"}})
    assert "仅并列展示" in app.result.getText()
    app.baseline = baseline
