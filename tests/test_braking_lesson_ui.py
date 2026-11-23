"""真实菜单/HUD/标线与结果传输；规则夹具明确不代替实际驾驶。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from braking_lesson import BrakingResult
from braking_markers import MARKER_MASK
from challenge_catalog import ROAD_CHALLENGES
from race import GameMode
from session import Phase, Session
from session_process import _decode_frame, _encode_frame, _output


@pytest.fixture
def app(tmp_path):
    game = CoastalDrive(smoke=True, output=tmp_path)
    game.taskMgr.remove("finish-smoke")
    game.taskMgr.remove("drive-update")
    yield game
    game.close_game()


def test_menu_rules_start_and_back_preserve_highway_shape_and_current_car(app):
    original = app.session.vehicle_config
    app.session.menu()
    app._shown_phase = None
    app.choose_highway()
    assert app.panel_option_count == 8
    app.buttons[4]["command"]()
    assert app.braking_menu and "无车流" in app.panel_note.getText()
    assert "100米" in app.panel_note.getText() and "170米" in app.panel_note.getText()
    app.handle_panel_key("escape")
    assert not app.braking_menu and app.highway_menu and app.panel_selection == 4
    previous_shape = app.highway_shape
    app.choose_braking_lesson()
    app.buttons[0]["command"]()
    assert app.career_panel.page == 'challenge' and app.session.phase == Phase.MENU
    assert app.session.vehicle_config == original
    app.challenge_action('challenge-start')
    assert app.session.mode == GameMode.BRAKING_LESSON and app.session.road_shape == "straight"
    assert app.highway_shape == previous_shape
    assert app.session.vehicle_config == ROAD_CHALLENGES[GameMode.BRAKING_LESSON].base_config
    assert not app.session.simulation.npcs
    app.challenge_action('challenge-back')
    assert app.session.vehicle_config == original and app.braking_menu


def test_markers_follow_lesson_origin_without_any_rigid_body_or_physical_change(app):
    app.session.road_shape = "straight"
    app.session.start(countdown=False, mode=GameMode.BRAKING_LESSON, track="endless")
    app.sync_scene()
    app.scene.render.show()
    before = app.session.simulation.snapshot()
    count = app.session.simulation._world.getNumRigidBodies()
    app.scene.apply(before)
    marker = app.scene.braking_markers
    assert not marker.root.isHidden(MARKER_MASK)
    assert marker.root.getY() == pytest.approx(before.player.position[1])
    shifted = replace(before, origin_y=100.)
    marker.apply(app.session.highway.snapshot.braking, shifted.origin_y)
    assert marker.root.getY() == pytest.approx(before.player.position[1]-100.)
    marker.apply(None, 0.)
    assert marker.root.isHidden(MARKER_MASK)
    assert app.session.simulation.snapshot() == before
    assert app.session.simulation._world.getNumRigidBodies() == count
    assert not marker.root.findAllMatches("**/+BulletRigidBodyNode")


def test_hud_and_result_give_actionable_error_and_lab_return(app):
    app.session.road_shape = "straight"
    app.session.start(countdown=False, mode=GameMode.BRAKING_LESSON, track="endless")
    app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                   track="endless", countdown="", notice="")
    assert app.hud.mode.getText() == "定点刹停" and "80" in app.hud.detail.getText()
    result = BrakingResult(entry_kph=87.3, error_m=-1.2, finished=True, succeeded=True,
                           medal="金", reason="金牌 · 已停稳1秒", best_error=1.2)
    app.session.highway.snapshot = replace(app.session.highway.snapshot, braking=result,
        finished=True, running=False, succeeded=True, elapsed=13.)
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    assert "金牌" in app.panel_note.getText() and "-1.20 m" in app.panel_detail.getText()
    assert "负数偏早" in app.panel_detail.getText() and "最佳误差" in app.panel_detail.getText()
    assert app.buttons[1]["text"] == "返回实验台"
    assert app.buttons[1]["command"] == app.open_vehicle_lab
    assert app.buttons[2]["text"] == "返回主菜单"
    app.buttons[2]["command"]()
    assert app.session.phase == Phase.MENU and app.scene is None


def test_existing_session_frame_carries_braking_result_without_new_vehicle_state(tmp_path):
    session = Session(track="endless")
    try:
        session.start(countdown=False, mode=GameMode.BRAKING_LESSON, track="endless")
        state = _decode_frame(_encode_frame(_output(session)))
        assert state.highway == session.highway.snapshot
        assert state.current == session.current
        assert state.highway.braking.start_progress == 8.
    finally:
        session.close()


def test_same_window_lab_round_trip_reopens_braking_lesson_with_current_hardware(app):
    window = app.win
    app.session.road_shape = "straight"
    app.session.start(countdown=False, mode=GameMode.BRAKING_LESSON, track="endless")
    config = app.session.vehicle_config
    app.open_vehicle_lab()
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == "lab" and app.win is window
    assert app.lab.engineered_config == app.workspace_vehicle.config
    app.lab.back_to_game()
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == "game" and app.win is window
    assert app.session.mode == GameMode.BRAKING_LESSON
    assert app.session.vehicle_config == config and not app.session.current.traffic
