"""Check menu paint selection and the camera while driving through all four gates."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from panda3d.core import ClockObject, Filename, Vec3
from route_driver import RouteDriver

from application import CoastalDrive
from race import GameMode
from session import Phase
from skins import SKINS


def main():
    output = Path(__file__).resolve().parents[1] / "logs/h3-feedback"
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=output)
    app.taskMgr.remove("finish-smoke")
    app.clock.setMode(ClockObject.MNonRealTime)
    app.clock.setDt(1 / 60)
    report = {}

    def capture(name):
        app.graphicsEngine.renderFrame()
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output / f"{name}.png")))

    try:
        app.session.menu()
        app.taskMgr.step()
        before = app.session.simulation.snapshot()
        for index in range(1, len(SKINS) + 1):
            app.buttons[3]["command"]()
            assert app.skin_index == index % len(SKINS)
            assert SKINS[app.skin_index].name in app.buttons[3]["text"]
            assert app.session.simulation.snapshot() == before
        app.buttons[3]["command"]()
        app.taskMgr.step()
        capture("menu-paint")
        selected = app.skin_index
        app.messenger.send("f4")
        assert app.skin_index == selected
        report["menu_paint_and_no_f4"] = True
        app.start_game(mode=GameMode.TIME_TRIAL)
        app.session.set_controller(RouteDriver())
        assert app.skin_index == selected
        previous = None
        changes = []
        gates = 0
        for _ in range(4500):
            app.taskMgr.step()
            if app.session.phase == Phase.DRIVING:
                position = Vec3(app.camera.getPos())
                if previous is not None:
                    changes.append((position - previous).length())
                previous = position
            passed = app.session.race.snapshot.checkpoints
            if passed > gates:
                gates = passed
                capture(f"gate-{gates}")
            if app.session.phase == Phase.RESULTS:
                break
        race = app.session.race.snapshot
        assert gates == 4 and race.finished and not race.invalidated
        assert max(changes) < 0.8
        report["four_gates_valid_lap"] = race.last_lap
        report["largest_camera_step_metres_at_60fps"] = max(changes)
        report["paint_kept_after_start"] = app.skin_index == selected
        report["passed"] = True
    finally:
        app.close_game()
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
