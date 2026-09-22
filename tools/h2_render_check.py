"""Render a full lap through the application and save frame timing and representative views."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panda3d.core import Filename
from route_driver import RouteDriver

from application import CoastalDrive
from coastal_map import map_length, project


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parents[1] / "logs/h2-review/render"
    )
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=output)
    app.taskMgr.remove("finish-smoke")
    app.session.set_controller(RouteDriver(90))
    durations = []
    previous_time = time.perf_counter()
    previous_progress = total = 0.0
    captures = []
    names = ["start", "north-climb", "west-s-bend", "sea-bend", "finish"]

    def observe(task):
        nonlocal previous_time, previous_progress, total
        now = time.perf_counter()
        if task.time > 2:
            durations.append(now - previous_time)
        previous_time = now
        state = app.session.current
        _, _, progress = project(*state.player.position[:2])
        total += (progress - previous_progress + map_length() / 2) % map_length() - map_length() / 2
        previous_progress = progress
        if len(captures) < len(names) and total >= len(captures) * map_length() / 4:
            name = names[len(captures)]
            path = output / f"{name}.png"
            app.graphicsEngine.renderFrame()
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
            captures.append(name)
        if total >= map_length() or task.time > 90:
            ordered = sorted(durations)
            report = {
                "mode": "real-time offscreen application, 1280x720, shadows and MSAA4",
                "renderer": app.win.getGsg().getDriverRenderer(),
                "ordered_laps": total / map_length(),
                "simulation_seconds": state.time,
                "wall_seconds": task.time,
                "average_fps": len(durations) / sum(durations),
                "p95_frame_ms": ordered[int(len(ordered) * 0.95)] * 1000,
                "p99_frame_ms": ordered[int(len(ordered) * 0.99)] * 1000,
                "dropped_simulation_seconds": app.session.stepper.dropped_time,
                "captures": captures,
            }
            report["passed"] = total >= map_length() and report["average_fps"] >= 60
            (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            app.smoke_passed = report["passed"]
            app.userExit()
            return task.done
        return task.cont

    app.taskMgr.add(observe, "h2-observe", sort=55)
    try:
        app.run()
        return 0 if app.smoke_passed else 1
    finally:
        app.close_game()


if __name__ == "__main__":
    raise SystemExit(main())
