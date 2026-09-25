"""Offline H4A visual and lifecycle checks for the current application APIs."""

import json
import math
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panda3d.core import Filename, Vec3

from application import CoastalDrive
from coastal_map import point_at
from controls import ConstantController
from race import GameMode
from simulation import Control, interpolate
from skins import SKINS, traffic_models
from tracks import COASTAL_CIRCUIT

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "logs/h4a/ui"


def render(app, frame, path):
    app.taskMgr.step()
    app.update(frame)
    app.graphicsEngine.renderFrame()
    app.graphicsEngine.renderFrame()
    assert app.win.saveScreenshot(Filename.fromOsSpecific(str(OUTPUT / path)))


def render_camera(app, path, position, target):
    app.camera.setPos(position)
    app.camera.lookAt(target)
    app.graphicsEngine.renderFrame()
    app.graphicsEngine.renderFrame()
    assert app.win.saveScreenshot(Filename.fromOsSpecific(str(OUTPUT / path)))


def visible_wheels(app):
    return sum(not wheel.isHidden() for wheels in app.scene.traffic_wheels for wheel in wheels)


def checkpoint_masks(app):
    return [
        body.getIntoCollideMask().getWord()
        for body in app.session.simulation._prop_bodies
        if body.getName().startswith("checkpoint")
    ]


def place_behind(app, traffic_index, distance=10.0):
    car = app.session.current.traffic[traffic_index]
    angle = math.radians(car.heading)
    forward = Vec3(-math.sin(angle), math.cos(angle), 0)
    position = Vec3(*car.position) - forward * distance
    app.session.simulation.reset_player(tuple(position), car.heading, car.pitch)
    app.session.simulation.player.reverse_enabled = False
    app.session.sync_snapshots()
    app.session.set_controller(ConstantController(Control(brake=1.0)))
    for _ in range(240):
        app.session.tick()
    assert app.session.current.tick >= 240
    app.scene.apply(app.session.current)
    app.scene.update_lighting(Vec3(*app.session.current.player.position))
    car = app.session.current.traffic[traffic_index]
    return Vec3(*app.session.current.player.position), Vec3(*car.position)


def start_live(app, mode, track):
    app.session.start(mode=mode, track=track, countdown=False)
    app.sync_scene()
    app.session.simulation.player.reverse_enabled = False
    app.session.set_controller(ConstantController(Control(brake=1.0)))


def settle_traffic(app, ticks=240):
    """Stop every NPC before placing the player for a close view."""
    for driver in app.session.simulation.drivers:
        driver.cruise = 0
    app.session.simulation.player.reverse_enabled = False
    app.session.set_controller(ConstantController(Control(brake=1.0)))
    for _ in range(ticks):
        app.session.tick()
    assert app.session.current.tick >= ticks
    assert all(abs(car.speed) < 0.5 for car in app.session.current.traffic if car.active)


def settle_player(app, ticks=240):
    """Advance two seconds at the fixed step before taking a grounded view."""
    app.session.simulation.player.reverse_enabled = False
    app.session.set_controller(ConstantController(Control(brake=1.0)))
    for _ in range(ticks):
        app.session.tick()
    state = app.session.current
    assert state.tick >= ticks
    app.scene.apply(state)
    app.scene.update_lighting(Vec3(*state.player.position))
    return state


def advance_and_render(app, frame, count=240):
    for _ in range(count):
        app.session.tick()
    state = app.session.current
    app.scene.apply(state)
    app.scene.update_lighting(Vec3(*state.player.position))
    render(app, frame, "settled.png")


def assert_wheels_grounded(app, state):
    sim = app.session.simulation
    vehicles = ((state.player, sim.player), *zip(state.traffic, sim.npcs))
    for car, vehicle in vehicles:
        if not getattr(car, "active", True):
            continue
        contacts = [wheel.getRaycastInfo().isInContact() for wheel in vehicle._vehicle.getWheels()]
        assert all(contacts)
        for wheel in car.wheels:
            ground = app.session.simulation.ground_height(wheel.position[0], wheel.position[1])
            assert 0.30 <= wheel.position[2] - ground <= 0.36


