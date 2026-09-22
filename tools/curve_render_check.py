"""Render genuine physics frames on bends, crests and across an origin shift."""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from endurance_check import EnduranceDriver
from panda3d.core import ClockObject, Filename, Vec3

from application import CoastalDrive


def main():
    output = Path("logs/h4b/curves/ui")
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=output, track="endless", road_shape="hills")
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.clock.setMode(ClockObject.MNonRealTime)
    app.clock.setDt(1 / 60)
    task = type("Frame", (), {"cont": None})()
    traces = []
    try:
        for start in (200, 520, 1990):
            app.session.start(countdown=False)
            sim = app.session.simulation
            p = sim.road.sample(start, 1)
            sim.reset_player((p.x, p.y, p.z + 0.55), p.heading, p.grade)
            sim._update_stream()
            h, grade = math.radians(p.heading), math.radians(p.grade)
            sim.player._chassis.setLinearVelocity(Vec3(-math.sin(h) * math.cos(grade), math.cos(h) * math.cos(grade), math.sin(grade)) * 25)
            app.session.sync_snapshots()
            app.session.set_controller(EnduranceDriver(sim, 701))
            app.chase_camera.position = None
            app._camera_origin = 0
            previous_camera = None
            for frame in range(180):
                app.taskMgr.step()
                app.update(task)
                app.graphicsEngine.renderFrame()
                state = app.session.current
                camera = app.camera.getPos() + Vec3(0, state.origin_y, 0)
                if previous_camera is not None:
                    assert (camera - previous_camera).length() < 2
                previous_camera = camera
                assert set(app.scene.segment_nodes) == set(sim.stream.segments)
                if frame in (30, 90, 179):
                    app.win.saveScreenshot(Filename.fromOsSpecific(str(output / f"road-{start}-{frame}.png")))
                traces.append({"start": start, "frame": frame, "origin": state.origin_y,
                               "position": state.player.position, "road": sim.road.locate(state.player),
                               "camera": tuple(camera)})
            if start == 1990:
                assert sim.rebases == 1
        app.session.menu()
        app.choose_highway()
        assert app.highway_menu
        app.start_highway("straight")
        assert app.session.simulation.road.curve is None
        assert app._scene_shape == "straight"
        app.session.menu()
        app.choose_highway()
        app.start_highway("hills")
        assert app.session.simulation.road.curve is not None
        assert app._scene_shape == "hills"
        app.taskMgr.step()
        app.update(task)
        app.graphicsEngine.renderFrame()
        (output / "report.json").write_text(json.dumps({"passed": True, "frames": traces}, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
