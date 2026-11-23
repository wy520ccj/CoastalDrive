"""真实弯坡场景/终点只读几何/同窗返回；结算夹具只验证呈现。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from challenge_build import BuildDraft
from overtake_observations import GapIncident, TrafficReading
from race import GameMode
from session import Phase
from traffic import Road


def test_hill_menu_markers_results_and_lab_return(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        app.back_to_menu()
        app.choose_sprint_routes()
        assert app.panel_option_count == 7
        assert app.driving_cards.active and all(not button.isHidden() for button in app.buttons[:7])
        app.buttons[4]['command']()
        assert app.overtake_mode == GameMode.HILL_TRAFFIC and '跑完2.4公里' in app.panel_note.getText()
        assert app.panel_note.getTightBounds(app.panel)[0].z > app.buttons[0].getZ()+app.buttons[0]['frameSize'][3]
        app.handle_panel_key('escape')
        assert app.sprint_menu and app.panel_selection == 4
        app.buttons[4]['command']()
        app.buttons[0]['command']()
        assert app.career_panel.page == 'challenge' and app.budget_mode == GameMode.HILL_TRAFFIC
        choice = next(button for button in app.career_panel.buttons if button['extraArgs'] == ['challenge-preset', 0])
        choice['command'](*choice['extraArgs'])
        app.challenge_action('challenge-start')
        assert app.session.challenge_build == BuildDraft(power=1.15)
        for _ in range(360):
            app.session.tick()
        assert app.session.mode == GameMode.HILL_TRAFFIC and app.session.phase == Phase.DRIVING
        assert app.session.seed == 23 and app.session.road_shape == 'hills' and len(app.session.current.traffic) == 12
        result = app.session.highway.snapshot.overtake
        before = app.session.current
        bodies = app.session.simulation._world.getNumRigidBodies()
        road = app.session.simulation.road
        app.scene.apply(before)
        marker = app.scene.overtake_markers.finish
        point = road.sample_lateral(result.start_progress+2400., 0.)
        assert tuple(marker.getPos()) == pytest.approx((point.x, point.y, point.z), abs=1e-4)
        assert marker.getP() == pytest.approx(point.grade, abs=1e-4)
        read_only_road = Road('endless', seed=23, shape='hills')
        read_only_road.origin_y = 2000.
        app.scene.overtake_markers.apply(result, read_only_road)
        assert marker.getY() == pytest.approx(point.y-2000., abs=1e-3)
        assert app.session.current == before and app.session.simulation._world.getNumRigidBodies() == bodies
        app._shown_phase = None
        app.refresh_panel()
        app.hud.update(before, app.session.race.snapshot, app.session.highway.snapshot, track='endless', countdown='', notice='')
        assert app.hud.coastal.title.getText() == '弯坡车流' and '0/3' in app.hud.coastal.notice.getText()
        assert '分段 0 / 4' in app.hud.coastal.checkpoints.getText()
        observed = replace(result, traffic_reading=TrafficReading((0, 3), 'front', -2.1, 15., 18., 1., True))
        app.hud.update(before, app.session.race.snapshot, replace(app.session.highway.snapshot, overtake=observed),
                       track='endless', countdown='', notice='')
        assert not app.hud.coastal.notice_frame.isHidden() and '匀速' in app.hud.coastal.notice.getText()
        assert app.hud.coastal.notice.getTightBounds(app.hud.coastal.notice_frame)[0].z > app.hud.coastal.notice_frame['frameSize'][2]
        assert tuple(app.hud.coastal.notice.textNode.getTextColor())[:3] == pytest.approx((1, .48, .34))
        app.hud.update(before, app.session.race.snapshot,
                       replace(app.session.highway.snapshot, overtake=replace(observed, passes=3)),
                       track='endless', countdown='', notice='')
        assert '3/3 · 安全驶至终点' in app.hud.coastal.notice.getText()
        # 旧专家路径的详细安全事件展示继续只读保留，不冒充预算奖牌。
        app.back_to_menu()
        app.session.road_shape = 'hills'
        app.start_game(mode=GameMode.HILL_TRAFFIC, track='endless')
        for _ in range(360):
            app.session.tick()
        before = app.session.current
        result = app.session.highway.snapshot.overtake
        complete = replace(result, passes=3, distance=2400., seconds=100., medal='金', finished=True, succeeded=True,
            pass_times=(30., 45., 70.), pass_ids=((0, 0), (4, 0), (9, 0)), pass_clearances=(2., 3., 2.5), reason='安全超越3辆 · 金牌完成')
        app.session.highway.snapshot = replace(app.session.highway.snapshot, overtake=complete, finished=True, succeeded=True)
        app.session.phase = Phase.RESULTS
        app._shown_phase = None
        app.refresh_panel()
        assert '3/3' in app.panel_detail.getText() and '第3辆' in app.panel_detail.getText()
        assert app.panel_detail.getTightBounds(app.panel)[0].z > app.buttons[0].getZ()+app.buttons[0]['frameSize'][3]
        failure = replace(complete, succeeded=False, reason='与车流#12间距不足；侧距2.40米 / 前后距-4.40米。并行留1米，跟车或切回留10米。',
            incident=GapIncident((11, 2), 'parallel', -2., -4., 100., 2300., True),
            save_notice='已有最佳详情无法读取，完整用时保持。')
        app.session.highway.snapshot = replace(app.session.highway.snapshot, overtake=failure, succeeded=False)
        app._shown_phase = None
        app.refresh_panel()
        assert '拍间触发' in app.panel_detail.getText() and '下次' in app.panel_detail.getText()
        assert app.panel_detail.getTightBounds(app.panel)[0].z > app.buttons[0].getZ()+app.buttons[0]['frameSize'][3]
        assert app.session.current == before
        window, config = app.win, app.session.vehicle_config
        app.open_vehicle_lab()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == 'lab' and app.lab_return_overtake == GameMode.HILL_TRAFFIC
        app.lab.back_to_game()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.win is window and app.session.mode == GameMode.HILL_TRAFFIC and app.session.vehicle_config == config
        for _ in range(360):
            app.session.tick()
        assert app.session.highway.snapshot.overtake.passes == 0
    finally:
        app.close_game()
