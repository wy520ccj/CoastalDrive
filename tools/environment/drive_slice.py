"""通过既有规则控制器实际驶过示范段，记录窗口截图和短程帧耗时。"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from panda3d.core import Filename, SceneGraphAnalyzer
from route_driver import RouteDriver

from application import CoastalDrive
from coastal_map import map_length, project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--onscreen", action="store_true")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--benchmark", action="store_true", help="预热30秒后独立采样300秒，不截屏")
    args = parser.parse_args()
    warmup_seconds = 30
    sample_seconds = 300
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    app = CoastalDrive(
        smoke=True, onscreen=args.onscreen, output=args.output, seed=23, render_size=(1920, 1080)
    )
    app.taskMgr.remove("finish-smoke")
    app.session.set_controller(RouteDriver(70))
    update_samples = []
    original_update = app.update

    def measured_update(task):
        start = time.perf_counter()
        result = original_update(task)
        if task.time > warmup_seconds:
            update_samples.append(time.perf_counter() - start)
        return result

    if args.benchmark:
        app.taskMgr.remove("drive-update")
        app.taskMgr.add(measured_update, "drive-update")
    durations, captures = [], []
    images = []
    previous_time = time.perf_counter()
    previous_progress = project(*app.session.current.player.position[:2])[2]
    total = 0.0
    passed = False
    sample_dropped_start = None
    sample_buckets = []
    bucket_start_index = 0
    bucket_drop_start = None
    focus_samples = []
    last_focus_second = -1
    targets = (0, 70, 140, 225, 315)

    def observe(task):
        nonlocal previous_time, previous_progress, total, passed, sample_dropped_start
        nonlocal last_focus_second, bucket_start_index, bucket_drop_start
        now = time.perf_counter()
        second = int(task.time)
        if args.benchmark and args.onscreen and second != last_focus_second:
            properties = app.win.getProperties()
            focus_samples.append({"second": second, "foreground": properties.getForeground(),
                                  "minimized": properties.getMinimized()})
            last_focus_second = second
        if task.time > (warmup_seconds if args.benchmark else 2):
            if sample_dropped_start is None:
                sample_dropped_start = app.session.stepper.dropped_time
                bucket_drop_start = sample_dropped_start
            else:
                durations.append(now - previous_time)
        if args.benchmark and sample_dropped_start is not None:
            next_end = min((len(sample_buckets) + 1) * 30, sample_seconds)
            if (len(sample_buckets) * 30 < sample_seconds
                    and task.time >= warmup_seconds + next_end):
                window = durations[bucket_start_index:]
                ordered_window = sorted(window)
                sample_buckets.append({
                    "sample_start_s": len(sample_buckets) * 30,
                    "sample_end_s": next_end,
                    "average_fps": len(window) / sum(window) if window else None,
                    "p95_frame_ms": ordered_window[int(len(window) * 0.95)] * 1000
                    if window else None,
                    "dropped_simulation_s": app.session.stepper.dropped_time - bucket_drop_start,
                })
                bucket_start_index = len(durations)
                bucket_drop_start = app.session.stepper.dropped_time
        previous_time = now
        state = app.session.current
        progress = project(*state.player.position[:2])[2]
        total += (progress - previous_progress + map_length() / 2) % map_length() - map_length() / 2
        previous_progress = progress
        if not args.benchmark and len(captures) < len(targets) and total >= targets[len(captures)]:
            path = args.output / f"drive-{targets[len(captures)]:03d}.png"
            # 先保存显存快照；PNG 压缩和磁盘写入放到驾驶结束后。
            images.append((path, app.win.getScreenshot()))
            captures.append(
                {
                    "screenshot": path.name,
                    "time": state.time,
                    "distance_m": total,
                    "position": state.player.position,
                }
            )
        finished = (task.time >= warmup_seconds + sample_seconds
                    if args.benchmark else total >= 365 or task.time >= args.seconds)
        if finished:
            # 场景首次 update 后才有八辆交通车；在采样结束时统计实际运行图。
            graph = SceneGraphAnalyzer()
            graph.addNode(app.render.node())
            geometry = {
                "nodes": graph.getNumNodes(),
                "geom_nodes": graph.getNumGeomNodes(),
                "geoms": graph.getNumGeoms(),
                "triangles": graph.getNumTris(),
            }
            ordered = sorted(durations)
            passed = total >= 365 and len(state.traffic) == 8 and bool(durations)
            sample_focus = [item for item in focus_samples
                            if item["second"] >= warmup_seconds]
            window_sampling_valid = (
                not any(item["minimized"] for item in sample_focus)
                    if args.benchmark and args.onscreen else None
            )
            report = {
                "passed": passed,
                "onscreen": args.onscreen,
                "resolution": [1920, 1080],
                "note": (
                    "30s warmup + 300s capture-free automated driving; not human acceptance."
                    if args.benchmark
                    else "Short automated route sample; not a long-run gate."
                ),
                "renderer": app.win.getGsg().getDriverRenderer(),
                "seed": 23,
                "traffic_count": len(state.traffic),
                "update_timer_enabled": args.benchmark,
                "distance_m": total,
                "simulation_seconds": state.time,
                "wall_seconds": task.time,
                "average_fps": len(durations) / sum(durations) if durations else None,
                "p95_frame_ms": ordered[int(len(ordered) * 0.95)] * 1000 if ordered else None,
                "p99_frame_ms": ordered[int(len(ordered) * 0.99)] * 1000 if ordered else None,
                "dropped_simulation_seconds": app.session.stepper.dropped_time,
                "sample_dropped_seconds": app.session.stepper.dropped_time
                - (sample_dropped_start or 0),
                "sample_frames": len(durations),
                "sample_seconds": sum(durations),
                "sample_30s_buckets": sample_buckets if args.benchmark else [],
                "scene_graph_totals": geometry,
                "geometry_capture_phase": "end of sample, after scene synchronization",
                "geometry_note": "Whole scene counts; not visible triangles or GPU draw calls.",
                "window_focus_samples": focus_samples if args.benchmark else [],
                "onscreen_sampling_valid": window_sampling_valid,
                "window_foreground_fraction": (
                    sum(item["foreground"] for item in focus_samples) / len(focus_samples)
                    if focus_samples else None
                ),
                "update_cpu_mean_ms": sum(update_samples) / len(update_samples) * 1000
                if update_samples
                else None,
                "update_cpu_p95_ms": sorted(update_samples)[int(len(update_samples) * 0.95)] * 1000
                if update_samples
                else None,
                "gpu_timing": "not measured",
                "captures": captures,
            }
            if args.benchmark:
                report["performance_gate_passed"] = (
                    passed and report["average_fps"] >= 60 and report["p95_frame_ms"] <= 25
                    if window_sampling_valid is not False else None
                )
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
