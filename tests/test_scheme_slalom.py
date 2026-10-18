"""冻结方案过门意图、原实验/复盘交接和失败边界。"""

from dataclasses import replace

import pytest
from direct.gui import DirectGuiGlobals as DGG
from scheme_slalom_check import finish, prepare

from application import CoastalDrive
from driving_modes import DrivingMode
from race import GameMode
from road_comparison import RoadResults, RoadTrial
from vehicle_schemes import save_scheme
from vehicle_workspace import WorkspaceVehicle


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path/"user"))
    game = CoastalDrive(smoke=True, output=tmp_path/"game", lab_output=tmp_path/"reports")
    game.taskMgr.remove("finish-smoke")
    game.taskMgr.remove("drive-update")
    game.back_to_menu()
    yield game
    game.close_game()


def test_explicit_b_slalom_overrides_workshop_and_preserves_reference_and_review(app):
    app.session.set_driving_mode(DrivingMode.SIMULATION)
    panel, better = prepare(app, "normal")
    lab, window, reference, run = app.lab, app.win, app.lab.record, app.lab.run_state
    frozen = tuple(panel.comparison.records)
    panel.review.drive_button["command"]()
    finish(app, "game")
    assert run.closed and app.win is window and app.lab is None
    assert app.session.mode == GameMode.SLALOM_LESSON and not app.session.simulation.npcs
    assert app.session.driving_mode == DrivingMode.SIMULATION
    assert app.workspace_vehicle.scheme_id == better.id
    assert app.session.vehicle_config == better.vehicle.config
    assert app.lab_workspace.record.snapshots == reference.snapshots
    assert app.lab_workspace.fields["cg"] == ".48"
    assert app.lab_workspace.road_state["records"] == frozen
    assert lab._closed
    app.open_vehicle_lab()
    finish(app, "lab")
    restored = app.lab.schemes.virtual_driver
    assert isinstance(restored.comparison, RoadResults) and restored.comparison.records == frozen
    assert not restored.review.root.isHidden() and restored.review.slider["value"] == 220.
    assert restored.identities[1] == better.id and app.lab.entries["cg"].get() == ".48"
    assert app.lab.record.snapshots == reference.snapshots
    assert app.lab.run_state is None


def test_existing_workshop_drive_still_chooses_coastal_time_trial(app):
    _, better = prepare(app, "normal")
    app.lab.schemes.drive_right()
    finish(app, "game")
    assert app.session.mode == GameMode.TIME_TRIAL and app.session.simulation.track == "coastal"
    assert app.workspace_vehicle.scheme_id == better.id


def test_leaving_active_virtual_trial_closes_world_and_restores_partial_only(app):
    panel, _ = prepare(app, "normal")
    panel.review.hide()
    panel.start()
    for _ in range(12):
        panel.comparison.run.step()
    world = panel.comparison.run.simulation
    app.lab.back_to_game()
    assert world.closed and app.lab_workspace.road_state["status"] == "cancelled"
    finish(app, "game")
    app.open_vehicle_lab()
    finish(app, "lab")
    panel = app.lab.schemes.virtual_driver
    assert len(panel.comparison.records) == 1 and len(panel.comparison.records[0].rows) == 12
    assert panel.drive_button["state"] == DGG.DISABLED


def test_bad_or_missing_b_keeps_current_vehicle_and_comparison(app):
    panel, better = prepare(app, "normal")
    vehicle, records = app.lab.workspace_vehicle, panel.comparison.records
    (better.folder/"trial/snapshots.bin").write_bytes(b"broken")
    panel.drive_slalom()
    assert app.workspace == "lab" and not app.lab.next_drive
    assert app.lab.workspace_vehicle == vehicle and panel.comparison.records == records
    assert not panel.review.root.isHidden()


def test_failed_save_keeps_lab_and_does_not_change_current_car(app, monkeypatch):
    panel, _ = prepare(app, "normal")
    original = app.lab.workspace_vehicle
    def failure(self, path=None):
        raise OSError("测试保存失败")
    monkeypatch.setattr(WorkspaceVehicle, "save", failure)
    panel.drive_slalom()
    assert app.workspace == "lab" and not app.lab.next_slalom and app.lab.workspace_vehicle == original


