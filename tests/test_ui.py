from dataclasses import replace

from panda3d.core import TextNode

from application import CoastalDrive
from race import GameMode
from session import Phase


def test_ui_modes_results_and_existing_keys(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    try:
        app.session.menu()
        app.refresh_panel()
        assert not app.main_menu.root.isHidden()
        assert app.panel.isHidden()
        assert [button["text"] for button in app.main_menu.buttons] == [
            "计时挑战", "滨海自由驾驶", "无限高速", "车库", "声音设置", "退出",
        ]
        app.key_down("enter")
        assert app.session.mode == GameMode.TIME_TRIAL
        app.key_up("enter")
        app.session.phase = Phase.DRIVING
        app.key_down("escape")
        assert app.session.phase == Phase.PAUSED
        app.key_up("escape")
        app.refresh_panel()
        assert app.panel_title.getText() == "已暂停"
        app.key_down("enter")
        assert app.session.phase == Phase.DRIVING
        app.key_up("enter")

        app.session.race.snapshot = replace(
            app.session.race.snapshot, finished=True, last_lap=87.123, best_lap=87.123,
        )
        app.session.phase = Phase.RESULTS
        app.refresh_panel()
        assert app.panel_title.getText() == "挑战成功"
        app.session.race.snapshot = replace(
            app.session.race.snapshot, invalidated=True, invalid_reason="错过检查点",
        )
        app._shown_phase = None
        app.refresh_panel()
        assert app.panel_title.getText() == "挑战失败"
        assert "错过检查点" in app.panel_note.getText()

        app.start_game(mode=GameMode.FREE_DRIVE)
        app.session.finish()
        app._shown_phase = None
        app.refresh_panel()
        assert app.panel_title.getText() == "驾驶结束"
        assert app.buttons[0]["text"].startswith("重新出发")
        app.start_game(mode=GameMode.DISTANCE_CHALLENGE, track="endless")
        app.session.highway.snapshot = replace(
            app.session.highway.snapshot, finished=True, succeeded=True,
            reason="完成 5 公里无碰撞挑战", distance=5000, elapsed=123.4,
        )
        app.session.phase = Phase.RESULTS
        app._shown_phase = None
        app.refresh_panel()
        assert app.panel_title.getText() == "挑战成功"
        app.session.highway.snapshot = replace(
            app.session.highway.snapshot, succeeded=False,
            reason="车辆复位后本次五公里无碰撞挑战结束，请返回菜单重新开始，再次驾驶需要从起点出发",
        )
        app._shown_phase = None
        app.refresh_panel()
        assert app.panel_title.getText() == "挑战失败"
        assert "车辆复位" in app.panel_note.getText()
        probe = TextNode("test-ui-width")
        probe.setFont(app.ui_font)
        for line in app.panel_note.getText().split("\n"):
            probe.setText(line)
            assert probe.getWidth() * 0.040 <= 1.37

        app.session.menu()
        app.choose_audio_settings()
        app.audio_settings.notice = "声音设置保存失败，请检查当前目录的写入权限后重试。"
        app._shown_phase = None
        app.refresh_panel()
        assert app.panel_title.getText() == "设置"
        assert "声音设置保存失败" in app.panel_note.getText()
        app.back_from_audio_settings()
        app.choose_garage()
        app.appearance.notice = "车辆外观设置保存失败，请检查当前目录的写入权限后重试。"
        app._shown_phase = None
        app.refresh_panel()
        assert app.panel_title.getText() == "车库"
        assert "车辆外观设置保存失败" in app.panel_note.getText()
    finally:
        app.close_game()


def test_keyboard_navigation_for_secondary_menus(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    try:
        app.session.menu()
        app.refresh_panel()
        app.key_down("s")
        assert app.main_menu.selected == 1
        app.key_up("s")

        app.choose_garage()
        original_model = app.garage_model_id
        original_skin = app.garage_skin_index
        app.key_down("w")
        assert app.panel_selection == 2
        app.key_up("w")
        app.key_down("d")
        assert app.garage_skin_index != original_skin
        app.key_up("d")
        app.key_down("w")
        app.key_up("w")
        app.key_down("w")
        app.key_up("w")
        app.key_down("a")
        assert app.garage_model_id != original_model
        app.key_up("a")
        app.key_down("escape")
        assert app.garage is None
        app.key_up("escape")

        app.choose_audio_settings()
        master = app.audio_settings.master_volume
        app.key_down("arrow_right")
        assert app.audio_settings.master_volume == min(100, master + 10)
        app.key_up("arrow_right")
        app.key_down("s")
        app.key_up("s")
        app.key_down("arrow_left")
        assert app.audio_settings.master_volume == max(0, min(100, master + 10) - 10)
        app.key_up("arrow_left")
        app.key_down("s")
        app.key_up("s")
        effects = app.audio_settings.effects_volume
        app.key_down("d")
        assert app.audio_settings.effects_volume == min(100, effects + 10)
        app.key_up("d")
        app.select_panel_option(4)
        music = app.audio_settings.music_volume
        app.key_down("a")
        app.key_up("a")
        assert app.audio_settings.music_volume == max(0, music - 10)
        app.select_panel_option(5)
        app.key_down("d")
        app.key_up("d")
        assert app.audio_settings.radio_station == 2
        app.toggle_radio()
        assert app.audio_settings.radio_station == 0
        app.toggle_radio()
        assert app.audio_settings.radio_station == 2
        app.key_down("escape")
        assert not app.audio_settings_page
        app.key_up("escape")

        app.choose_highway()
        app.key_down("w")
        app.key_up("w")
        density = app.highway_density_index
        app.key_down("a")
        assert app.highway_density_index == (density - 1) % len(app.highway_density_keys)
        app.key_up("a")
        app.key_down("escape")
        assert not app.highway_menu
        app.key_up("escape")

        app.session.start(mode=GameMode.FREE_DRIVE)
        app.session.pause()
        app._shown_phase = None
        app.refresh_panel()
        app.key_down("s")
        app.key_up("s")
        assert app.panel_selection == 1
        app.key_down("enter")
        assert app.audio_settings_page
        assert app.panel_title.getText() == "设置"
        assert app.session.phase == Phase.PAUSED
        app.key_up("enter")
        tick = app.session.current.tick
        for _ in range(10):
            app.session.frame(.1)
        assert app.session.current.tick == tick
        before = app.audio_settings.music_volume
        app.select_panel_option(4)
        app.key_down("a")
        app.key_up("a")
        assert app.audio_settings.music_volume == max(0, before - 10)
        app.key_down("escape")
        app.key_up("escape")
        assert not app.audio_settings_page and app.session.phase == Phase.PAUSED
        assert app.panel_selection == 1
        app.key_down("s")
        app.key_up("s")
        app.key_down("enter")
        assert app.session.phase == Phase.COUNTDOWN
        app.key_up("enter")
        app.session.finish()
        app._shown_phase = None
        app.refresh_panel()
        app.key_down("s")
        app.key_up("s")
        assert app.panel_selection == 1
        app.key_down("enter")
        assert app.session.phase == Phase.MENU
        app.key_up("enter")
    finally:
        app.close_game()


def test_radio_key_repeat_does_not_skip_station_or_desync_label(tmp_path):
    from test_soundscape import make_soundscape

    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    app.soundscape, _ = make_soundscape()
    try:
        app.back_to_menu()
        app.key_down("n")
        app.key_down("n")
        assert app.audio_settings.radio_station == 2
        assert app.soundscape.music.station == 2
        app.key_up("n")
        app.key_down("n")
        assert app.audio_settings.radio_station == 0
        assert app.soundscape.music.station == 0
    finally:
        app.close_game()
