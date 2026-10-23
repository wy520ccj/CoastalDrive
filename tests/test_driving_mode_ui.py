"""驾驶模式设置边界与菜单/HUD的直接交互，不改变原主菜单动作。"""
import json

import pytest
from direct.gui.DirectGuiBase import DirectGuiWidget
from panda3d.core import TextNode

from application import CoastalDrive
from driving_modes import DrivingMode
from session import Phase
from settings import AudioSettingsStore, DrivingModeStore
from ui.hud import driving_help
from vehicle_designs import vehicle_design


def test_mode_store_roundtrip_and_invalid_user_data(tmp_path):
    path = tmp_path / "driving-mode.json"
    store = DrivingModeStore(path)
    assert store.mode == DrivingMode.GAME and store.abs_enabled and store.tcs_enabled
    assert store.save(DrivingMode.SIMULATION, False, False)
    restored = DrivingModeStore(path)
    assert restored.mode == DrivingMode.SIMULATION and not restored.abs_enabled and not restored.tcs_enabled
    assert restored.save(DrivingMode.GAME, False, False)
    assert not DrivingModeStore(path).abs_enabled and not DrivingModeStore(path).tcs_enabled
    assert restored.save(DrivingMode.SIMULATION)
    assert not DrivingModeStore(path).abs_enabled and not DrivingModeStore(path).tcs_enabled
    path.write_text(json.dumps({"mode": "simulation"}), encoding="utf-8")
    assert DrivingModeStore(path).abs_enabled
    path.write_text(json.dumps({"mode": "simulation", "abs_enabled": 0}), encoding="utf-8")
    assert DrivingModeStore(path).abs_enabled and DrivingModeStore(path).notice
    assert not (tmp_path / "appearance.json").exists()
    for data in ([], {"mode": "unknown"}, {"mode": None}):
        path.write_text(json.dumps(data), encoding="utf-8")
        restored = DrivingModeStore(path)
        assert restored.mode == DrivingMode.GAME and restored.notice
    path.write_text("broken json", encoding="utf-8")
    assert DrivingModeStore(path).notice
    with pytest.raises(TypeError):
        store.save("simulation")
    with pytest.raises(TypeError):
        store.save(DrivingMode.GAME, "off")


