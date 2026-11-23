"""实际Panda菜单/道路门/HUD及同窗返回；结果数据为明示规则夹具。"""

import pytest

from application import CoastalDrive
from challenge_catalog import SPRINT_CHALLENGES, course_shape
from race import GameMode
from session import Phase
from sprint_routes import SPRINT_ROUTES, sprint_result_route


def test_menu_two_routes_markers_hud_result_and_same_window_lab_return(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        config = app.session.vehicle_config
        app.back_to_menu()
        app.choose_highway()
        assert app.panel_option_count == 8
        assert app.driving_cards.active and all(not button.isHidden() for button in app.buttons[:8])
        app.buttons[6]['command']()
        assert app.sprint_menu and app.panel_option_count == 7
        assert '平路连弯' in app.panel_note.getText() and '山脊冲刺' in app.panel_note.getText()
        previous_shape = app.highway_shape
        app.adjust_panel_option(1)
        assert app.highway_shape == previous_shape
        app.handle_panel_key('escape')
        assert not app.sprint_menu and app.panel_selection == 6
        for index, mode in enumerate(SPRINT_ROUTES):
            app.choose_sprint_routes()
            app.buttons[index]['command']()
            assert app.career_panel.page == 'challenge' and app.session.phase == Phase.MENU
            app.challenge_action('challenge-start')
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING and app.session.mode == mode
            assert app.session.vehicle_config == SPRINT_CHALLENGES[mode].base_config and app.session.road_shape == course_shape(mode)
            result = app.session.highway.snapshot.sprint
            route = sprint_result_route(result)
            before = app.session.simulation.snapshot()
            bodies = app.session.simulation._world.getNumRigidBodies()
            app.scene.apply(before)
            point = app.session.simulation.road.sample_lateral(result.start_progress+route.gates[0], 0.)
            marker = app.scene.sprint_markers.gates[0]
            assert tuple(marker.getPos()) == pytest.approx((point.x, point.y, point.z), abs=1e-4)
            assert marker.getP() == pytest.approx(point.grade, abs=1e-4)
            children = app.scene.sprint_markers.zone_root.getNumChildren()
            assert (children > 0) == (route.speed_zone is not None)
            app.scene.apply(before)
            assert app.scene.sprint_markers.zone_root.getNumChildren() == children
            app.hud.update(before, app.session.race.snapshot, app.session.highway.snapshot,
                           track='endless', countdown='', notice='')
            assert app.hud.coastal.title.getText() == route.name
            assert '金牌目标' in app.hud.coastal.cumulative.getText()
            if route.speed_zone is not None:
                assert '测速门375m · ≥80km/h' in app.hud.coastal.notice.getText()
                assert app.scene.sprint_markers.labels[0].getText() == '测速 ≥80km/h'
            app.scene.sprint_markers.apply(None, app.session.simulation.road)
            assert app.session.simulation.snapshot() == before and app.session.simulation._world.getNumRigidBodies() == bodies
            app.session.finish()
            app._shown_phase = None
            app.refresh_panel()
            assert app.career_panel.page == 'challenge-result'
            assert app.session.highway.snapshot.engineering.result.medal == ''
            assert all(column.isHidden() for column in app.result_sectors)
            app.back_to_menu()
        app.start_sprint(GameMode.VALLEY_PACE)
        app.challenge_action('challenge-start')
        window = app.win
        app.open_vehicle_lab()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == 'lab' and app.lab_return_sprint == GameMode.VALLEY_PACE
        app.lab.back_to_game()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == 'game' and app.win is window
        assert app.session.mode == GameMode.VALLEY_PACE
        assert app.session.vehicle_config == SPRINT_CHALLENGES[GameMode.VALLEY_PACE].base_config
        for _ in range(360):
            app.session.tick()
        assert app.session.highway.snapshot.sprint.route_id == GameMode.VALLEY_PACE.value
        app.back_to_menu()
        assert app.session.vehicle_config == config
    finally:
        app.close_game()


def test_same_shape_different_seed_rebuilds_road_presentation(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        # 旧专家路线仍是同一hills形状；预算路线的独立几何由目录测试覆盖。
        app.session.start(mode=GameMode.RIDGE_SPRINT, track='endless', countdown=False)
        app.sync_scene()
        original = app.scene
        assert app.session.simulation.seed == 0 and app.session.road_shape == 'hills'
        app.session.menu()
        app.session.start(mode=GameMode.VALLEY_PACE, track='endless', countdown=False)
        app.sync_scene()
        assert app.session.simulation.seed == 17 and app.session.road_shape == 'hills'
        assert app.scene is not original
        assert original.render.isEmpty()
        assert app._scene_seed == 17
    finally:
        app.close_game()
