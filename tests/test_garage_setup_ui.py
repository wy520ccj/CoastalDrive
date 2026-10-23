"""正常输入、跨分组保留、保存复载和文件失败；使用隔离玩家目录。"""

import pytest

from application import CoastalDrive
from vehicle_workspace import WorkspaceVehicle


@pytest.mark.parametrize('size', [(1280, 720), (1024, 768)])
def test_manual_setup_edits_without_key_leaks_and_saves_same_workspace(tmp_path, monkeypatch, size):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    app = CoastalDrive(smoke=True, output=tmp_path/'game', render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        app.open_career_collection()
        app.career_action('garage-tab', 'setup')
        panel, original = app.career_panel, app.workspace_vehicle
        entry = panel.setup_entries['front_tire']
        entry.enterText('72')
        entry['focus'] = 1
        app.key_down('arrow_down')
        app.key_up('arrow_down')
        assert panel.setup_group == 'tires' and app.workspace_vehicle == original
        app.key_down('escape')
        app.key_up('escape')
        assert panel.page == 'garage' and not entry['focus']
        app.career_action('setup-group', 'drive')
        panel.setup_entries['final_drive'].enterText('4.1')
        app.career_action('setup-group', 'tires')
        assert panel.setup_entries['front_tire'].get() == '72'
        app.career_action('setup-save')
        assert app.workspace_vehicle.config.lateral_stiffness == 72000.
        assert app.session.base_vehicle_config.final_drive == 4.1
        assert WorkspaceVehicle.load(app.workspace_path) == app.workspace_vehicle
        assert panel.setup_changes() == {}
        before = app.workspace_vehicle
        panel.setup_entries['front_tire'].enterText('bad')
        app.career_action('setup-save')
        assert app.workspace_vehicle == before
        assert panel.setup_entries['front_tire'].get() == 'bad'
        app.career_action('setup-reset')
        assert panel.setup_entries['front_tire'].get() == '72'
    finally:
        app.close_game()
