"""实际主菜单初章入口、模态键盘与同窗项目定位。"""

import gzip
from dataclasses import replace
from pathlib import Path

import pytest

from application import CoastalDrive
from braking_lesson import BrakingScores
from lab_records import load_record
from race import GameMode
from session import Phase
from vehicle_schemes import load_scheme

ROOT = Path(__file__).resolve().parents[1]
CORNER_ID = "e8009496ea504a31b63bdd5e754955b5"


def restore_saved_scheme(root):
    """使用已提交真实道路圈的原始数据，不重跑/伪造驾驶成绩。"""
    source = ROOT/"tests/data/fixtures/DESIGN-SCHEMES-01/normal/schemes"/CORNER_ID
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        target = root/CORNER_ID/path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = target.with_suffix("") if path.suffix == ".gz" else target
        target.write_bytes(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())
    return load_scheme(root, CORNER_ID)


def finish(app, target):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app._workspace_steps is None and app.workspace == target
    app.taskMgr.remove("lab-update" if target == "lab" else "drive-update")


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


def press(app, key):
    app.key_down(key)
    app.key_up(key)


def test_workshop_modal_keyboard_close_and_main_free_choice_remain(app):
    assert len(app.main_menu.buttons) == len(app.main_menu.actions) == 9
    app.open_workshop_garage()
    assert not app.workshop_garage.root.isHidden()
    original = app.main_menu.selected
    press(app, "arrow_right")
    assert app.workshop_garage.selected == 1 and app.main_menu.selected == original
    press(app, "escape")
    assert app.workshop_garage.root.isHidden() and app.session.phase == Phase.MENU
    app.open_workshop_garage()
    app.workshop_garage.activate(5)
    assert app.workshop_garage.root.isHidden()
    app.main_menu.select(1)
    app.main_menu.activate()
    assert app.session.mode == GameMode.TIME_TRIAL


def test_new_project_opens_correct_workshop_and_returns_same_window(app):
    window = app.win
    app.open_workshop_journey()
    app.journey.buttons[1]["command"]()
    finish(app, "lab")
    assert app.win is window and app.lab.workshop.topic == 1
    assert not app.lab.workshop.root.isHidden() and app.lab_journey_request is None
    app.lab.entries["cg"].enterText(".46")
    app.lab.back_to_game()
    finish(app, "game")
    app.open_workshop_journey()
    app.journey.buttons[0]["command"]()
    finish(app, "lab")
    assert app.win is window and app.lab.workshop.topic == 0
    assert app.lab.entries["cg"].get() == ".46"


def test_saved_pending_project_locates_exact_scheme_and_drives_frozen_hardware(app):
    item = restore_saved_scheme(app.scheme_root)
    pending = replace(item.vehicle, workshop_result={**item.vehicle.workshop_result, "road_validated": False})
    pending.save(item.folder/"vehicle.json")
    app.open_workshop_journey()
    assert app.journey.data["steps"] == 1 and "道路待验证" in app.journey.details[1].getText()
    app.journey.buttons[1]["command"]()
    finish(app, "lab")
    assert not app.lab.schemes.root.isHidden()
    assert app.lab.schemes.selected(1).id == CORNER_ID
    app.lab.schemes.drive_right()
    finish(app, "game")
    assert app.workspace_vehicle.scheme_id == CORNER_ID
    assert app.workspace_vehicle.config == item.vehicle.config
    assert app.session.mode == GameMode.FREE_DRIVE


def test_file_corruption_after_open_does_not_replace_current_world_or_vehicle(app):
    item = restore_saved_scheme(app.scheme_root)
    app.open_workshop_journey()
    world, vehicle = app.session.simulation, app.workspace_vehicle
    (item.folder/"trial"/"snapshots.bin").write_bytes(b"bad")
    app.journey.buttons[1]["command"]()
    assert not app.journey.root.isHidden() and "不可继续" in app.journey.notice.getText()
    assert app.session.simulation is world and not world.closed and app.workspace_vehicle == vehicle


def test_braking_card_uses_current_hardware_and_opens_original_rules(app):
    key = "braking-v1:"+app.session.score_variant()
    scores = BrakingScores(app.session.race.scores.path.with_name("braking-best.json"), key)
    scores.record(1.5)
    app.open_workshop_journey()
    assert "金牌" in app.journey.details[2].getText()
    app.journey.buttons[2]["command"]()
    assert app.braking_menu and "170米" in app.panel_note.getText()
    app.back_to_modes()
    app.session.set_esc_enabled(not app.session.esc_enabled)
    app.open_workshop_journey()
    assert app.journey.data["projects"][2]["steps"] == 0
    assert "尚无停车成绩" in app.journey.details[2].getText()


def test_legacy_single_vehicle_restores_its_real_award_without_a_scheme_library(app):
    item = restore_saved_scheme(app.output/"legacy")
    legacy = replace(item.vehicle, scheme_id=None)
    app.workspace_vehicle = legacy
    app.session.set_vehicle_config(legacy.config)
    app.session.set_abs_enabled(legacy.config.braking.abs_enabled)
    app.session.set_tcs_enabled(legacy.config.traction.tcs_enabled)
    app.session.set_esc_enabled(legacy.config.stability.esc_enabled)
    app.open_workshop_journey()
    assert app.journey.data["projects"][1]["scheme_id"] is None
    assert app.journey.data["steps"] == 2
    app.journey.buttons[1]["command"]()
    finish(app, "lab")
    assert not app.lab.workshop.root.isHidden() and app.lab.workshop.topic == 1
    assert app.lab.workshop.historical['medal'] == '金' and app.lab.workshop.result is None
    assert app.lab.record.snapshots == item.records()[1].snapshots


def test_unsaved_trial_survives_returning_to_the_same_project(app):
    item = restore_saved_scheme(app.output/"historical-input")
    app.open_workshop_journey()
    app.journey.buttons[1]["command"]()
    finish(app, "lab")
    assert app.lab.import_record(item.folder/"trial")
    app.lab.baseline = load_record(item.folder/"trial"/"baseline-A")
    app.lab.workshop.restore_saved(item.vehicle)
    before = app.lab.workshop.capture()
    app.lab.back_to_game()
    finish(app, "game")
    app.open_workshop_journey()
    assert app.journey.data["steps"] == 0
    app.journey.buttons[1]["command"]()
    finish(app, "lab")
    assert app.lab.workshop.result == before["result"]
    assert app.lab.workshop.candidate.snapshots == before["candidate"].snapshots
    assert app.lab.workshop.historical == before['historical']
    assert app.lab.workshop.capture()['drafts'] == before['drafts']
