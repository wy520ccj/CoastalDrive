"""真实课题入口、门线纯显示、返回同课题与结算规则夹具。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from challenge_catalog import ROAD_CHALLENGES
from race import GameMode
from session import Phase
from slalom_markers import MARKER_MASK


@pytest.fixture
def app(tmp_path):
    game = CoastalDrive(smoke=True, output=tmp_path, lab_output=tmp_path/"reports")
    game.taskMgr.remove("finish-smoke")
    game.taskMgr.remove("drive-update")
    game.back_to_menu()
    game._shown_phase = None
    game.refresh_panel()
    yield game
    game.close_game()


def finish(app, target):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == target and app._workspace_steps is None
    app.taskMgr.remove("lab-update" if target == "lab" else "drive-update")


def test_rules_entry_preserves_car_and_highway_preferences_and_back_focus(app):
    original = app.session.vehicle_config
    app.choose_highway()
    assert app.panel_option_count == 8
    app.buttons[5]["command"]()
    assert app.slalom_menu and "4米" in app.panel_note.getText() and "40km/h" in app.panel_note.getText()
    app.handle_panel_key("escape")
    assert app.highway_menu and not app.slalom_menu and app.panel_selection == 5
    shape = app.highway_shape
    app.choose_slalom_lesson()
    app.buttons[0]["command"]()
    assert app.career_panel.page == 'challenge' and app.session.vehicle_config == original
    app.challenge_action('challenge-start')
    assert app.session.mode == GameMode.SLALOM_LESSON and not app.session.simulation.npcs
    assert app.session.vehicle_config == ROAD_CHALLENGES[GameMode.SLALOM_LESSON].base_config
    assert app.highway_shape == shape
    app.challenge_action('challenge-back')
    assert app.session.vehicle_config == original


def test_markers_only_render_do_not_affect_world_and_rebase_display_only(app):
    app.start_slalom_lesson()
    app.challenge_action('challenge-start')
    for _ in range(360):
        app.session.tick()
    app.apply_scene(app.session.current, 0.)
    marker = app.scene.slalom_markers
    before = app.session.simulation.snapshot()
    count = app.session.simulation._world.getNumRigidBodies()
    assert not marker.root.isHidden(MARKER_MASK)
    result = app.session.highway.snapshot.slalom
    marker.apply(result, 100.)
    assert marker.root.getY() == pytest.approx(result.start_progress-100.)
    marker.apply(None, 0.)
    assert marker.root.isHidden(MARKER_MASK)
    assert before == app.session.simulation.snapshot() and count == app.session.simulation._world.getNumRigidBodies()


def test_actual_same_window_lab_return_restarts_slalom_instead_of_coastal(app):
    owned = app.workspace_vehicle
    app.start_slalom_lesson()
    app.challenge_action('challenge-start')
    config = app.session.vehicle_config
    window = app.win
    app.open_vehicle_lab()
    finish(app, "lab")
    assert app.budget_active and app.budget_mode == GameMode.SLALOM_LESSON
    assert app.lab.engineered_config == config
    app.lab.entries["cg"].enterText(".47")
    app.lab.back_to_game()
    finish(app, "game")
    assert app.win is window and app.session.mode == GameMode.SLALOM_LESSON
    assert app.workspace_vehicle == owned and app.session.vehicle_config == config
    assert app.lab_workspace.fields["cg"] == ".47"


def test_display_fixture_shows_gate_error_and_retry_without_claiming_actual_drive(app):
    # 专家自由试验的旧结果展示仍保留，夹具不冒充新预算驾驶。
    app.start_game(mode=GameMode.SLALOM_LESSON, track='endless')
    for _ in range(360):
        app.session.tick()
    actual = app.session.highway.snapshot
    result = replace(actual.slalom, gates=2, errors=(.1, -.2, 1.2), clearances=(.8, .7, -.3),
                     entry_kph=55., entry_time=6., run_seconds=8., finished=True, reason="错过第3门")
    app.session.highway.snapshot = replace(actual, running=False, finished=True, slalom=result, reason=result.reason)
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    assert "第3门" in app.panel_note.getText() and "-0.30" in app.panel_detail.getText()
    assert app.buttons[1]["text"] == "返回实验台" and app.buttons[2]["text"] == "返回主菜单"
    app.buttons[0]["command"]()
    assert app.session.mode == GameMode.SLALOM_LESSON
