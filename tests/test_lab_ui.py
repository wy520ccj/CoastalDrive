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
    assert app.entries["steer"].guiItem.getFocus()
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
def test_failed_initialization_clears_old_candidate_but_preserves_baseline(workbench, maneuver):
    app = workbench
    app.set_options(LabOptions(speed_kph=10, duration=1/120))
    app.start_experiment()
    app.toggle_pause()
    app.single_step()
    app.present_summary(app.run_state.summary())
    app.pin_baseline()
    baseline = app.baseline
    assert app.candidate_value.getText() != "—"
    app.set_options(LabOptions(maneuver=maneuver, speed_kph=18, duration=.1))
    app.start_experiment()
    assert app.run_state is None and app.record is None
    assert app.baseline is baseline
    assert app.status.getText() == "初始化失败"
    assert app.metric.getText() == app.candidate_value.getText() == "—"
    assert app.cursor_label.getText() == "t = —"
    assert app.scene.path_bounds is None
    assert "记录 → 导入工程模型" in app.notice.getText()
    assert all(plot.series == [baseline.samples] for plot in app.plots)
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
