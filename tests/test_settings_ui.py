"""多层级游戏设置持久化、实时生效与界面导航测试。"""

import json

import pytest
from direct.gui.DirectGuiBase import DirectGuiWidget

from application import CoastalDrive
from chase_camera import ChaseCamera
from session import Phase
from settings import AudioSettingsStore, GameSettingsStore


def test_game_settings_store_roundtrip_presets_rebind_and_fallback(tmp_path):
    path = tmp_path / "game-settings.json"
    store = GameSettingsStore(path)
    assert store.graphics_preset == "high"
    assert store.key_preset == "wasd"
    assert store.fov == 68 and store.camera_distance == 11.0

    # 画质预设联动 + 修改单项切回 custom
    assert store.apply_graphics_preset("ultra")
    assert (store.shadow_quality, store.msaa_samples, store.view_distance) == ("ultra", 8, "ultra")
    assert store.graphics_preset == "ultra"
    store.shadow_quality = "medium"
    assert store.graphics_preset == "custom"

    # 改键冲突自动互换与保留键拦截
    ok, swapped = store.rebind_key("throttle", "s")
    assert ok and swapped == "brake"
    assert store.key_bindings["throttle"] == "s" and store.key_bindings["brake"] == "w"
    assert store.key_preset == "custom"
    blocked, swapped = store.rebind_key("throttle", "escape")
    assert not blocked and swapped is None

    # 持久化重读
    store.fov = 74
    store.speed_unit = "mph"
    store.show_key_hints = False
    store.pause_on_focus_loss = False
    assert store.save()
    reloaded = GameSettingsStore(path)
    assert reloaded.fov == 74 and reloaded.speed_unit == "mph"
    assert not reloaded.show_key_hints and not reloaded.pause_on_focus_loss
    assert reloaded.key_bindings["throttle"] == "s" and reloaded.key_bindings["brake"] == "w"

    # 单分类恢复默认不影响其他分类
    assert reloaded.reset_category("controls")
    assert reloaded.key_preset == "wasd" and reloaded.fov == 74 and reloaded.speed_unit == "mph"

    # 损坏与非法值回退
    path.write_text("not json", encoding="utf-8")
    damaged = GameSettingsStore(path)
    assert damaged.notice and damaged.fov == 68
    path.write_text(json.dumps({"window_mode": "invalid", "fov": 999, "speed_unit": "knots"}), encoding="utf-8")
    clamped = GameSettingsStore(path)
    assert clamped.window_mode == "windowed" and clamped.fov == 82 and clamped.speed_unit == "kmh" and clamped.notice


def test_audio_settings_extended_channels_keep_legacy_compatibility(tmp_path):
    path = tmp_path / "audio.json"
    path.write_text(json.dumps({"master_volume": 80, "effects_volume": 70, "music_volume": 40, "radio_station": 2}),
                    encoding="utf-8")
    legacy = AudioSettingsStore(path)
    assert not legacy.notice
    assert (legacy.engine_volume, legacy.ui_volume, legacy.mute_unfocused) == (100, 100, False)

    assert legacy.save(80, 70, 40, 2, engine_volume=60, ui_volume=50, mute_unfocused=True)
    reloaded = AudioSettingsStore(path)
    assert (reloaded.engine_volume, reloaded.ui_volume, reloaded.mute_unfocused) == (60, 50, True)


def test_chase_camera_respects_base_fov_and_dynamic_fov():
    from types import SimpleNamespace

    car = SimpleNamespace(position=(0.0, 0.0, 0.0), heading=0.0, speed=45.0, acceleration=0.0)
    cam = ChaseCamera(base_fov=74.0, dynamic_fov=False)
    cam.update(car, 11.0, 1.0, snap=True)
    assert cam.fov == pytest.approx(74.0)
    cam.configure(dynamic_fov=True)
    for _ in range(30):
        cam.update(car, 11.0, 0.1)
    assert cam.fov > 77.5


