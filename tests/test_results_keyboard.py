"""通过已注册的键盘事件验证结算页导航及菜单切换边界。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from race import GameMode
from session import Phase


@pytest.mark.parametrize("mode,track", [
    (GameMode.TIME_TRIAL, "coastal"),
    (GameMode.FREE_DRIVE, "coastal"),
    (GameMode.DISTANCE_CHALLENGE, "endless"),
])
def test_results_horizontal_keys_and_selected_action(tmp_path, mode, track):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    exits = []
    app.userExit = lambda: exits.append(True)

    def press(key):
        app.messenger.send(key)
        app.messenger.send(key + "-up")

    try:
        app.start_game(mode=mode, track=track)
        app.session.phase = Phase.DRIVING
        app.refresh_panel()
        for succeeded in (True, False):
            if mode == GameMode.TIME_TRIAL:
                app.session.race.snapshot = replace(
                    app.session.race.snapshot, finished=True, last_lap=87.123,
                    invalidated=not succeeded, invalid_reason="错过检查点" if not succeeded else "",
                )
                app.session.tick()
            elif mode == GameMode.DISTANCE_CHALLENGE:
                app.session.highway.snapshot = replace(
                    app.session.highway.snapshot, finished=True, succeeded=succeeded,
                    reason="完成挑战" if succeeded else "发生碰撞",
                )
                app.session.tick()
            else:
                app.session.finish()
            assert app.session.phase == Phase.RESULTS
            frozen = app.session.simulation.snapshot()
            # 故意不刷新面板：比赛刚结束时的首个按键也必须使用结算按钮。
            app.messenger.send("arrow_right")
            app.messenger.send("arrow_right")
            assert app.panel_selection == 1  # 按住不连续跳选项。
            app.messenger.send("arrow_right-up")
            app.refresh_panel()
            assert app.panel_selection == 1
            assert app.buttons[1]["frameTexture"][0] == app.button_states[2]
            press("d")
            assert app.panel_selection == 2
            press("arrow_right")
            assert app.panel_selection == 0
            press("arrow_left")
            assert app.panel_selection == 2
            press("a")
            assert app.panel_selection == 1
            press("arrow_up")
            assert app.panel_selection == 0
            press("arrow_down")
            assert app.panel_selection == 1
            assert app.session.simulation.snapshot() == frozen
            assert not app.session.keyboard.pressed
            press("enter")
            assert app.session.phase == Phase.MENU
            assert not app.main_menu.root.isHidden()
            # 不等待渲染帧，立即再次进入同一模式并结束。
            app.start_game(mode=mode, track=track)
            app.session.phase = Phase.DRIVING
            app.refresh_panel()

        app.session.finish()
        press("arrow_left")
        press("enter")
        assert exits == [True]
        assert app.session.phase == Phase.RESULTS
        press("arrow_right")
        press("enter")
        assert app.session.phase == Phase.COUNTDOWN
        assert app.session.mode == mode
        assert app.session.simulation.track == track
    finally:
        app.close_game()


def test_pause_immediate_enter_uses_pause_actions(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    try:
        app.start_game(mode=GameMode.FREE_DRIVE)
        app.session.phase = Phase.DRIVING
        app.refresh_panel()
        frozen = app.session.current
        app.messenger.send("escape")
        app.messenger.send("escape-up")
        assert app.session.phase == Phase.PAUSED
        app.messenger.send("enter")
        app.messenger.send("enter-up")
        assert app.session.phase == Phase.DRIVING
        assert app.session.current == frozen
    finally:
        app.close_game()
