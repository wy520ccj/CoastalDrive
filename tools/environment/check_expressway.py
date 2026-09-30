"""HWY-01固定视点、短程真实驾驶和人工试玩入口；不提供长测选项。"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from endurance_check import EnduranceDriver
from panda3d.core import Filename, SceneGraphAnalyzer, Vec3

from application import CoastalDrive
from race import GameMode


def capture(app, output):
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    app.scene.apply(app.session.current)
    views = []
    for s in (8, 170, 285, 390, 510, 665, 790, 830):
        app.camera.setPos(0, s, 3.4)
        app.camera.lookAt(Vec3(0, s + 45, 1.9))
        app.scene.sky.setPos(app.camera.getPos())
        app.scene.update_lighting(app.camera.getPos())
        app.taskMgr.step()
        for _ in range(8):
            app.graphicsEngine.renderFrame()
        path = output / f"highway-{s:03d}.png"
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        views.append({"distance_m": s, "file": path.name, "camera_height_m": 3.4})
    app.camera.setPos(-1.5, 510, 3.6)
    app.camera.lookAt(Vec3(75, 540, -1.8))
    app.scene.sky.setPos(app.camera.getPos())
    app.scene.update_lighting(app.camera.getPos())
    app.taskMgr.step()
    for _ in range(8):
        app.graphicsEngine.renderFrame()
    assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output / "bay-side.png")))
    views.append({"distance_m": 510, "file": "bay-side.png", "camera_height_m": 3.6})
    (output / "views.json").write_text(json.dumps({"kind": "static renderer views; not driving",
                                                  "views": views}, indent=2), encoding="utf-8")


def capture_route(app, output):
    """静态取景使用实际分段装卸；不计为驾驶或重定位验证。"""
    from environment.expressway_route import sample

    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    sim = app.session.simulation
    curve = sim.road.curve
    views = []
    for distance in (8, 170, 790, 1680, 2150, 3400, 8400):
        center = sample(curve, distance)
        sim.origin_y = center.y
        sim.stream.update(distance, sim.origin_y, [])
        app.scene.sync_segments()
        origin = Vec3(0, sim.origin_y, 0)
        position = center - origin + Vec3(0, 0, 3.4)
        app.camera.setPos(position)
        app.camera.lookAt(sample(curve, distance + 45) - origin + Vec3(0, 0, 1.9))
        app.scene.sky.setPos(position)
        app.scene.update_lighting(position)
        app.taskMgr.step()
        for _ in range(8):
            app.graphicsEngine.renderFrame()
        path = output / f"route-{distance}.png"
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        views.append({"distance_m": distance, "file": path.name})
    (output / "views.json").write_text(json.dumps({"kind": "static renderer; not driving", "views": views}, indent=2), encoding="utf-8")


def drive(app, output, seconds, onscreen):
    app.session.set_controller(EnduranceDriver(app.session.simulation, 724))
    durations, captures, focus = [], [], []
    previous = time.perf_counter()
    targets = (70, 260, 430, 620, 780)
    last_second = -1
    report = {}

    def observe(task):
        nonlocal previous, last_second
        now = time.perf_counter()
        if task.time > 3:
            durations.append(now - previous)
        previous = now
        state = app.session.current
        s = app.session.simulation.road.locate(state.player)[0]
        if len(captures) < len(targets) and s >= targets[len(captures)]:
            captures.append((s, app.win.getScreenshot()))
        if onscreen and int(task.time) != last_second:
            props = app.win.getProperties()
            focus.append({"second": int(task.time), "minimized": props.getMinimized(),
                          "foreground": props.getForeground()})
            last_second = int(task.time)
        if task.time >= seconds:
            graph = SceneGraphAnalyzer()
            graph.addNode(app.scene.render.node())
            valid = not any(item["minimized"] for item in focus) if onscreen else None
            report.update({
                "kind": "short sanity; not Performance Gate or human acceptance",
                "seed": 23, "shape": "hills" if app.session.simulation.road.curve and app.session.simulation.road.curve.height else "curves" if app.session.simulation.road.curve else "straight", "resolution": [1920, 1080],
                "onscreen": onscreen, "window_sampling_valid": valid,
                "wall_seconds": task.time, "distance_m": s - 8,
                "simulation_seconds": state.time, "traffic_count": len(state.traffic),
                "average_fps": len(durations) / sum(durations),
                "max_ms": max(durations)*1000,
                "frames_over_50ms": sum(t>.05 for t in durations),
                "frames_over_100ms": sum(t>.1 for t in durations),
                "p95_ms": sorted(durations)[int(len(durations) * 0.95)] * 1000,
                "sample_seconds": sum(durations), "frames": len(durations),
                "collisions": app.session.simulation.collision_count,
                "dropped_simulation_seconds": app.session.stepper.dropped_time,
                "nodes": graph.getNumNodes(), "geoms": graph.getNumGeoms(),
                "triangles": graph.getNumTris(), "window": focus,
                "passed": s >= 800 and bool(durations) and valid is not False
                          and len(durations) / sum(durations) >= 25,
            })
            app.userExit()
            return task.done
        return task.cont

    app.taskMgr.add(observe, "expressway-sanity", sort=55)
    app.run()
    for s, texture in captures:
        assert texture.write(Filename.fromOsSpecific(str(output / f"drive-{int(s):03d}.png")))
    (output / "sanity.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "window"}, indent=2))
    return report["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shape", choices=("straight", "curves", "hills"), default="straight")
    parser.add_argument("--route", action="store_true")
    parser.add_argument("--drive", action="store_true")
    parser.add_argument("--onscreen", action="store_true")
    parser.add_argument("--play", action="store_true")
    parser.add_argument("--seconds", type=float, default=55)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 60:
        parser.error("HWY-01 sanity限于30–60秒")
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    app = CoastalDrive(smoke=not args.play, onscreen=args.onscreen or args.play,
                       track="endless", road_shape=args.shape, seed=23, output=args.output,
                       render_size=(1920, 1080))
    app.taskMgr.remove("finish-smoke")
    try:
        if args.play:
            app.start_highway(args.shape, mode=GameMode.FREE_DRIVE)
            app.run()
        elif args.drive:
            return 0 if drive(app, args.output, args.seconds, args.onscreen) else 1
        else:
            if args.route:
                capture_route(app, args.output)
            else:
                capture(app, args.output)
    finally:
        app.close_game()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
