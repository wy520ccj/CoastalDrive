"""定圆参考工坊的连续硬件/免费分配、超预算试验、切题与资源回收。"""

from types import SimpleNamespace

import pytest

from challenge_build import BuildDraft
from lab_application import VehicleLab
from vehicle_workspace import WorkspaceVehicle
from workshop_budget import REFERENCE_CHALLENGES


@pytest.fixture
def lab(tmp_path, monkeypatch):
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


def prepare(panel):
    panel.show()
    panel.set_topic(1)
    panel.action('challenge-value', ('front_tire', '45.5'))
    panel.action('challenge-tab', 2)
    panel.action('challenge-value', ('antiroll_share', str(100*8/30)))


def test_actual_reference_result_and_frozen_hardware_survive_workspace_and_save(lab, monkeypatch):
    panel = lab.workshop
    prepare(panel)
    panel.start()
    finish(lab)
    assert panel.result['improvement_pct'] > 0 and panel.result['cost'] == 2000
    assert panel.result['passed'] and panel.result['medal'] == '银'
    saved = lab.capture_workspace()
    result = panel.result
    panel.set_topic(0)
    assert panel.result is None and panel.draft == BuildDraft()
    panel.restore(saved.workshop_state)
    assert panel.topic == 1 and panel.result == result
    assert panel.draft.front_tire == 1.3 and panel.selected_cost() == 2000
    monkeypatch.setattr(lab, 'userExit', lambda: None)
    panel.drive()
    vehicle = WorkspaceVehicle.load(lab.workspace_path)
    assert vehicle.config == REFERENCE_CHALLENGES[1].configuration(panel.measured_build)
    lab.record, lab.baseline = panel.candidate, panel.baseline
    panel.set_topic(0)
    panel.restore_saved(vehicle)
    assert panel.topic == 1 and panel.result['passed']


def test_overbudget_is_a_real_trial_and_topic_switch_cancels_the_active_computation(lab):
    panel = lab.workshop
    prepare(panel)
    panel.action('challenge-tab', 1)
    panel.action('challenge-value', ('rear_tire', '65'))
    assert panel.selected_cost() == 4000
    assert '超出' in panel.editor.challenge_readouts['budget'].getText()
    panel.start()
    finish(lab)
    assert not panel.result['passed'] and '超出本场预算' in panel.result['unmet']
    panel.action('challenge-adjust')
    panel.start()
    run = lab.run_state
    panel.set_topic(0)
    assert run.paused and panel.phase is None and panel.result is None
    assert panel.drafts[1].cost == 4000


def test_repeated_topic_switch_keeps_one_vehicle_buffer_and_releases_old_controls(lab):
    panel = lab.workshop
    panel.show()
    panel.set_topic(1)
    count = panel.root.getNumChildren()
    buffer = panel.vehicle_view.buffer
    old = tuple(panel.editor.challenge_entries.values())
    for index in range(12):
        panel.set_topic(index % 2)
        assert panel.root.getNumChildren() == count
        assert panel.vehicle_view.buffer == buffer
    assert all(entry.isEmpty() for entry in old)
