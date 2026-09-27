"""通过既有规则控制器实际驶过示范段，记录窗口截图和短程帧耗时。"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from panda3d.core import Filename
from route_driver import RouteDriver

from application import CoastalDrive
from coastal_map import map_length, project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--onscreen", action="store_true")
    parser.add_argument("--seconds", type=float, default=60)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    app = CoastalDrive(smoke=True, onscreen=args.onscreen, output=args.output,
                       seed=23, render_size=(1920, 1080))
    app.taskMgr.remove("finish-smoke")
    app.session.set_controller(RouteDriver(70))
    durations, captures = [], []
    images = []
    previous_time = time.perf_counter()
    previous_progress = project(*app.session.current.player.position[:2])[2]
    total = 0.0
    passed = False
    targets = (0, 70, 140, 225, 315)

    def observe(task):
        nonlocal previous_time, previous_progress, total, passed
        now = time.perf_counter()
        if task.time > 2:
            durations.append(now - previous_time)
        previous_time = now
        state = app.session.current
        progress = project(*state.player.position[:2])[2]
        total += (progress - previous_progress + map_length() / 2) % map_length() - map_length() / 2
        previous_progress = progress
        if len(captures) < len(targets) and total >= targets[len(captures)]:
            path = args.output / f"drive-{targets[len(captures)]:03d}.png"
            # 先保存显存快照；PNG 压缩和磁盘写入放到驾驶结束后。
            images.append((path, app.win.getScreenshot()))
            captures.append({"screenshot": path.name, "time": state.time,
                             "distance_m": total, "position": state.player.position})
        if total >= 365 or task.time >= args.seconds:
            ordered = sorted(durations)
            passed = total >= 365 and len(state.traffic) == 8 and bool(durations)
            report = {
                "passed": passed, "onscreen": args.onscreen, "resolution": [1920, 1080],
                "note": "Short automated route sample; not human acceptance or a long-run gate.",
                "renderer": app.win.getGsg().getDriverRenderer(), "seed": 23,
                "traffic_count": len(state.traffic), "distance_m": total,
                "simulation_seconds": state.time, "wall_seconds": task.time,
                "average_fps": len(durations) / sum(durations) if durations else None,
                "p95_frame_ms": ordered[int(len(ordered) * 0.95)] * 1000 if ordered else None,
                "p99_frame_ms": ordered[int(len(ordered) * 0.99)] * 1000 if ordered else None,
                "dropped_simulation_seconds": app.session.stepper.dropped_time,
                "captures": captures,
            }
            (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            app.userExit()
            return task.done
        return task.cont

    app.taskMgr.add(observe, "environment-route-observer", sort=55)
    try:
        app.run()
    finally:
        for path, texture in images:
            assert texture.write(Filename.fromOsSpecific(str(path)))
        app.close_game()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
