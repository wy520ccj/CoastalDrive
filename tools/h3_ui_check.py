"""Exercise H3 through the application, render results and keep test records separate."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from panda3d.core import Filename, Vec3
from route_driver import RouteDriver

from application import CoastalDrive
from coastal_map import point_at
from race import GameMode
from session import Phase
from simulation import Control
from skins import SKINS, apply_skin
from tracks import COASTAL_CIRCUIT


def main():
    output = Path(__file__).resolve().parents[1] / "logs/h3-review/ui"
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=output)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    frame = type("Frame", (), {"cont": None})()
    results = {}

    def capture(name):
        # Physics is advanced in batches below; snap the camera to the sampled state.
        app.chase_camera.position = None
        app.taskMgr.step()
        app.update(frame)
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output / f"{name}.png")))

    try:
        app.session.menu()
        capture("menu")
        app.start_game(mode=GameMode.FREE_DRIVE, track="highway")
        capture("highway")
        app.session.menu()
        capture("highway-menu")
        app.messenger.send("enter")
        app.messenger.send("enter-up")
        capture("enter-coastal")
        assert app._scene_track == app.session.simulation.track == "coastal"
        assert len(app.scene.traffic) == 4
        results["keyboard_switch_keeps_scene_and_physics_together"] = True
        for _ in range(360):
            app.session.tick()
        app.session.set_controller(RouteDriver())
        for _ in range(3500):
            app.session.tick()
        capture("checkpoint-progress")
        assert app.session.race.snapshot.checkpoints >= 2
        for _ in range(5000):
            app.session.tick()
        capture("valid-result")
        result = app.session.race.snapshot
        assert app.session.phase == Phase.RESULTS and result.finished and not result.invalidated
        results["actual_lap_time"] = result.last_lap
        app.start_game(mode=GameMode.TIME_TRIAL)
        for _ in range(360):
            app.session.tick()
        app.session.reset_player()
        capture("reset-invalid")
        assert app.session.race.snapshot.invalidated
        results["invalid_attempt_is_visible"] = "本次无效" in app.status.getText()
        app.session.menu()
        counts = []
        for _ in range(10):
            for track in ("highway", "coastal"):
                app.start_game(mode=GameMode.FREE_DRIVE, track=track)
            counts.append(app.scene.render.findAllMatches("**").getNumPaths())
        assert len(set(counts)) == 1
        results["twenty_map_switches_stable"] = True
        point = point_at(COASTAL_CIRCUIT.checkpoints[0] - 12)
        app.session.simulation.reset_player((point.x, point.y, point.z + 0.55), point.heading)
        for _ in range(240):
            app.session.simulation.step(Control())
        app.session.sync_snapshots()
        capture("solid-checkpoint")
        app.start_game(mode=GameMode.FREE_DRIVE, track="highway")
        for _ in range(600):
            app.session.tick()
        car = app.session.current.traffic[0]
        app.session.simulation.reset_player((car.position[0], car.position[1] - 10, 0.55))
        for _ in range(60):
            app.session.tick()
        app.session.sync_snapshots()
        capture("traffic-close")
        app.start_game(mode=GameMode.FREE_DRIVE, track="coastal")
        for _ in range(600):
            app.session.tick()
        capture("skin-start")
        app.scene.apply(app.session.current)
        app.panel.hide()

        car = Vec3(*app.session.current.player.position)
        for index in range(len(SKINS)):
            app.skin_index = index
            before = app.session.simulation.snapshot()
            apply_skin(app.scene.player.getChild(0), index)
            assert app.session.simulation.snapshot() == before
            app.camera.setPos(car + Vec3(5, -7, 2))
            app.camera.lookAt(car + Vec3(0, 0, 0.3))
            app.taskMgr.step()
            app.graphicsEngine.renderFrame()
            assert app.win.saveScreenshot(
                Filename.fromOsSpecific(str(output / f"skin-{index}.png"))
            )
        app.messenger.send("f4")
        assert app.skin_index == len(SKINS) - 1
        app.session.menu()
        app.refresh_panel()
        app.buttons[3]["command"]()
        assert app.skin_index == 0
        results["skins_leave_physics_unchanged"] = True
        results["passed"] = True
    finally:
        app.close_game()
    (output / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
