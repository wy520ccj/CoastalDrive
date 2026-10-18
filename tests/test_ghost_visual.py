"""真实车辆网格的幽灵装配；只显示，不进入物理或阴影相机。"""

from dataclasses import replace

import pytest
from panda3d.core import BitMask32

from application import CoastalDrive
from ghost_visual import GHOST_MASK
from lap_ghost import GhostRecorder
from race import GameMode, RaceSnapshot
from session import Phase
from vehicle_state import FIXED_DT


def visual_fixture(state):
    car = state.player
    shift = (0., 15., 0.)
    car = replace(car, position=tuple(a+b for a, b in zip(car.position, shift)),
                  wheels=tuple(replace(wheel, position=tuple(a+b for a, b in zip(wheel.position, shift)))
                               for wheel in car.wheels))
    first = replace(state, player=car)
    recorder = GhostRecorder(first, {"source": "visual-fixture"})
    recorder.append(replace(first, tick=first.tick+1, time=first.time+FIXED_DT))
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, finished=True, new_best=True,
                        last_lap=FIXED_DT, splits=(FIXED_DT,))
    return recorder.finish("visual-fixture", race)


@pytest.fixture
def app(tmp_path):
    game = CoastalDrive(smoke=True, output=tmp_path)
    game.taskMgr.remove("finish-smoke")
    game.taskMgr.remove("drive-update")
    yield game
    game.close_game()


def test_ghost_has_no_rigid_body_or_shadow_and_fades_near_player(app):
    state = app.session.current
    count = app.session.simulation._world.getNumRigidBodies()
    lap = visual_fixture(state)
    app.scene.set_ghost(lap)
    assert app.scene.ghost is not None and not app.scene.ghost_error
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, start_time=state.time)
    app.scene.apply_ghost(state, race, True)
    ghost = app.scene.ghost
    assert not ghost.root.isHidden(GHOST_MASK)
    assert app.scene.sun_path.node().getCameraMask() & GHOST_MASK == BitMask32.allOff()
    assert ghost.root.node().getDrawShowMask() & app.cam.node().getCameraMask() == GHOST_MASK
    assert tuple(ghost.body.getPos()) == pytest.approx(lap.pose_at(0.).position)
    assert len(ghost.wheels) == 4
    for node, wheel in zip(ghost.wheels, lap.pose_at(0.).wheels):
        assert tuple(node.getPos()) == pytest.approx(wheel.position)
    assert app.session.simulation._world.getNumRigidBodies() == count
    assert app.session.simulation.snapshot() == state
    overlap = replace(state, player=replace(state.player, position=lap.pose_at(0.).position))
    app.scene.apply_ghost(overlap, race, True)
    assert ghost.root.isHidden(GHOST_MASK)
    app.scene.apply_ghost(state, race, False)
    assert ghost.root.isHidden(GHOST_MASK)
    app.scene.apply_ghost(state, replace(race, invalidated=True), True)
    assert ghost.root.isHidden(GHOST_MASK)


def test_g_and_button_only_toggle_display_and_not_repeated_key_events(app):
    state = app.session.current
    app.session.reference_ghost = visual_fixture(state)
    app.session.mode, app.session.phase = GameMode.TIME_TRIAL, Phase.DRIVING
    app.sync_scene()
    app.key_down("g")
    app.key_down("g")
    assert not app.ghost_enabled and "关闭" in app.ghost_button["text"]
    app.key_up("g")
    app.ghost_button["command"]()
    assert app.ghost_enabled and "开启" in app.ghost_button["text"]
    assert app.session.current == state and app.session.simulation.snapshot() == state


@pytest.mark.parametrize("error", [FileNotFoundError, ValueError, RuntimeError])
def test_missing_or_invalid_ghost_asset_keeps_main_scene_and_world(app, monkeypatch, error):
    state = app.session.current
    original = app.scene.player

    def fail(*args, **kwargs):
        raise error("unavailable ghost asset")

    monkeypatch.setattr("ghost_visual.load_vehicle", fail)
    app.scene.set_ghost(visual_fixture(state))
    assert app.scene.ghost is None and app.scene.ghost_error
    assert app.scene.player is original and app.session.simulation.snapshot() == state
    assert app.scene.render.find("**/personal-best-ghost").isEmpty()
