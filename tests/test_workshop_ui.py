"""真实连续参数工坊：A/B、编辑失效、取消、报告和保存边界。"""

from types import SimpleNamespace

import pytest

from challenge_build import BuildDraft
from lab_application import VehicleLab
from vehicle_workspace import WorkspaceVehicle
from workshop_budget import REFERENCE_CHALLENGES


@pytest.fixture
def workbench(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    app = VehicleLab(offscreen=True, output=tmp_path/'reports', workspace_path=tmp_path/'vehicle.json')
    app.engine.taskMgr.remove('lab-update')
    yield app
    app.close_game()


def finish(app):
    while app.workshop.phase is not None:
        while not app.run_state.done:
            app.run_state.step()
        app.update(SimpleNamespace(cont=None))


def prepare_brakes(panel):
    panel.show()
    panel.action('challenge-tab', 2)
    panel.action('challenge-value', ('brake_share', '70'))
    assert panel.draft == BuildDraft(brake_share=.7) and panel.selected_cost() == 0


def test_typed_reference_setup_is_committed_before_run_and_invalid_input_blocks_it(workbench, monkeypatch):
    panel = workbench.workshop
    panel.show()
    panel.action('challenge-tab', 2)
    entry = panel.editor.challenge_entries['brake_share']
    entry.enterText('70')
    started = []
    monkeypatch.setattr(panel, 'start', lambda: started.append(panel.draft))
    panel.action('challenge-start')
    assert started == [BuildDraft(brake_share=.7)]
    entry.enterText('81')
    panel.action('challenge-start')
    assert started == [BuildDraft(brake_share=.7)]
    assert '范围' in panel.editor.challenge_readouts['notice'].getText()
    entry.enterText('68')
    panel.action('challenge-save')
    assert panel.plans.load(panel.spec) == BuildDraft(brake_share=.68)


def test_reference_ab_uses_shared_parameter_callbacks_and_changed_unrun_draft_invalidates_result(workbench):
    app, panel = workbench, workbench.workshop
    prepare_brakes(panel)
    panel.start()
    assert panel.editor.challenge_entries['brake_share']['state'] == 'disabled'
    finish(app)
    assert panel.result['passed'] and panel.result['medal'] == '金'
    assert app.baseline is panel.baseline and app.record is panel.candidate
    assert panel.editor.page == 'reference-result'
    frozen = app.capture_workspace()
    panel.action('challenge-adjust')
    panel.action('challenge-value', ('brake_share', '75'))
    assert panel.result is None and panel.draft.brake_share == .75
    panel.restore(frozen.workshop_state)
    assert panel.result['passed'] and panel.draft.brake_share == .7
    assert panel.editor.page == 'reference-result'
    assert panel.export_interpretation().parent.joinpath('challenge.json').is_file()
    baseline, candidate = panel.baseline, panel.candidate
    panel.action('challenge-adjust')
    panel.start()
    panel.escape()
    assert panel.phase is None and app.run_state.paused and panel.result is None
    assert panel.baseline is None and app.record is None
    assert baseline.snapshots and candidate.snapshots


def test_save_and_export_failures_retain_tested_hardware_then_retry_without_overwriting_player_early(workbench, tmp_path, monkeypatch):
    app, panel = workbench, workbench.workshop
    prepare_brakes(panel)
    panel.start()
    finish(app)
    blocked = tmp_path/'blocked'
    blocked.write_text('原文件', encoding='utf-8')
    previous_output = app.output
    app.output = blocked
    assert panel.export_interpretation() is None and panel.result['passed']
    assert app.workspace_vehicle is None and app.last_report is None
    assert any('未导出' in label.getText() for label in panel.editor.labels)
    app.output = previous_output
    path = app.workspace_path
    app.workspace_path = blocked/'vehicle.json'
    panel.drive()
    assert app.next_workspace is None and panel.result['passed']
    assert any('未保存' in label.getText() for label in panel.editor.labels)
    app.workspace_path = path
    app.entries['cg'].enterText('.9')
    monkeypatch.setattr(app, 'userExit', lambda: None)
    panel.drive()
    assert app.next_workspace == 'game' and app.next_drive
    assert app.workspace_vehicle.config == REFERENCE_CHALLENGES[0].configuration(BuildDraft(brake_share=.7))
    assert WorkspaceVehicle.load(path) == app.workspace_vehicle
    assert blocked.read_text(encoding='utf-8') == '原文件'


def test_legacy_report_is_read_only_and_does_not_invent_new_budget_medals(workbench):
    from workshop import evaluate

    app, panel = workbench, workbench.workshop
    prepare_brakes(panel)
    panel.start()
    finish(app)
    legacy = evaluate(panel.baseline, panel.candidate, 2, False)
    vehicle = WorkspaceVehicle('reference-rwd', panel.selected_config(), workshop_result=legacy)
    app.record, app.baseline = panel.candidate, panel.baseline
    panel.restore_saved(vehicle)
    panel.show()
    assert panel.historical == legacy and panel.historical['cost'] == 1
    assert panel.result is None and panel.editor.page == 'challenge'
    assert panel.baseline is app.baseline and panel.candidate is app.record
    assert '历史报告' in panel.editor.challenge_readouts['notice'].getText()


def test_one_invalid_saved_draft_remains_visible_after_the_other_topic_loads_successfully(tmp_path, monkeypatch):
    import json

    from challenge_plans import ChallengePlans
    from paths import user_data

    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    plans = ChallengePlans(user_data()/'challenge-plans.json')
    spec = REFERENCE_CHALLENGES[0]
    plans.save(spec, BuildDraft(brakes=1.1))
    data = json.loads(plans.path.read_text(encoding='utf-8'))
    data['plans'][plans._key(spec)]['brakes'] = 2.
    plans.path.write_text(json.dumps(data), encoding='utf-8')
    before = plans.path.read_bytes()
    app = VehicleLab(offscreen=True, output=tmp_path/'reports')
    app.engine.taskMgr.remove('lab-update')
    try:
        panel = app.workshop
        panel.show()
        assert '未能读取' in panel.editor.challenge_readouts['notice'].getText()
        panel.set_topic(1)
        assert '未能读取' not in panel.editor.challenge_readouts['notice'].getText()
        panel.set_topic(0)
        assert '未能读取' in panel.editor.challenge_readouts['notice'].getText()
        assert plans.path.read_bytes() == before
    finally:
        app.close_game()
