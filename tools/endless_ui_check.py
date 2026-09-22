"""Render streamed segments and the frames immediately around an origin shift."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import itertools

from panda3d.core import ClockObject, Filename, Vec3

from application import CoastalDrive
from controls import ConstantController
from race import GameMode
from simulation import Control


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("logs/h4b/ui"))
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=output, track="endless")
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.clock.setMode(ClockObject.MNonRealTime)
    app.clock.setDt(1 / 60)
    frame = type("Frame", (), {"cont": None})()
    records = []
    try:
        app.session.start(mode=GameMode.FREE_DRIVE, track="endless", countdown=False)
        app.session.simulation.reset_player((0, 1995, 0.55))
        app.session.simulation._update_stream()
        app.session.simulation._chassis.setLinearVelocity(Vec3(0, 25, 0))
        app.session.sync_snapshots()
        app.session.set_controller(ConstantController(Control(throttle=0.3)))
        app.chase_camera.position = None
        for index in range(240):
            app.taskMgr.step()
            app.update(frame)
            app.graphicsEngine.renderFrame()
            state = app.session.current
            position = app.camera.getPos()
            records.append(
                {
                    "frame": index,
                    "origin": state.origin_y,
                    "car_y": state.origin_y + state.player.position[1],
                    "camera_y": state.origin_y + position.y,
                    "segments": len(app.scene.segment_nodes),
                }
            )
            if index in (1, 10, 20, 60, 239):
                app.win.saveScreenshot(Filename.fromOsSpecific(str(output / f"frame-{index}.png")))
        assert app.session.simulation.rebases == 1
        assert max(abs(b["camera_y"] - a["camera_y"]) for a, b in itertools.pairwise(records)) < 1
        assert set(app.scene.segment_nodes) == set(app.session.simulation.stream.segments)
        assert all(
            root.findAllMatches("**/+GeomNode").getNumPaths()
            for root in app.scene.segment_nodes.values()
        )
        app.session.menu()
        app.update(frame)
        app.graphicsEngine.renderFrame()
        app.win.saveScreenshot(Filename.fromOsSpecific(str(output / "menu.png")))
        (output / "report.json").write_text(
            json.dumps({"passed": True, "frames": records}, indent=2)
        )
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
