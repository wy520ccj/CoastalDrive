"""Check held-key and raw-key paths in the real application; render evidence offscreen."""

import json
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from panda3d.core import Filename

    from application import CoastalDrive
    from session import Phase
    from test_track import TEST_SPAWN

    app = CoastalDrive(smoke=True, track="test")
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    session = app.session
    output = root / "logs/h1-ui-review"
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    task = type("Frame", (), {"cont": None})()

    def update():
        app.update(task)

    def capture(name):
        app.taskMgr.step()
        update()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output / f"{name}.png")))

    def key(name):
        app.messenger.send(name)

    try:
        session.menu()
        capture("menu")
        key("enter")
        key("enter-up")
        results["enter_starts_countdown"] = session.phase == Phase.COUNTDOWN
        key("w")
        for _ in range(360):
            session.tick()
        update()
        for _ in range(360):
            session.tick()
        results["holding_throttle_through_countdown"] = session.current.player.speed > 8
        key("w-up")
        update()
        results["release_clears_throttle"] = not session.keyboard.pressed
        key("r")
        key("r-up")
        for _ in range(1800):
            session.tick()
        # Input is checked on the straight test strip so a map barrier does not
        # hide a successful key-to-steering path.
        session.simulation.reset_player(TEST_SPAWN)
        session.sync_snapshots()
        key("raw-w")
        key("raw-d")
        update()
        for _ in range(360):
            session.tick()
        car = session.current.player
        results["raw_keys_start_and_turn_after_15s_idle"] = car.speed > 3 and car.heading < -30
        capture("turning")
        key("raw-w-up")
        key("raw-d-up")
        key("escape")
        key("escape-up")
        capture("paused")
        results["pause_clears_held_input"] = not app.driving_keys_held
        key("enter")
        key("enter-up")
        update()
        results["enter_resumes_without_stuck_throttle"] = (
            session.phase == Phase.DRIVING and not session.keyboard.pressed
        )
        key("r")
        key("r-up")
        key("arrow_up")
        update()
        for _ in range(360):
            session.tick()
        results["arrow_key_drives"] = session.current.player.speed > 8
        key("arrow_up-up")
        capture("driving")
        results["wheel_meshes_use_snapshot_poses"] = all(
            (node.getPos() - wheel.position).length() < 0.1
            for node, wheel in zip(app.scene.wheels, session.current.player.wheels)
        )
        results["passed"] = all(results.values())
    finally:
        app.close_game()
    (output / "ui-check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
