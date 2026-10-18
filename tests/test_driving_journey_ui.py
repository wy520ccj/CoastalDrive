"""真实进阶控件/键盘路由/同车分组与明确结算夹具；非人工体验。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from braking_lesson import BrakingScores
from driving_modes import DrivingMode
from race import GameMode
from session import Phase
from slalom_lesson import SlalomScores


@pytest.fixture
def app(tmp_path):
    game = CoastalDrive(smoke=True, output=tmp_path, render_size=(1024, 768))
    game.taskMgr.remove("finish-smoke")
    game.taskMgr.remove("drive-update")
    game.back_to_menu()
    game._shown_phase = None
    game.refresh_panel()
    yield game
    game.close_game()


def key(app, value):
    app.messenger.send(value)
    app.messenger.send(value+"-up")


def save(app, error, seconds):
    path, variant = app.session.race.scores.path, app.session.score_variant()
    BrakingScores(path.with_name("braking-best.json"), "braking-v1:"+variant).record(error)
    SlalomScores(path.with_name("slalom-best.json"), "slalom-v1:"+variant).record(seconds)


def test_registered_tab_enters_progress_without_moving_menu_and_returns_to_original_chapter(app):
    app.main_menu.select(7)
    key(app, "enter")
    assert "0 / 5" in app.journey.progress.getText()
    key(app, "tab")
    assert app.journey.root.isHidden() and not app.driving_journey.root.isHidden()
    assert "0 / 6" in app.driving_journey.progress.getText() and len(app.main_menu.buttons) == 8
    app.messenger.send("f2")
    assert not app.driving_mode_page
    selected = app.main_menu.selected
    key(app, "arrow_right")
    assert app.driving_journey.selected == 1 and app.main_menu.selected == selected
    key(app, "tab")
    assert app.driving_journey.root.isHidden() and "0 / 5" in app.journey.progress.getText()
    app.messenger.send("f2")
    assert not app.driving_mode_page
    app.open_driving_journey()
    key(app, "escape")
    assert app.driving_journey.root.isHidden() and app.session.phase == Phase.MENU


@pytest.mark.parametrize("index,mode,rule", [(0, GameMode.BRAKING_LESSON, "170米"),
                                           (1, GameMode.SLALOM_LESSON, "40km/h")])
def test_card_opens_existing_rules_preserves_hardware_and_cancel_clears_return(app, index, mode, rule):
    config, world, shape = app.session.vehicle_config, app.session.simulation, app.highway_shape
    app.open_driving_journey()
    app.driving_journey.buttons[index]["command"]()
    assert app.driving_journey.root.isHidden() and rule in app.panel_note.getText()
    assert app.session.simulation is world and app.session.vehicle_config == config and app.highway_shape == shape
    key(app, "escape")
    assert app.highway_menu and not app.driving_journey_return
    app.open_driving_journey()
    app.driving_journey.buttons[index]["command"]()
    app.buttons[0]["command"]()
    assert app.session.mode == mode and app.session.vehicle_config == config


def test_best_gaps_balanced_recommendation_and_visible_bounds(app):
    save(app, 7., 17.)
    app.open_driving_journey()
    panel = app.driving_journey
    assert "3 / 6" in panel.progress.getText() and panel.selected == 0
    assert "2.000m" in panel.details[0].getText() and "2.000s" in panel.details[1].getText()
    assert "银牌 ≤5m" in panel.summary.getText()
    for detail, button in zip(panel.details, panel.buttons[:2], strict=True):
        lower, upper = detail.getTightBounds(panel.root)
        assert lower.z > button.getZ()+button["frameSize"][3]+.005
        assert upper.x < 1.56 and lower.x > -1.52
    save(app, 1., 14.)
    app.open_driving_journey()
    assert "6 / 6" in panel.progress.getText() and "双项金牌达成" in panel.summary.getText()
    assert all("刷新最佳" in button["text"] for button in panel.buttons[:2])
    app.open_workshop_journey()
    assert app.journey.data["steps"] == 1 and "1 / 5" in app.journey.progress.getText()


def test_hardware_electronics_input_groups_keep_other_progress_without_rewriting_files(app):
    save(app, 1., 14.)
    path = app.session.race.scores.path
    originals = {name: path.with_name(name).read_bytes() for name in ("braking-best.json", "slalom-best.json")}
    original = app.session.vehicle_config
    app.session.set_vehicle_config(replace(original, center_of_mass_height=.401))
    app.open_driving_journey()
    assert app.driving_journey.data["steps"] == 0
    app.session.set_vehicle_config(original)
    app.session.set_abs_enabled(not app.session.abs_enabled)
    app.open_driving_journey()
    assert app.driving_journey.data["steps"] == 0
    app.session.set_abs_enabled(not app.session.abs_enabled)
    app.session.set_driving_mode(DrivingMode.SIMULATION)
    app.open_driving_journey()
    assert app.driving_journey.data["steps"] == 0 and "直接输入" in app.driving_journey.vehicle.getText()
    app.session.set_driving_mode(DrivingMode.GAME)
    app.open_driving_journey()
    assert app.driving_journey.data["steps"] == 6
    assert all(path.with_name(name).read_bytes() == raw for name, raw in originals.items())


def test_failed_course_returns_to_progress_without_new_award_and_old_entry_keeps_menu(app):
    save(app, 7., 17.)
    app.open_driving_journey()
    app.driving_journey.activate(1)
    app.buttons[0]["command"]()
    for _ in range(360):
        app.session.tick()
    highway = app.session.highway.snapshot
    failed = replace(highway.slalom, finished=True, reason="车辆复位", succeeded=False)
    app.session.highway.snapshot = replace(highway, slalom=failed, finished=True, running=False, reason=failed.reason)
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    assert app.buttons[2]["text"] == "查看驾驶进阶"
    app.buttons[2]["command"]()
    assert app.session.phase == Phase.MENU and not app.driving_journey.root.isHidden()
    assert app.driving_journey.data["steps"] == 3 and not app.driving_journey_return
    app.driving_journey.hide()
    app.choose_highway()
    app.choose_slalom_lesson()
    app.buttons[0]["command"]()
    assert not app.driving_journey_return


def test_same_window_lab_return_keeps_explicit_progress_origin(app):
    app.open_driving_journey()
    app.driving_journey.activate(1)
    app.buttons[0]["command"]()
    window = app.win
    app.open_vehicle_lab()
    for target in ("lab", "game"):
        if target == "game":
            app.lab.back_to_game()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == target and app._workspace_steps is None
        app.taskMgr.remove("lab-update" if target == "lab" else "drive-update")
    assert app.win is window and app.session.mode == GameMode.SLALOM_LESSON
    assert app.driving_journey_return
