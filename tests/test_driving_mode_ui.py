"""驾驶模式设置边界与菜单/HUD的直接交互，不改变原主菜单动作。"""
import json

import pytest
from panda3d.core import TextNode

from application import CoastalDrive
from driving_modes import DrivingMode
from session import Phase
from settings import DrivingModeStore
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
def test_menu_mode_selection_and_hud_text(tmp_path, height):
    app = CoastalDrive(smoke=True, output=tmp_path, render_size=(round(height * 16 / 9), height))
    app.taskMgr.remove("finish-smoke")
    try:
        app.session.menu()
        app.refresh_panel()
        assert len(app.main_menu.actions) == len(app.main_menu.buttons) == 6
        assert [b["text"] for b in app.main_menu.buttons] == [
            "计时挑战", "滨海自由驾驶", "无限高速", "车库", "声音设置", "退出"]
        old_world = app.session.simulation
        app.messenger.send("f2")
        assert app.driving_mode_page and app.panel_option_count == 6
        assert [b["text"] for b in app.buttons[:6]] == [
            "正常游戏", "困难仿真", "车辆 ABS：开启", "驱动防滑 TCS：开启", "横摆稳定 ESC：开启", "返回"]
        note_bottom = app.panel_note.getTightBounds(app.panel)[0].z
        assert note_bottom > app.buttons[0].getZ() + app.buttons[0]["frameSize"][3]
        app.key_down("arrow_down")
        app.key_up("arrow_down")
        app.key_down("enter")
        app.key_up("enter")
        assert app.session.driving_mode == DrivingMode.SIMULATION
        assert app.session.simulation is old_world
        assert DrivingModeStore(tmp_path / "test-driving-mode.json").mode == DrivingMode.SIMULATION
        app.toggle_abs()
        assert not app.session.abs_enabled and app.session.simulation is old_world
        assert not DrivingModeStore(tmp_path / "test-driving-mode.json").abs_enabled
        assert app.buttons[2]["text"] == "车辆 ABS：关闭"
        app.toggle_tcs()
        assert not app.session.tcs_enabled and app.session.simulation is old_world
        assert not DrivingModeStore(tmp_path / "test-driving-mode.json").tcs_enabled
        assert app.buttons[3]["text"] == "驱动防滑 TCS：关闭"
        app.toggle_esc()
        assert not app.session.esc_enabled and app.session.simulation is old_world
        assert not DrivingModeStore(tmp_path / "test-driving-mode.json").esc_enabled
        assert app.buttons[4]["text"] == "横摆稳定 ESC：关闭"
        app.toggle_abs()
        blocked = tmp_path / "blocked-settings"
        blocked.write_text("not a directory", encoding="utf-8")
        original_path = app.driving_mode_settings.path
        app.driving_mode_settings.path = blocked / "driving-mode.json"
        app.set_driving_mode(DrivingMode.SIMULATION)
        assert app.driving_mode_settings.notice
        assert app.panel_note.getTightBounds(app.panel)[0].z > (
            app.buttons[0].getZ() + app.buttons[0]["frameSize"][3]
        )
        app.driving_mode_settings.path = original_path
        app.set_driving_mode(DrivingMode.SIMULATION)
        app.key_down("escape")
        app.key_up("escape")
        assert not app.driving_mode_page and not app.main_menu.root.isHidden()
        assert "困难仿真" in app.main_menu.driving_mode_button["text"]
        corner = TextNode("mode-corner-width")
        corner.setFont(app.ui_font)
        assert corner.calcWidth(app.main_menu.driving_mode_button["text"]) * .04 <= .76
        app.choose_garage()
        for _ in range(3):
            app.cycle_garage_model()
        assert app.garage_model_id == "reference-fwd"
        app.apply_garage()
        assert app.vehicle_model_id == "reference-fwd"
        assert app.session.base_vehicle_config is vehicle_design("reference-fwd").config
        assert app.session.simulation is old_world
        app.session.start(countdown=False)
        assert app.session.simulation is not old_world
        assert app.session.simulation.config.front_drive_share == 1.
        app.session.phase = Phase.DRIVING
        app.choose_driving_mode()
        assert not app.driving_mode_page
        app.set_driving_mode(DrivingMode.GAME)
        assert app.session.driving_mode == DrivingMode.SIMULATION
        app.hud.update(app.session.frame(0), app.session.race.snapshot, app.session.highway.snapshot,
                       track=app.session.simulation.track, countdown="", notice="",
                       driving_mode=app.session.driving_mode)
        assert "Q 倒挡 / E 前进挡" in app.hud.help.getText()
        assert "刹车·倒车" not in app.hud.help.getText()
        assert "ABS待命 TCS关闭 ESC关闭" in app.hud.help.getText()
        app.toggle_abs()
        assert app.session.abs_enabled
        # 按实际字体宽度检验两行提示及角落入口落在既有底板内。
        for line in app.hud.help.getText().splitlines():
            node = TextNode("mode-help-width")
            node.setFont(app.ui_font)
            assert node.calcWidth(line) * .027 <= 1.5
        assert "刹车·倒车" in driving_help(DrivingMode.GAME)
    finally:
        app.close_game()
