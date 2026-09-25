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
        assert app.panel_title.getText() == "COASTAL DRIVE"
        assert [button["text"] for button in app.buttons] == [
            "计时挑战  Enter", "滨海自由驾驶", "无限高速", "车库", "声音设置", "退出",
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
            assert probe.getWidth() * 0.040 <= 1.80

        app.session.menu()
        app.choose_audio_settings()
        app.audio_settings.notice = "声音设置保存失败，请检查当前目录的写入权限后重试。"
        app._shown_phase = None
        app.refresh_panel()
        assert app.panel_title.getText() == "声音设置"
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
