"""Exercise real application callbacks and capture the phase 1 UI."""

import json
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from panda3d.core import Filename

    from application import CoastalDrive
    from session import Phase
    from simulation import FIXED_DT

    output = root / "logs/h0-ui"
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=output)
    app.taskMgr.remove("finish-smoke")
    session = app.session
    results = {}

    def capture(name):
        app.taskMgr.step()
        app.update(type("Task", (), {"cont": None})())
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output / f"{name}.png")))

    def key(name):
        app.messenger.send(name)

    try:
        session.menu()
        capture("menu")
        # Use the command bound to the actual menu button.
        app.buttons[0]["command"]()
        assert session.phase == Phase.COUNTDOWN
        capture("countdown")
        for _ in range(360):
            session.tick()
        assert session.phase == Phase.DRIVING
        key("w")
        key("arrow_up")
        key("w-up")
        for _ in range(90):
            session.tick()
        results["keyboard_aliases_drive"] = session.current.player.speed > 0
        capture("driving")
        key("escape")
        frozen = session.current
        key("escape")
        session.frame(10)
        results["pause_edge_and_time"] = session.phase == Phase.PAUSED and session.current == frozen
        capture("paused")
        app.buttons[0]["command"]()
        session.frame(10)
        results["resume_no_wall_time_catchup"] = session.current == frozen
        key("escape-up")
        key("arrow_up-up")
        session.focus_changed(False)
        session.focus_changed(True)
        results["focus_requires_resume"] = (
            session.phase == Phase.PAUSED and not session.keyboard.pressed
        )
        session.resume()
        session.frame(0)
        key("w")
        key("r")
        results["reset_clears_throttle"] = (
            not session.keyboard.pressed and session.current.player.speed == 0
        )
        session.frame(FIXED_DT)
        key("r")
        results["reset_not_repeated"] = session.current.events == ()
        key("r-up")
        key("c")
        distance = session.camera_distance
        key("c")
        results["camera_edge"] = session.camera_distance == distance == 16
        key("c-up")
        session.finish()
        capture("results")
        results["results_state"] = session.phase == Phase.RESULTS
        session.menu()
        capture("menu-returned")
        results["menu_return"] = session.phase == Phase.MENU
        assert all(results.values()), results
    finally:
        app.close_game()
        app.close_game()
    results["close_twice"] = True
    results["passed"] = all(results.values())
    (output / "ui-check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
