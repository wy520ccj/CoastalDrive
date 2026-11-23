"""实际滨海目标HUD/菜单/结算布局；成绩夹具不冒充真实驾驶。"""

from dataclasses import asdict, replace

import pytest
from panda3d.core import Point3, ShaderAttrib, Texture

from application import CoastalDrive
from driving_modes import DrivingMode
from race import BestTimes, GameMode, RaceSnapshot
from session import Phase
from tracks import COASTAL_CIRCUIT


def test_coastal_modes_keep_distinct_regional_light_and_checkpoint_rules(tmp_path):
    from environment.expressway_materials import daylight_environment
    from environment.foundation import coastal_ground_shader
    from paths import resource_root

    game = CoastalDrive(smoke=True, output=tmp_path)
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    try:
        coast = game.scene
        initial_exposure = coast.previous_exposure
        mountain, _metadata = daylight_environment(resource_root()/'assets/game/environment/daylight')
        coast_texture = coast.render.getShaderInput('filtered_env_map').getTexture()
        assert coast_texture != mountain.filtered_env_map
        assert coast.coastal_daylight['art_direction'] == 'design38'
        assert 0 < coast.coastal_daylight['source_sun_elevation_degrees'] < 8
        assert game.render.getShaderInput('filtered_env_map').getTexture() != coast_texture
        original_config = game.session.vehicle_config
        original_props = game.session.simulation.props
        for mode in (GameMode.FREE_DRIVE, GameMode.TIME_TRIAL):
            game.start_game(mode=mode, track='coastal')
            if game.scene is not coast:
                assert coast.render.isEmpty()
            coast = game.scene
            assert coast.render.getShaderInput('filtered_env_map').getTexture() == coast_texture
            assert game.session.vehicle_config == original_config
            assert game.session.simulation.props == original_props
            assert coast.checkpoint_nodes
            assert all(node.isHidden() == (mode == GameMode.FREE_DRIVE) for node in coast.checkpoint_nodes)
            # 静态合批后仍必须保持草地实际绘制材质、色彩空间与同源细节。
            ground_states = []
            for path in coast.render.findAllMatches('**/+GeomNode'):
                for index in range(path.node().getNumGeoms()):
                    state = path.getNetState().compose(path.node().getGeomState(index))
                    shader = state.getAttrib(ShaderAttrib)
                    if shader is not None and shader.getShader() == coastal_ground_shader():
                        ground_states.append(shader)
            assert len(ground_states) == 1
            ground = ground_states[0]
            assert ground.getShaderInput('coastal_ground_albedo').getTexture().getFormat() == Texture.FSrgb
            for name in ('coastal_ground_normals', 'coastal_ground_roughness'):
                assert ground.getShaderInput(name).getTexture().getFormat() not in (Texture.FSrgb, Texture.FSrgbAlpha)
            # 检查最终绘制状态，防止合批把初始时间烘焙进Geom后挡住节点更新。
            assert coast.ocean.getParent() == coast.render
            for seconds in (.25,1.5):
                coast.apply(replace(game.session.current,time=seconds))
                water_state = coast.ocean.getNetState().compose(coast.ocean.node().getGeomState(0))
                assert water_state.getAttrib(ShaderAttrib).getShaderInput('sea_time').getVector()[0] == seconds
        game.back_to_menu()
        assert coast.render.isEmpty() and game.scene is None
        assert game.pipeline.exposure == initial_exposure
    finally:
        game.close_game()


@pytest.fixture
def app(tmp_path):
    game = CoastalDrive(smoke=True, output=tmp_path, render_size=(1024, 768))
    game.taskMgr.remove("finish-smoke")
    game.taskMgr.remove("drive-update")
    game.back_to_menu()
    game._shown_phase = None
    game.refresh_panel()
    yield game
    game.close_game()


def test_menu_budget_entry_keeps_old_times_separate_and_fits_primary_button(app):
    scores = BestTimes(app.session.race.scores.path)
    course = COASTAL_CIRCUIT.score_id+":"+app.session.score_variant()
    scores.record(GameMode.TIME_TRIAL, 50., "legacy")
    app._shown_phase = None
    app.refresh_panel()
    assert app.main_menu.time_goal.getText() == '独立预算 5000 · 用时与油耗'
    scores.record(GameMode.TIME_TRIAL, 70., course)
    app._shown_phase = None
    app.refresh_panel()
    assert app.main_menu.time_goal.getText() == '独立预算 5000 · 用时与油耗'
    button = app.main_menu.buttons[0]
    lower, upper = app.main_menu.time_goal.getTightBounds(button)
    assert lower.z > button["frameSize"][2] and upper.x < button["frameSize"][1]
    original = app.session.vehicle_config
    app.session.set_vehicle_config(replace(original, center_of_mass_height=.401))
    app._shown_phase = None
    app.refresh_panel()
    assert app.main_menu.time_goal.getText() == '独立预算 5000 · 用时与油耗'
    app.session.set_vehicle_config(original)
    app._shown_phase = None
    app.refresh_panel()
    assert app.main_menu.time_goal.getText() == '独立预算 5000 · 用时与油耗'