@pytest.mark.ui
def test_multilevel_settings_navigation_rebinding_hud_and_pause_return(tmp_path, monkeypatch):
    app = CoastalDrive(smoke=True, output=tmp_path, load_initial_scene=False)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    try:
        app.back_to_menu()
        app.refresh_panel()
        base_widgets = len(DirectGuiWidget.guiDict)

        # 从首页打开多层级设置，默认落在大类 graphics / 子页 display
        app.choose_settings()
        sp = app.settings_panel
        assert sp.visible and sp.category == "graphics" and sp.subsections["graphics"] == 0
        assert not sp.audio_preview_active

        # Tab 切换二级子分页：display -> quality -> camera
        app.key_down("tab")
        app.key_up("tab")
        assert sp.subsections["graphics"] == 1
        app.key_down("tab")
        app.key_up("tab")
        assert sp.subsections["graphics"] == 2
        # 调整基础 FOV（68 -> 70）并验证立即生效到 ChaseCamera
        app.key_down("arrow_right")
        app.key_up("arrow_right")
        assert app.game_settings.fov == 70
        assert app.chase_camera.base_fov == 70.0

        # E 切到声音大类：应激活实时电台试听
        app.key_down("e")
        app.key_up("e")
        assert sp.category == "audio" and sp.audio_preview_active

        # E 切到操作大类，进入驾驶键位，交互重绑油门为 'i'
        app.key_down("e")
        app.key_up("e")
        assert sp.category == "controls"
        app.key_down("arrow_down")
        app.key_up("arrow_down")
        app.key_down("enter")
        app.key_up("enter")
        assert sp.listening_action == "throttle"
        app.key_down("i")
        app.key_up("i")
        assert sp.listening_action is None
        assert app.game_settings.key_bindings["throttle"] == "i"
        assert app._translate_drive_key("i") == "w"

        # Tab 到驾驶辅助子页，主菜单中可切换 ABS
        app.key_down("tab")
        app.key_up("tab")
        app.key_down("tab")
        app.key_up("tab")
        assert sp.subsections["controls"] == 2
        abs_before = app.session.abs_enabled
        app.key_down("enter")
        app.key_up("enter")
        assert app.session.abs_enabled is (not abs_before)

        # E 切到游戏与界面，切换车速单位为 mph 并验证 HUD 更新
        app.key_down("e")
        app.key_up("e")
        assert sp.category == "gameplay"
        app.key_down("arrow_down")
        app.key_up("arrow_down")
        app.key_down("arrow_right")
        app.key_up("arrow_right")
        assert app.game_settings.speed_unit == "mph"
        assert app.hud.speed_unit_label.getText() == "mph"
        assert app.hud.coastal.speed_unit_label.getText() == "mph"
        assert app.hud.career.speed_unit_label.getText() == "mph"

        # 4:3 与 16:9 尺寸变化下均可重绘且关闭后零控件泄漏
        orig_aspect = app.getAspectRatio()
        monkeypatch.setattr(app, "getAspectRatio", lambda: 4 / 3)
        sp.resize(4 / 3)
        monkeypatch.setattr(app, "getAspectRatio", lambda: orig_aspect)
        sp.resize(orig_aspect)

        # 恢复当前大类默认
        sp.reset_current_category()
        assert app.game_settings.speed_unit == "kmh"
        assert app.hud.speed_unit_label.getText() == "km/h"

        # Esc 返回主菜单，无控件泄漏
        app.key_down("escape")
        app.key_up("escape")
        assert not sp.visible and not app.audio_settings_page
        assert not app.main_menu.root.isHidden()
        assert len(DirectGuiWidget.guiDict) == base_widgets

        # 暂停态下进入设置：驾驶辅助应锁定不可改，Esc 返回暂停页
        app.session.phase = Phase.PAUSED
        app.refresh_panel()
        pause_widgets = len(DirectGuiWidget.guiDict)
        app.choose_settings("controls", subsection=2)
        abs_paused = app.session.abs_enabled
        app.key_down("enter")
        app.key_up("enter")
        assert app.session.abs_enabled is abs_paused
        assert "主菜单" in sp.feedback_notice
        app.key_down("escape")
        app.key_up("escape")
        assert not sp.visible and app.session.phase == Phase.PAUSED
        assert len(DirectGuiWidget.guiDict) == pause_widgets
    finally:
        app.close_game()
