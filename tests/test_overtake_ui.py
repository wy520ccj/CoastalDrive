"""实际菜单/HUD/失败结算与同窗实验台往返；成功驾驶另由记录工具验证。"""

from application import CoastalDrive
from challenge_build import BuildDraft
from race import GameMode
from session import Phase


def test_overtake_menu_hud_result_retry_and_same_window_lab_return(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        app.back_to_menu()
        app.choose_highway()
        assert app.panel_option_count == 8
        app.buttons[6]['command']()
        assert app.panel_option_count == 7
        app.buttons[3]['command']()
        assert app.overtake_menu and '10米' in app.panel_note.getText() and app.panel_option_count == 2
        assert '150秒内跑完2公里' in app.panel_note.getText()
        assert any('150秒内安全到终点' in label.getText() for label in app.driving_cards.labels)
        assert app.panel_note.getTightBounds(app.panel)[0].z > app.buttons[0].getZ()+app.buttons[0]['frameSize'][3]
        app.adjust_panel_option(1)
        app.handle_panel_key('escape')
        assert app.sprint_menu and not app.overtake_menu and app.panel_selection == 3
        app.buttons[3]['command']()
        app.buttons[0]['command']()
        assert app.career_panel.page == 'challenge' and app.budget_mode == GameMode.SAFE_OVERTAKE
        choice = next(button for button in app.career_panel.buttons if button['extraArgs'] == ['challenge-preset', 1])
        choice['command'](*choice['extraArgs'])
        app.challenge_action('challenge-start')
        assert app.session.challenge_build == BuildDraft(mass=.96, drag=.95, brake_share=.65, antiroll_share=.4)
        for _ in range(360):
            app.session.tick()
        assert app.session.phase == Phase.DRIVING and app.session.mode == GameMode.SAFE_OVERTAKE
        app._shown_phase = None
        app.refresh_panel()
        app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                       track='endless', countdown='', notice='')
        assert app.hud.coastal.title.getText() == '车流安全超车' and '0/2' in app.hud.coastal.notice.getText()
        assert not app.hud.coastal.notice_frame.isHidden()
        config, window = app.session.vehicle_config, app.win
        app.open_vehicle_lab()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == 'lab' and app.budget_active and app.budget_mode == GameMode.SAFE_OVERTAKE
        app.lab.back_to_game()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == 'game' and app.win is window and app.session.vehicle_config == config
        for _ in range(360):
            app.session.tick()
        assert app.session.mode == GameMode.SAFE_OVERTAKE and len(app.session.current.traffic) == 12
        app.session.reset_player()
        app._shown_phase = None
        app.refresh_panel()
        assert app.session.phase == Phase.RESULTS and app.career_panel.page == 'challenge-result'
        assert not app.session.highway.snapshot.engineering.result.valid
        assert '复位' in app.session.highway.snapshot.engineering.result.notice
        app.challenge_action('challenge-retry')
        for _ in range(360):
            app.session.tick()
        assert app.session.highway.snapshot.overtake.passes == 0
        app.back_to_menu()
        app.choose_highway()
        assert not app.overtake_menu and app.panel_option_count == 8
    finally:
        app.close_game()
