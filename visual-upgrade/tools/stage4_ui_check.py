"""Check the stage 4 menu actions and map switch with a real Panda3D context."""

import json
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from panda3d.core import Filename

    from application import CoastalDrive
    from race import GameMode
    from session import Phase

    output = root / "logs/stage4-ui-review"
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, track="coastal")
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    task = type("Frame", (), {"cont": None})()
    results = {}

    def update():
        app.taskMgr.step()
        app.update(task)
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()

    try:
        app.session.menu()
        update()
        results["menu_has_four_choices"] = sum(not button.isHidden() for button in app.buttons) == 4
        app.buttons[0]["command"]()
        results["time_trial_button_starts_countdown"] = (
            app.session.phase == Phase.COUNTDOWN
            and app.session.mode == GameMode.TIME_TRIAL
            and app.session.simulation.track == "coastal"
        )
        app.session.menu()
        update()
        app.buttons[2]["command"]()
        update()
        results["highway_button_switches_map"] = (
            app.session.phase == Phase.COUNTDOWN
            and app.session.mode == GameMode.FREE_DRIVE
            and app.session.simulation.track == "highway"
            and len(app.session.current.traffic) == 8
        )
        captured = app.win.saveScreenshot(Filename.fromOsSpecific(str(output / "highway-menu-switch.png")))
        results["screenshot"] = captured
        results["passed"] = all(results.values())
    finally:
        app.close_game()
    (output / "ui-check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
