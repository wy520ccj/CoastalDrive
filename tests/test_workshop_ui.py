"""真实控件：挑战计算、选项失效、取消与工程车辆交接。"""

from types import SimpleNamespace

import pytest
from direct.gui import DirectGuiGlobals as DGG

from lab_application import VehicleLab
from vehicle_workspace import WorkspaceVehicle
from workshop import build_config


@pytest.fixture
def workbench(tmp_path):
    app = VehicleLab(offscreen=True, output=tmp_path/"reports")
    app.engine.taskMgr.remove("lab-update")
    yield app
    app.close_game()


def finish(app):
    panel = app.workshop
    while panel.phase is not None:
        while not app.run_state.done:
            app.run_state.step()
        app.update(SimpleNamespace(cont=None))


def test_challenge_uses_real_trials_and_invalidates_unrun_selection(workbench):
    app = workbench
    panel = app.workshop
    panel.show()
    panel.share.set(2)
    panel.start()
    finish(app)
    assert panel.result["passed"] and panel.result["medal"] == "金"
    assert app.baseline is panel.baseline and app.record is panel.candidate
    assert panel.drive_button["state"] == DGG.NORMAL
    panel.show_insights()
    assert not panel.insights.root.isHidden() and panel.insights.data['passed']
    data = panel.insights.data
    assert panel.insights.primary_values[1].getText() == f"{data['primary'][2]:.3f} m"
    assert panel.insights.metric_rows[0][3].getText() == f"{data['rows'][0][2]-data['rows'][0][1]:+.3f}"
    assert panel.insights.budget_note.getText() == '预算内'
    state = app.capture_workspace()
    panel.brakes.set(1)
    assert panel.result is None and panel.drive_button["state"] == DGG.DISABLED
    app.workshop.restore(state.workshop_state)
    assert panel.result["passed"] and panel.selection() == (2, False)
    assert not panel.insights.root.isHidden()
    app.escape()
    assert panel.insights.root.isHidden() and not panel.root.isHidden()
    baseline, candidate = panel.baseline, panel.candidate
    panel.share.set(0)
    panel.candidate = panel.baseline
    panel.result = panel.evaluate_records()
    panel.present_result()
    panel.show_insights()
    panel.export_interpretation()
    assert app.last_report.parent.joinpath('insights.json').is_file()
    panel.prepare_next_trial()
    assert panel.selection() == (1, False) and panel.result is None and panel.phase is None
    assert panel.baseline is baseline and panel.candidate is baseline
    assert app.record is candidate and panel.insight_button['state'] == DGG.DISABLED
    panel.start()
    app.escape()
    assert panel.phase is None and app.run_state.paused and panel.result is None


def test_save_freezes_tested_hardware_and_failure_retains_result(workbench, tmp_path, monkeypatch):
    app = workbench
    panel = app.workshop
    panel.share.set(2)
    panel.start()
    finish(app)
    blocked = tmp_path/"blocked"
    blocked.write_text("file", encoding="utf-8")
    previous_output, previous_report = app.output, app.last_report
    app.output = blocked
    panel.export_interpretation()
    assert panel.result['passed'] and app.last_report == previous_report and app.workspace_vehicle is None
    app.notice.dismiss()
    app.output = previous_output
    monkeypatch.setattr("vehicle_workspace.workspace_vehicle_path", lambda: blocked/"vehicle.json")
    panel.drive()
    assert app.next_workspace is None and panel.result["passed"]
    app.notice.dismiss()
    path = tmp_path/"vehicle.json"
    monkeypatch.setattr("vehicle_workspace.workspace_vehicle_path", lambda: path)
    app.entries["cg"].enterText(".9")
    monkeypatch.setattr(app, "userExit", lambda: None)
    panel.drive()
    assert app.next_workspace == "game" and app.next_drive
    assert app.workspace_vehicle.config == build_config(2, False)
    assert WorkspaceVehicle.load(path) == app.workspace_vehicle
    assert any(folder.joinpath("challenge.json").is_file() for folder in app.output.iterdir())