def test_changed_frozen_hardware_is_rejected_before_driving(app, monkeypatch):
    from types import SimpleNamespace
    panel, better = prepare(app, "normal")
    original_records = better.records()
    changed = replace(better.vehicle, config=replace(better.vehicle.config, lateral_stiffness=70000.))
    monkeypatch.setattr("ui.virtual_driver.load_scheme", lambda *args: SimpleNamespace(
        vehicle=changed, records=lambda: original_records))
    panel.drive_slalom()
    assert not app.lab.next_drive and app.workspace == "lab"


def test_missing_b_after_return_never_substitutes_another_scheme(app, tmp_path):
    panel, better = prepare(app, "normal")
    frozen = tuple(panel.comparison.records)
    panel.drive_slalom()
    finish(app, "game")
    better.folder.rename(tmp_path/"removed-test-scheme")
    app.open_vehicle_lab()
    finish(app, "lab")
    panel = app.lab.schemes.virtual_driver
    assert panel.identities[1] == better.id and panel.comparison.records == frozen
    panel.drive_slalom()
    assert app.workspace == "lab" and not app.lab.next_drive
    assert app.lab.workspace_vehicle.scheme_id == better.id


def test_original_low_friction_is_preserved_and_differs_from_virtual_baseline(app):
    from lab_experiment import LabOptions
    panel, _ = prepare(app, "normal")
    lab = app.lab
    lab.set_options(LabOptions(duration=.1, friction=.6))
    lab.start_experiment()
    while not lab.run_state.done:
        lab.run_state.step()
    item = save_scheme(lab.scheme_root, "低附着原方案", lab.active_record())
    assert item.vehicle.config.road_friction == .6
    lab.run_state.close()
    lab.record = lab.active_record()
    lab.run_state = None
    records = []
    for _ in range(2):
        run = RoadTrial(item.vehicle)
        try:
            run.step()
            run.stop("cancelled")
            records.append(run.record())
        finally:
            run.close()
    panel.identities, panel.names = (item.id, item.id), (item.name, item.name)
    panel.comparison = RoadResults(tuple(records), "cancelled")
    panel.present()
    assert "μ=0.6" in panel.drive_note.getText() and "μ=1.1" in panel.drive_note.getText()
    assert records[1].metadata["actual_config"]["road_friction"] == 1.1
    panel.drive_slalom()
    finish(app, "game")
    assert app.session.vehicle_config.road_friction == .6
    assert app.workspace_vehicle.config == item.vehicle.config


def test_success_display_fixture_does_not_award_unverified_coastal_progress(app):
    from session import Phase
    panel, better = prepare(app, "normal")
    pending = replace(better.vehicle, workshop_result={**better.vehicle.workshop_result, "road_validated": False})
    pending.save(better.folder/"vehicle.json")
    original = (better.folder/"vehicle.json").read_bytes()
    panel.drive_slalom()
    finish(app, "game")
    for _ in range(360):
        app.session.tick()
    result = app.session.highway.snapshot
    passed = replace(result.slalom, finished=True, succeeded=True, gates=6, run_seconds=14., medal="金")
    app.session.highway.snapshot = replace(result, finished=True, succeeded=True, slalom=passed)
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    assert not app.workspace_vehicle.workshop_result["road_validated"]
    assert (better.folder/"vehicle.json").read_bytes() == original


def test_explicit_journey_navigation_hides_restored_road_review(app):
    panel, _ = prepare(app, "normal")
    panel.drive_slalom()
    finish(app, "game")
    app.continue_workshop_project({"topic": 0, "scheme_id": None, "vehicle": None})
    finish(app, "lab")
    assert app.lab.workshop.topic == 0 and not app.lab.workshop.root.isHidden()
    assert app.lab.schemes.virtual_driver.root.isHidden()
