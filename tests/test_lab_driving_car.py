"""显式准备下一次硬件，不把旧回放或A基线改成新配方结果。"""

from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from application import CoastalDrive
from lab_application import VehicleLab
from lab_experiment import LabOptions
from race import GameMode
from vehicle_workspace import WorkspaceVehicle
from workshop_cornering import build_config


def finish(app, workspace):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    car = WorkspaceVehicle('reference-rwd', build_config(0, False, False))
    game = CoastalDrive(smoke=True, output=tmp_path/'game', lab_output=tmp_path/'reports', workspace_vehicle=car)
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.open_vehicle_lab()
    finish(game, 'lab')
    yield game
    game.close_game()


def trial(lab):
    lab.set_options(LabOptions(speed_kph=20., duration=.1, friction=.6))
    lab.start_experiment()
    while not lab.run_state.done:
        lab.run_state.step()
    lab.run_state.paused = True
    lab.record = lab.active_record()
    lab.refresh_plots()
    lab.show_sample(6)
    return lab.record


def test_missing_car_has_clear_error_and_no_state_mutation():
    errors = []
    lab = SimpleNamespace(workspace_vehicle=None, show_error=errors.append)
    VehicleLab.stage_driving_vehicle(lab)
    assert errors and '没有驾驶车辆' in errors[0]


def test_load_preserves_old_record_baseline_cursor_and_drafts_until_new_trial(app):
    lab = app.lab
    old = trial(lab)
    lab.pin_baseline()
    baseline, run, cursor, metric = lab.baseline, lab.run_state, lab.view_index, lab.metric.getText()
    config = build_config(3, False, False)
    config = replace(config, braking=replace(config.braking, abs_enabled=False),
                     stability=replace(config.stability, esc_enabled=True))
    car = WorkspaceVehicle('reference-rwd', config, {'basis': '当前驾驶配方'})
    lab.workspace_vehicle = car
    lab.entries['cg'].enterText('.47')
    lab.entries['tire_load'].enterText('3500')
    lab.manual_entries['throttle'].enterText('15')
    lab.driving_car_button['command']()
    assert lab.engineered_config == config and lab.parameter_metadata == car.parameter_metadata
    options = lab.read_options()
    assert options.friction == .6 and options.duration == .1 and options.speed_kph == 20.
    assert options.cg_height is options.tire_reference_load is None
    assert not options.abs_enabled and options.esc_enabled
    assert lab.manual_entries['throttle'].get() == '15'
    assert lab.record is old and lab.baseline is baseline and lab.run_state is run and not run.closed
    assert lab.view_index == cursor and lab.metric.getText() == metric
    assert '旧试验' in lab.model_note.getText()
    old_states = old.snapshots
    lab.start_experiment()
    while not lab.run_state.done:
        lab.run_state.step()
    new = lab.active_record()
    assert lab.baseline is baseline and baseline.snapshots == old_states
    assert new.metadata['vehicle_config']['lateral_stiffness'] == 70000.
    assert new.metadata['vehicle_config']['road_friction'] == .6
    assert new.metadata['summary']['options']['cg_height'] is None
    assert new.metadata['vehicle_config']['center_of_mass_height'] == car.config.center_of_mass_height


def test_staging_pauses_active_world_without_changing_a_or_creating_results(app):
    lab = app.lab
    lab.set_options(LabOptions(speed_kph=20., duration=1.))
    lab.start_experiment()
    lab.run_state.step()
    run = lab.run_state
    snapshot, count = run.snapshots[-1], len(run.snapshots)
    lab.workspace_vehicle = WorkspaceVehicle('reference-rwd', build_config(3, False, False))
    lab.stage_driving_vehicle()
    assert run.paused and not run.closed and run.snapshots[-1] == snapshot and len(run.snapshots) == count
    assert lab.baseline is None and lab.record is None and lab.run_state is run
    assert lab.engineered_config.lateral_stiffness == 70000.


def test_empty_trial_can_prepare_different_design_without_default_override(app):
    lab = app.lab
    old = lab.workspace_vehicle
    car = replace(old, design_id='reference-fwd', config=replace(old.config, front_drive_share=1., lateral_stiffness=70000.))
    lab.workspace_vehicle = car
    lab.stage_driving_vehicle()
    assert lab.run_state is lab.record is lab.baseline is None
    assert lab.engineered_vehicle_id == 'reference-fwd' and lab.engineered_config == car.config
    assert '当前驾驶车' in lab.model_note.getText()
    assert lab.read_options().vehicle_id == 'reference-fwd'


def test_actual_game_tuning_stages_new_car_after_old_workspace_return(app):
    lab = app.lab
    old = trial(lab)
    lab.pin_baseline()
    lab.entries['cg'].enterText('.47')
    lab.back_to_game()
    finish(app, 'game')
    app.back_to_menu()
    app.choose_slalom_lesson(GameMode.FAST_SLALOM)
    app.open_tire_tuning()
    app.tire_tuning.activate(3)
    app.tire_tuning.activate(4)
    fitted = app.workspace_vehicle
    before_file = app.workspace_path.read_bytes()
    app.back_from_tire_tuning()
    app.start_slalom_lesson()
    app.open_vehicle_lab()
    finish(app, 'lab')
    lab = app.lab
    assert lab.engineered_config.lateral_stiffness == 35000.
    lab.stage_driving_vehicle()
    assert lab.engineered_config == fitted.config and lab.record.snapshots == old.snapshots
    assert lab.baseline.snapshots == old.snapshots and lab.entries['cg'].get() == ''
    assert app.workspace_path.read_bytes() == before_file
    lab.back_to_game()
    finish(app, 'game')
    assert app.workspace_vehicle == fitted and app.session.mode == GameMode.FAST_SLALOM
    assert asdict(app.lab_workspace.config) == asdict(fitted.config)
