"""实际同窗入口与课题返回；结果数据为显式界面夹具。"""

import pytest

from application import CoastalDrive
from race import GameMode
from slalom_lesson import SLALOM_MODES


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, output=tmp_path/'game', lab_output=tmp_path/'reports')
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.back_to_menu()
    yield game
    game.close_game()


def finish(app, workspace):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


def test_keyboard_toggle_rules_preserves_car_and_old_entry(app):
    config = app.session.vehicle_config
    app.choose_slalom_lesson()
    assert app.panel_option_count == 4 and '40km/h' in app.panel_note.getText()
    app.select_panel_option(1)
    app.handle_panel_key('enter')
    assert app.slalom_mode == GameMode.FAST_SLALOM and '70–80' in app.panel_note.getText()
    assert app.session.vehicle_config == config
    app.handle_panel_key('escape')
    assert app.highway_menu and not app.slalom_menu and app.panel_selection == 5
    app.choose_slalom_lesson()
    assert app.slalom_mode == GameMode.SLALOM_LESSON


def test_fast_scene_and_same_window_lab_return_preserve_course_and_mode(app):
    app.choose_slalom_lesson(GameMode.FAST_SLALOM)
    config, window = app.session.vehicle_config, app.win
    app.buttons[0]['command']()
    for _ in range(360):
        app.session.tick()
    result = app.session.highway.snapshot.slalom
    assert result.fast and app.session.mode == GameMode.FAST_SLALOM and not app.session.simulation.npcs
    app.apply_scene(app.session.current, 0.)
    assert '70–80' in app.scene.slalom_markers.entry_label.getText()
    app.open_vehicle_lab()
    finish(app, 'lab')
    app.lab.entries['cg'].enterText('.47')
    app.lab.back_to_game()
    finish(app, 'game')
    assert app.win is window and app.session.mode == GameMode.FAST_SLALOM
    assert app.session.vehicle_config == config and app.lab_workspace.fields['cg'] == '.47'
    assert app.session.mode in SLALOM_MODES