def test_mode_store_save_failure_reports_notice(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    store = DrivingModeStore(blocked / "driving-mode.json")
    assert not store.save(DrivingMode.SIMULATION)
    assert store.notice


@pytest.mark.parametrize("height", [700, 1080])
def test_game_ignores_stale_direct_mode_and_menu_only_changes_electronics(tmp_path, height):
    path = tmp_path / "test-driving-mode.json"
    path.write_text(json.dumps({"mode": "simulation", "abs_enabled": True,
                               "tcs_enabled": True, "esc_enabled": True}), encoding="utf-8")
    app = CoastalDrive(smoke=True, output=tmp_path, render_size=(round(height * 16 / 9), height))
    app.taskMgr.remove("finish-smoke")
    try:
        app.session.menu()
        app.refresh_panel()
        assert app.session.driving_mode is DrivingMode.GAME
        assert app.session.simulation.input_config is DrivingMode.GAME.input_config
        assert [b["text"] for b in app.main_menu.buttons] == [
            "计时挑战", "滨海自由驾驶", "海岸生涯", "我的车库", "声音设置", "退出游戏", "专家试验台", "驾驶辅助  F2"]
        old_world = app.session.simulation
        app.messenger.send("f2")
        assert app.driving_mode_page and app.panel_option_count == 4
        assert [b["text"] for b in app.buttons[:4]] == ["开启", "开启", "开启", "Esc   返回首页"]
        assert app.driving_cards.active and app.panel_note.isHidden()
        assert app.buttons[0].getX() == app.buttons[1].getX() == app.buttons[2].getX()
        assert app.buttons[0].getZ() > app.buttons[1].getZ() > app.buttons[2].getZ()
        app.key_down("enter")
        app.key_up("enter")
        assert not app.session.abs_enabled and app.session.simulation is old_world
        assert DrivingModeStore(path).mode is DrivingMode.GAME
        assert not DrivingModeStore(path).abs_enabled
        app.toggle_tcs()
        app.toggle_esc()
        assert not app.session.tcs_enabled and not app.session.esc_enabled
        assert [b["text"] for b in app.buttons[:3]] == ["关闭", "关闭", "关闭"]
        app.toggle_abs()
        blocked = tmp_path / "blocked-settings"
        blocked.write_text("not a directory", encoding="utf-8")
        original_path = app.driving_mode_settings.path
        app.driving_mode_settings.path = blocked / "driving-mode.json"
        app.toggle_abs()
        assert app.driving_mode_settings.notice
        app.driving_mode_settings.path = original_path
        app.toggle_abs()
        app.key_down("escape")
        app.key_up("escape")
        assert not app.driving_mode_page and not app.main_menu.root.isHidden()
        corner = TextNode("mode-corner-width")
        corner.setFont(app.ui_font)
        assert corner.calcWidth(app.main_menu.driving_mode_button["text"]) * .04 <= .76
        app.choose_garage()
        for _ in range(3):
            app.cycle_garage_model()
        assert app.garage_model_id == "reference-fwd"
        app.apply_garage()
        assert app.session.base_vehicle_config is vehicle_design("reference-fwd").config
        assert app.session.simulation is old_world
        app.session.start(countdown=False)
        assert app.session.simulation is not old_world
        assert app.session.simulation.config.front_drive_share == 1.
        app.session.phase = Phase.DRIVING
        app.choose_driving_mode()
        assert not app.driving_mode_page
        app.hud.update(app.session.frame(0), app.session.race.snapshot, app.session.highway.snapshot,
                       track=app.session.simulation.track, countdown="", notice="",
                       driving_mode=app.session.driving_mode)
        assert "刹车·倒车" in app.hud.help.getText()
        assert "ABS待命 TCS关闭 ESC关闭" in app.hud.help.getText()
        for line in app.hud.help.getText().splitlines():
            node = TextNode("mode-help-width")
            node.setFont(app.ui_font)
            assert node.calcWidth(line) * .027 <= 1.5
        assert "刹车·倒车" in driving_help(DrivingMode.GAME)
    finally:
        app.close_game()


def test_settings_cards_adjust_save_return_without_retaining_widgets(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        app.back_to_menu()
        app.refresh_panel()
        snapshot, world = app.session.current, app.session.simulation
        widget_count = len(DirectGuiWidget.guiDict)
        app.choose_audio_settings()
        assert app.panel_option_count == 8
        for minus, plus, name in ((0, 1, 'master_volume'), (2, 3, 'effects_volume'), (4, 5, 'music_volume')):
            before = getattr(app.audio_settings, name)
            app.buttons[minus]['command']()
            assert getattr(app.audio_settings, name) == before-10
            app.buttons[plus]['command']()
            assert getattr(app.audio_settings, name) == before
        music = app.audio_settings.music_volume
        app.select_panel_option(4)
        app.adjust_panel_option(-1)
        assert app.audio_settings.music_volume == music-10
        app.adjust_panel_option(1)
        app.select_panel_option(0)
        app.key_down('arrow_down')
        app.key_up('arrow_down')
        assert app.panel_selection == 2
        app.key_down('arrow_down')
        app.key_up('arrow_down')
        assert app.panel_selection == 4
        app.select_panel_option(6)
        station = app.audio_settings.radio_station
        app.adjust_panel_option(1)
        restored = AudioSettingsStore(app.audio_settings.path)
        assert restored.radio_station == station+1
        assert restored.music_volume == music
        app.buttons[7]['command']()
        assert not app.audio_settings_page and not app.main_menu.root.isHidden()
        # 菜单装饰随普通节点移除，借用的原按钮返回panel，不能留在旧content中。
        app.choose_highway()
        app.choose_sprint_routes()
        app.handle_panel_key('escape')
        app.handle_panel_key('escape')
        assert len(DirectGuiWidget.guiDict) == widget_count
        assert all(button.getParent() == app.panel for button in app.buttons)
        assert app.session.current == snapshot and app.session.simulation is world
        app.session.phase = Phase.PAUSED
        app.refresh_panel()
        pause_count = len(DirectGuiWidget.guiDict)
        app.choose_audio_settings()
        app.buttons[7]['command']()
        assert app.session.phase == Phase.PAUSED and not app.audio_settings_page
        assert len(DirectGuiWidget.guiDict) == pause_count
    finally:
        app.close_game()
