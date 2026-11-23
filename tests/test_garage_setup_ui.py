"""车库专家入口使用唯一实验参数编辑；不保留另一套永久改装表。"""

import pytest

from application import CoastalDrive
from session import Phase


def finish(app, workspace):
    for _ in range(60):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


@pytest.mark.parametrize('size', [(1280, 720), (1024, 768)])
def test_garage_expert_parameters_stage_current_vehicle_and_return_same_collection(tmp_path, monkeypatch, size):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    app = CoastalDrive(smoke=True, output=tmp_path/'game', lab_output=tmp_path/'reports', render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        original = app.workspace_vehicle
        original.save(app.workspace_path)
        before = app.workspace_path.read_bytes()
        app.open_career_collection()
        app.career_action('garage-tab', 'setup')
        finish(app, 'lab')
        assert app.lab.engineered_config == original.config
        app.lab.entries['cg'].enterText('.47')
        app.lab.back_to_game()
        finish(app, 'game')
        assert app.session.phase == Phase.MENU and app.career_panel.page == 'garage'
        assert app.workspace_vehicle == original and app.workspace_path.read_bytes() == before
        assert app.lab_workspace.fields['cg'] == '.47'
    finally:
        app.close_game()
