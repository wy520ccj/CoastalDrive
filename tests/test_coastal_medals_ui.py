"""实际滨海目标HUD/菜单/结算布局；成绩夹具不冒充真实驾驶。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from race import BestTimes, GameMode, RaceSnapshot
from session import Phase
from tracks import COASTAL_CIRCUIT


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


def test_menu_goal_reads_only_saved_current_hardware_and_fits_primary_button(app):
    scores = BestTimes(app.session.race.scores.path)
    course = COASTAL_CIRCUIT.score_id+":"+app.session.score_variant()
    scores.record(GameMode.TIME_TRIAL, 50., "legacy")
    app._shown_phase = None
    app.refresh_panel()
    assert app.main_menu.time_goal.getText() == "铜牌 ≤80s"
    scores.record(GameMode.TIME_TRIAL, 70., course)
    app._shown_phase = None
    app.refresh_panel()
    assert app.main_menu.time_goal.getText() == "铜牌 · 银牌 ≤65s"
    button = app.main_menu.buttons[0]
    lower, upper = app.main_menu.time_goal.getTightBounds(button)
    assert lower.z > button["frameSize"][2] and upper.x < button["frameSize"][1]
    original = app.session.vehicle_config
    app.session.set_vehicle_config(replace(original, center_of_mass_height=.401))
    app._shown_phase = None
    app.refresh_panel()
    assert app.main_menu.time_goal.getText() == "铜牌 ≤80s"
    app.session.set_vehicle_config(original)
    app._shown_phase = None
    app.refresh_panel()
    assert "银牌 ≤65s" in app.main_menu.time_goal.getText()


def test_hud_target_fits_below_splits_uses_departure_reference_and_hides_elsewhere(app):
    app.hud.root.show()
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, elapsed=60., reference_lap=70., best_lap=50.,
                        splits=(20., 40.), reference_splits=(21., 42., 50., 60., 70.))
    app.hud.update(app.session.current, race, app.session.highway.snapshot, track="coastal", countdown="", notice="")
    assert "目标 银牌 · 还剩5.0s" in app.hud.goal.getText() and not app.hud.goal.isHidden()
    lower, upper = app.hud.goal.getTightBounds(app.hud.status_frame)
    assert lower.z > -.64 and upper.x < .84
    assert upper.z < app.hud.split.getTightBounds(app.hud.status_frame)[0].z-.02
    app.hud.update(app.session.current, replace(race, mode=GameMode.SLALOM_LESSON), app.session.highway.snapshot,
                   track="endless", countdown="", notice="")
    assert app.hud.goal.isHidden() and app.hud.status_frame["frameSize"][2] == -.54
    app.hud.update(app.session.current, race, app.session.highway.snapshot, track="test", countdown="", notice="")
    assert app.hud.goal.isHidden() and app.hud.status_frame["frameSize"][2] == -.54


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
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    assert expected in app.panel_note.getText()
    assert "目标" in app.panel_detail.getText()
    if save_error:
        assert "新个人最佳" not in app.panel_note.getText() and save_error in app.panel_note.getText()
    for column in app.result_sectors:
        assert not column.isHidden()
        lower, upper = column.getTightBounds(app.panel)
        assert lower.z > app.buttons[0].getZ()+app.buttons[0]["frameSize"][3]+.01
        assert upper.z < app.panel_detail.getTightBounds(app.panel)[0].z-.01
        assert lower.x > -.94 and upper.x < .94
    app.buttons[0]["command"]()
    app.refresh_panel()
    assert all(column.isHidden() for column in app.result_sectors)