def test_hud_target_fits_below_splits_uses_departure_reference_and_hides_elsewhere(app):
    app.hud.root.show()
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, elapsed=60., reference_lap=70., best_lap=50.,
                        splits=(20., 40.), reference_splits=(21., 42., 50., 60., 70.))
    app.hud.update(app.session.current, race, app.session.highway.snapshot, track="coastal", countdown="", notice="")
    view = app.hud.coastal
    assert "目标 银牌 · 还剩5.0s" in view.goal.getText() and not view.goal.isHidden()
    lower, upper = view.goal.getTightBounds(view.status)
    assert lower.z > -276 and upper.x < 360
    assert upper.z < view.cumulative.getTightBounds(view.status)[0].z-8
    app.hud.update(app.session.current, replace(race, mode=GameMode.SLALOM_LESSON), app.session.highway.snapshot,
                   track="endless", countdown="", notice="")
    assert app.hud.goal.isHidden() and app.hud.status_frame["frameSize"][2] == -.54
    assert view.root.isHidden()
    app.hud.update(app.session.current, race, app.session.highway.snapshot, track="test", countdown="", notice="")
    assert app.hud.goal.isHidden() and app.hud.status_frame["frameSize"][2] == -.54


def test_compact_coastal_hud_keeps_state_warnings_controls_and_viewport(app):
    app.hud.root.show()
    before = asdict(app.session.current)
    view = app.hud.coastal
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, elapsed=42.73, checkpoints=2, next_checkpoint=3,
        reference_lap=70., splits=(21.,40.), reference_splits=(20.,41.,50.,60.,70.))
    for aspect in (16/9,4/3):
        app.hud.resize(aspect)
        app.hud.select_radio(1)
        app.hud.update(app.session.current,race,app.session.highway.snapshot,track='coastal',
                       countdown='',notice='',driving_mode=DrivingMode.SIMULATION)
        assert app.hud.status_frame.isHidden() and app.hud.career.root.isHidden()
        assert not view.root.isHidden() and view.timer.getText() == '00:42.73'
        assert '下一处 3' in view.checkpoints.getText()
        assert 'Q 倒挡' in view.secondary_keys.getText() and 'S 刹车 ' in view.primary_keys.getText()
        assert [not label.isHidden() for label in view.radio] == [False,True,False]
        for card in (view.status,view.help_frame,view.instruments):
            left,right,bottom,top=card['frameSize']
            low=app.aspect2d.getRelativePoint(card,Point3(left,0,bottom))
            high=app.aspect2d.getRelativePoint(card,Point3(right,0,top))
            assert -aspect <= low.x < high.x <= aspect and -1 <= low.z < high.z <= 1
        assert not view.progress_insets[2].isHidden()
    app.hud.update(app.session.current,replace(race,invalidated=True,invalid_reason='车辆复位',
        score_notice='成绩未保存',ghost_notice='幽灵不可用'),app.session.highway.snapshot,
        track='coastal',countdown='',notice='原有警告')
    assert all(text in view.notice.getText() for text in ('成绩未保存','幽灵不可用','原有警告'))
    assert view.goal.getText() == '圈速无效：车辆复位'
    assert '不参与最佳比较' in view.cumulative.getText()
    app.hud.select_radio(None)
    app.hud.update(app.session.current,replace(race,mode=GameMode.FREE_DRIVE),
        app.session.highway.snapshot,track='coastal',countdown='',notice='')
    assert all(widget.isHidden() for widget in view.timed_widgets)
    assert view.notice_frame.isHidden() and all(label.isHidden() for label in view.radio)
    assert asdict(app.session.current) == before


def test_coastal_action_buttons_keep_callbacks_and_restore_for_other_tracks(app):
    app.layout_driving_buttons()
    assert app.lab_return_button['command'] == app.return_from_test_drive
    assert app.ghost_button['command'] == app.toggle_ghost
    assert app.lab_return_button['frameSize'] == (-.25,.25,-.048,.048)
    app.start_game(mode=GameMode.FREE_DRIVE,track='test')
    app.layout_driving_buttons()
    assert app.lab_return_button['frameSize'] == (-.34,.34,-.055,.055)
    assert app.lab_return_button.getX() == pytest.approx(app.getAspectRatio()-.44)


@pytest.mark.parametrize("seconds,invalid,save_error,expected", [(50., False, "", "滨海金牌"),
    (60., False, "", "滨海银牌"), (75., False, "", "滨海铜牌"), (90., False, "", "尚未达到铜牌"),
    (50., True, "", "圈速无效"), (50., False, "成绩暂未保存，请检查存储空间或目录权限", "滨海金牌")])
def test_result_medal_next_gap_and_table_clear_each_other_with_warnings(app, seconds, invalid, save_error, expected):
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, finished=True, elapsed=seconds, last_lap=seconds,
        best_lap=70. if save_error or invalid else seconds, reference_lap=70.,
        invalidated=invalid, invalid_reason="车辆复位" if invalid else "", save_error=save_error,
        new_best=not (save_error or invalid) and seconds < 70.,
        splits=tuple(seconds*index/5 for index in range(1, 6)),
        ghost_notice="成绩未保存，本次幽灵未关联。" if save_error else "最佳圈幽灵已保存，下次挑战可对照。")
    app.session.race.snapshot = race
    app.session.mode = GameMode.TIME_TRIAL
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    summary = app.driving_cards.summary_values
    visible = summary['outcome'].getText()+summary['title']
    assert expected in visible
    assert "目标" in summary['goal'].getText()
    if save_error:
        assert "新个人最佳" not in summary['notice'].getText() and save_error in summary['notice'].getText()
    for label in summary['sectors']:
        assert not label.isHidden()
        lower, upper = label.getTightBounds(app.driving_cards.content)
        assert upper.z < app.workshop_vehicle.frame['frameSize'][2]
        assert lower.z > 1-860*2/941
    assert all(column.isHidden() for column in app.result_sectors)
    app.buttons[0]["command"]()
    app.refresh_panel()
    assert all(column.isHidden() for column in app.result_sectors)
