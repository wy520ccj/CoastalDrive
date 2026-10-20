"""实际Panda菜单/道路门/HUD及同窗返回；结果数据为明示规则夹具。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from race import GameMode
from session import Phase
from sprint_routes import SPRINT_ROUTES


def test_menu_two_routes_markers_hud_result_and_same_window_lab_return(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        config = app.session.vehicle_config
        app.back_to_menu()
        app.choose_highway()
        assert app.panel_option_count == 8
        for first, second in zip(app.buttons[:7], app.buttons[1:8], strict=True):
            assert first.getZ()+first['frameSize'][2] > second.getZ()+second['frameSize'][3]
        app.buttons[6]['command']()
        assert app.sprint_menu and app.panel_option_count == 7
        assert '平路连弯' in app.panel_note.getText() and '山脊冲刺' in app.panel_note.getText()
        previous_shape = app.highway_shape
        app.adjust_panel_option(1)
        assert app.highway_shape == previous_shape
        app.handle_panel_key('escape')
        assert not app.sprint_menu and app.panel_selection == 6
        for index, (mode, route) in enumerate(SPRINT_ROUTES.items()):
            app.choose_sprint_routes()
            app.buttons[index]['command']()
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING and app.session.mode == mode
            assert app.session.vehicle_config == config and app.session.road_shape == route.shape
            result = app.session.highway.snapshot.sprint
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
            assert app.hud.mode.getText() == route.name and '金' in app.hud.split.getText()
            app.scene.sprint_markers.apply(None, app.session.simulation.road)
            assert app.session.simulation.snapshot() == before and app.session.simulation._world.getNumRigidBodies() == bodies
            # 只验证结算呈现：真实跑圈另由独立工具记录，夹具不写入最佳文件。
            result = replace(result, seconds=route.targets[0], finished=True, succeeded=True, gates=4,
                gate_times=tuple(route.targets[0]*i/4 for i in range(1, 5)), medal='金', reason=route.name+' · 金牌完成')
            app.session.highway.snapshot = replace(app.session.highway.snapshot, sprint=result, finished=True, succeeded=True)
            app.session.phase = Phase.RESULTS
            app._shown_phase = None
            app.refresh_panel()
            assert route.name in app.panel_note.getText() and '金' in app.panel_detail.getText()
            assert all(not column.isHidden() for column in app.result_sectors)
            app.back_to_menu()
        app.start_sprint(GameMode.VALLEY_PACE)
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
        assert app.session.mode == GameMode.VALLEY_PACE and app.session.vehicle_config == config
        for _ in range(360):
            app.session.tick()
        assert app.session.highway.snapshot.sprint.route_id == GameMode.VALLEY_PACE.value
    finally:
        app.close_game()


def test_same_shape_different_seed_rebuilds_road_presentation(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        app.start_sprint(GameMode.RIDGE_SPRINT)
        original = app.scene
        assert app.session.simulation.seed == 0 and app.session.road_shape == 'hills'
        # 直接切换两项弯坡赛事，不能依赖先关场景来碰巧清除旧几何。
        app.start_sprint(GameMode.VALLEY_PACE)
        assert app.session.simulation.seed == 17 and app.session.road_shape == 'hills'
        assert app.scene is not original
        assert original.render.isEmpty()
        assert app._scene_seed == 17
    finally:
        app.close_game()
