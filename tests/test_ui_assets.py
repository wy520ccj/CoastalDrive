from dataclasses import replace
from types import SimpleNamespace

from application import CoastalDrive
from race import GameMode
from session import Phase


def test_menu_navigation_and_overlay_lifecycle(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    try:
        app.session.menu()
        app.refresh_panel()
        frozen = app.session.current
        app.key_down("arrow_down")
        app.key_down("arrow_down")  # 按住只移动一次，沿用去重规则。
        assert app.main_menu.selected == 1
        assert app.session.current == frozen
        app.key_up("arrow_down")
        app.key_down("enter")
        app.key_up("enter")
        app.refresh_panel()
        assert app.session.mode == GameMode.FREE_DRIVE
        assert app.main_menu.root.isHidden()
        assert not app.hud.root.isHidden()
        app.session.phase = Phase.DRIVING
        app.session.pause()
        app.refresh_panel()
        assert app.hud.root.isHidden()
        assert not app.panel.isHidden()
        app.session.resume()
        app.refresh_panel()
        assert not app.hud.root.isHidden()
        assert app.panel.isHidden()
        app.session.menu()
        app.refresh_panel()
        # DirectButton 的同一命令也用于鼠标点击，不增加另一套游戏动作。
        app.main_menu.buttons[2]["command"]()
        assert app.highway_menu
        assert app.main_menu.root.isHidden()
        app.back_to_modes()
        app.main_menu.buttons[3]["command"]()
        assert app.garage is not None
        assert app.main_menu.root.isHidden()
        app.cancel_garage()
        assert not app.main_menu.root.isHidden()
        app.main_menu.buttons[4]["command"]()
        before = app.audio_settings.master_volume
        app.buttons[0]["command"]()
        assert app.audio_settings.master_volume == max(0, before - 10)
        assert str(app.audio_settings.master_volume) in app.panel_note.getText()
        app.back_from_audio_settings()
        app.main_menu.select(0)
        app.main_menu.activate()
        assert app.session.mode == GameMode.TIME_TRIAL
    finally:
        app.close_game()


def test_hud_consumes_snapshots_and_keeps_critical_notices(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    try:
        state = replace(app.session.current, player=replace(
            app.session.current.player, speed=-10, gear=-1, rpm=3500,
        ))
        race = replace(app.session.race.snapshot, mode=GameMode.TIME_TRIAL,
                       elapsed=123.456, checkpoints=2, next_checkpoint=3,
                       invalidated=True, invalid_reason="错过检查点")
        app.hud.update(state, race, app.session.highway.snapshot, track="coastal",
                       countdown="3 秒后开始", notice="电台：夜驰 FM · Midnight Circuit · 请返回赛道")
        assert app.speed.getText() == "036"
        assert app.hud.gear.getText() == "R"
        assert "123.456" in app.status.getText()
        assert "2 / 4" in app.hud.detail.getText()
        assert "检查点 3" in app.hud.detail.getText()
        assert all(t in app.status_notice.getText() for t in ("3 秒后开始", "请返回赛道", "错过检查点"))
        assert app.status_notice.textNode.getWidth() * .034 <= .801
        assert "\n" in app.status_notice.textNode.getWordwrappedText()
        assert state.player.speed == -10 and race.elapsed == 123.456
        app.session.menu()
        app.update(SimpleNamespace(cont=None))
        assert app.hud.root.isHidden()
    finally:
        app.close_game()
