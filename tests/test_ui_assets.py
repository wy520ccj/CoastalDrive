from dataclasses import replace
from types import SimpleNamespace

from direct.gui import DirectGuiGlobals as DGG

from application import CoastalDrive
from race import GameMode
from session import Phase


def test_menu_navigation_and_overlay_lifecycle(tmp_path, monkeypatch):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    try:
        app.session.menu()
        app.refresh_panel()
        cues = []
        monkeypatch.setattr(app, 'audio_cue', cues.append)
        app.main_menu.resize(4/3)
        app.messenger.send(DGG.B1PRESS+app.main_menu.buttons[3].guiId, [None])
        assert cues == ['confirm']
        app.main_menu.resize(app.getAspectRatio())
        frozen = app.session.current
        # 默认聚焦主线赛事；先向下到车库，再到自由驾驶，按住只移动一次。
        app.key_down("arrow_down")
        app.key_down("arrow_down")  # 按住只移动一次，沿用去重规则。
        assert app.main_menu.selected == 3
        assert app.session.current == frozen
        app.key_up("arrow_down")
        app.key_down("arrow_down")
        app.key_up("arrow_down")
        assert app.main_menu.selected == 1
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
        assert app.career_panel.page == 'board' and not app.career_panel.root.isHidden()
        assert not app.workshop_vehicle.buffer.isActive()
        app.career_action('exit')
        app.main_menu.buttons[3]["command"]()
        assert app.career_panel.page == 'garage' and app.career_garage_return == 'home'
        assert app.career_panel.buttons[-1]['text'] == '返回首页'
        app.career_action('garage-back')
        assert app.career_panel.root.isHidden() and app.main_menu.selected == 3
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