def checkpoint_camera_probe(app):
    """Probe the actual checkpoint beams from three longitudinal positions."""
    assert app.session.mode == GameMode.TIME_TRIAL
    masks = checkpoint_masks(app)
    assert masks and all(mask & 2 and not (mask & 4) for mask in masks)
    probes = []
    for distance in COASTAL_CIRCUIT.checkpoints:
        for delta in (-3.0, 0.0, 3.0):
            before = point_at(distance + delta - 3.0)
            after = point_at(distance + delta + 3.0)
            anchor = Vec3(before.x, before.y, before.z + 3.35)
            desired = Vec3(after.x, after.y, after.z + 3.35)
            # Each ray crosses the actual beam location; bit 2 must keep it
            # transparent to the chase camera while bit 1 remains enabled.
            actual = app.session.simulation.camera_position(anchor, desired)
            probes.append((distance, delta, (actual - desired).length()))
    assert all(error < 1e-6 for _, _, error in probes)
    return probes


def render_benchmark(app, count, frames=120):
    """Measure fixed-step CPU/update time separately from render submission/wait."""
    start_live(app, GameMode.FREE_DRIVE, "highway")
    if count != len(app.session.current.traffic):
        app.session.simulation.traffic_count = count
        app.session.simulation.reset(app.session.seed)
        app.session.sync_snapshots()
        app.sync_scene()
    cpu = submit = 0.0
    for _ in range(frames):
        started = time.perf_counter()
        app.session.tick()
        app.session.tick()
        state = app.session.current
        app.scene.apply(state)
        app.scene.update_lighting(Vec3(*state.player.position))
        cpu += time.perf_counter() - started
        started = time.perf_counter()
        app.taskMgr.step()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        submit += time.perf_counter() - started
    assert app.session.current.tick >= frames * 2
    assert_wheels_grounded(app, app.session.current)
    return {
        "traffic_count": count,
        "frames": frames,
        "simulation_ticks": app.session.current.tick,
        "cpu_update_seconds": round(cpu, 4),
        "render_submit_wait_seconds": round(submit, 4),
        "cpu_update_ms_per_frame": round(cpu * 1000 / frames, 3),
        "render_submit_wait_ms_per_frame": round(submit * 1000 / frames, 3),
        "renderer": app.win.getGsg().getDriverRenderer(),
        "measurement_note": "CPU update and Panda3D render submission/wait; no independent GPU timing claimed",
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=OUTPUT, seed=0)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    frame = type("Frame", (), {"cont": None})()
    results = {}

    try:
        app.session.menu()
        render(app, frame, "menu.png")

        # Do not capture the initial, pre-settle tick.  Advance two seconds
        # with reverse disabled and brake held, then sync scene and lighting.
        start_live(app, GameMode.FREE_DRIVE, "coastal")
        state = settle_player(app, 240)
        render(app, frame, "coastal-free.png")
        assert_wheels_grounded(app, state)
        assert len(app.scene.traffic) == len(app.session.current.traffic) == 8
        assert len(app.scene.traffic_wheels) == 8
        assert visible_wheels(app) == 32
        assert all(car.active for car in app.session.current.traffic)
        results["coastal_free_has_8_cars_and_32_visible_wheels"] = True

        app.start_game(mode=GameMode.TIME_TRIAL, track="coastal")
        assert len(app.session.current.traffic) == 0
        assert len(app.scene.traffic) == 0
        results["timed_coastal_has_zero_traffic"] = True

        start_live(app, GameMode.FREE_DRIVE, "highway")
        state = settle_player(app, 240)
        render(app, frame, "highway-free.png")
        assert_wheels_grounded(app, state)
        assert len(app.scene.traffic) == len(app.session.current.traffic) == 8
        assert visible_wheels(app) == 32
        assert all(car.active for car in app.session.current.traffic)
        results["highway_free_has_8_cars_and_32_visible_wheels"] = True

        # Put the player 10 m behind one active NPC and capture both models from
        # two view angles.  The target is kept inside the scene's active window.
        settle_traffic(app, 240)
        indices = {
            name: traffic_models(0, 8).index(name)
            for name in ("player-car.glb", "traffic-sedan.glb")
        }
        for label, index in (
            ("sports", indices["player-car.glb"]),
            ("sedan", indices["traffic-sedan.glb"]),
        ):
            player, npc = place_behind(app, index, 10.0)
            assert 8.0 <= (npc - player).length() <= 12.0
            car = app.session.current.traffic[index]
            assert car.active
            assert_wheels_grounded(app, app.session.current)
            app.scene.apply(app.session.current)
            for angle, offset in (("rear", Vec3(7, -10, 4)), ("side", Vec3(11, 2, 3.5))):
                render_camera(
                    app,
                    f"traffic-close-{label}-{angle}.png",
                    player + offset,
                    npc + Vec3(0, 0, 0.55),
                )
            assert all(not wheel.isHidden() for wheel in app.scene.traffic_wheels[index])
        results["close_traffic_sedan_and_sports_rendered"] = True

        # Free-drive checkpoint frames are absent from the scene and disabled
        # in Bullet; time-trial enables bit 1 for race tracking while bit 2
        # stays clear so the chase-camera ray passes through the beam.
        start_live(app, GameMode.FREE_DRIVE, "coastal")
        assert not app.scene.render.findAllMatches("**/checkpoint*").getNumPaths()
        assert all(mask == 0 for mask in checkpoint_masks(app))
        start_live(app, GameMode.TIME_TRIAL, "coastal")
        probes = checkpoint_camera_probe(app)
        results["free_checkpoint_frames_have_no_render_or_collision"] = True
        results["checkpoint_camera_beams_transparent_at_minus_zero_plus_3m"] = {
            "probes": len(probes),
            "max_camera_error_m": max(error for _, _, error in probes),
            "mask": checkpoint_masks(app)[0],
        }

        # Repeated mode changes must replace the scene rather than accumulate it.
        mode_counts = {}
        for mode, track, expected in (
            (GameMode.FREE_DRIVE, "coastal", 8),
            (GameMode.FREE_DRIVE, "highway", 8),
            (GameMode.TIME_TRIAL, "coastal", 0),
        ):
            values = []
            for _ in range(4):
                app.start_game(mode=mode, track=track)
                values.append(app.scene.render.findAllMatches("**").getNumPaths())
            assert len(set(values)) == 1
            assert len(app.scene.traffic) == expected
            mode_counts[f"{mode.value}:{track}"] = values[0]
        results["mode_switch_scene_node_counts_stable"] = True
        results["mode_switch_node_counts"] = mode_counts

        # Route the paint change through the menu button callback, preserving
        # the exact application entry point used by players.
        app.session.menu()
        before = app.session.simulation.snapshot()
        for index in range(len(SKINS)):
            app.buttons[3]["command"]()
            assert app.session.simulation.snapshot() == before
            assert SKINS[app.skin_index].name in app.buttons[3]["text"]
        results["menu_skin_changes_leave_physics_unchanged"] = True

        # A generation/active transition must snap to the new traffic state;
        # interpolating it would create a visible flying car between slots.
        start_live(app, GameMode.FREE_DRIVE, "highway")
        highway = app.session.simulation.snapshot()
        old = highway.traffic[0]
        new = replace(
            old,
            position=(old.position[0], old.position[1] + 200, old.position[2]),
            generation=old.generation + 1,
        )
        current = replace(highway, traffic=(new, *highway.traffic[1:]))
        midpoint = interpolate(highway, current, 0.5)
        assert midpoint.traffic[0] == new
        results["interpolate_recycle_snaps_without_flying"] = True

        results["render_120_frame_cpu_and_submit_wait"] = {
            "cars_8": render_benchmark(app, 8),
            "cars_16": render_benchmark(app, 16),
        }

        results["passed"] = True
    finally:
        app.close_game()
    (OUTPUT / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
