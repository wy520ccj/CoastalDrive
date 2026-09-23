"""记录起跑格和护栏在真实渲染管线中的连续视角。"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panda3d.core import ClockObject, Filename, Vec3
from route_driver import RouteDriver

from application import CoastalDrive
from coastal_map import RAIL_OFFSET, offset_point, point_at
from controls import ConstantController
from simulation import Control, forward


def view(track, subject, distance, travel):
    if subject == "grid":
        y = -4 + travel
        return Vec3(95, y - distance, 4.2), Vec3(95, y + 7, 0.04)
    if track == "coastal":
        p = point_at(25 + travel)
        q = point_at(38 + travel)
        cx, cy, cz = offset_point(p, 2.4, 2.4)
        tx, ty, tz = offset_point(q, RAIL_OFFSET, 0.55)
        return Vec3(cx, cy - distance / 2, cz), Vec3(tx, ty, tz)
    y = 25 + travel
    return Vec3(3.7, y - distance / 2, 2.7), Vec3(8, y + 14, 0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", choices=("coastal", "endless"), required=True)
    parser.add_argument("--subject", choices=("grid", "rail"), required=True)
    parser.add_argument("--speed", type=float, required=True)
    parser.add_argument("--distance", type=int, choices=(11, 16), required=True)
    parser.add_argument("--width", type=int, choices=(1280, 1920), required=True)
    parser.add_argument("--fixed-sun", action="store_true")
    parser.add_argument("--no-shadows", action="store_true")
    parser.add_argument("--drive", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    app = CoastalDrive(smoke=True, output=args.output, track=args.track,
                       road_shape="hills" if args.track == "endless" else "straight",
                       render_size=(args.width, args.width * 9 // 16))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    if args.no_shadows:
        app.scene.sun_path.node().setShadowCaster(False)
    app.clock.setMode(ClockObject.MNonRealTime)
    app.clock.setDt(1 / 15)
    if args.drive:
        sim = app.session.simulation
        if args.subject == "grid":
            position, heading, grade = (95, -3, 0.55), 0, 0
        elif args.track == "coastal":
            p = point_at(25)
            position = offset_point(p, 2.5, 0.55)
            heading, grade = p.heading, p.grade
        else:
            p = sim.road.curve.sample(100, 2.5)
            position = (p.x, p.y, p.z + 0.55)
            heading, grade = p.heading, p.grade
        sim.reset_player(position, heading, grade)
        sim._chassis.setLinearVelocity(Vec3(*forward(heading)) * args.speed)
        app.session.sync_snapshots()
        app.session.camera_distance = args.distance
        app.chase_camera.position = None
        app.session.set_controller(RouteDriver(args.speed * 3.6) if args.track == "coastal" and args.speed
                                   else ConstantController(Control(throttle=0.2 if args.speed else 0)))
    frames = []
    first_eye, _ = view(args.track, args.subject, args.distance, 0)
    if args.fixed_sun:
        app.scene.update_lighting(first_eye)
    task = type("Frame", (), {"cont": None})()
    try:
        for index in range(18):
            app.taskMgr.step()
            if args.drive:
                app.update(task)
                eye = app.camera.getPos()
                target = Vec3(*app.session.current.player.position)
            else:
                app.scene.apply(app.session.current)
                eye, target = view(args.track, args.subject, args.distance,
                                   args.speed * index / 15)
                app.camera.setPos(eye)
                app.camera.lookAt(target)
                if not args.fixed_sun:
                    app.scene.update_lighting(eye)
            app.graphicsEngine.renderFrame()
            path = args.output / f"frame-{index:03d}.jpg"
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
            frames.append({"file": path.name, "eye": list(eye), "target": list(target),
                           "tick": app.session.current.tick,
                           "actual_speed_mps": app.session.current.player.speed})
        (args.output / "frames.json").write_text(json.dumps({
            "track": args.track, "subject": args.subject, "speed_mps": args.speed,
            "camera_distance": args.distance, "resolution": [args.width, args.width * 9 // 16],
            "fixed_sun": args.fixed_sun, "no_shadows": args.no_shadows,
            "drive": args.drive,
            "fps": 15, "frames": frames,
        }, indent=2), encoding="utf-8")
        print(args.output)
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
