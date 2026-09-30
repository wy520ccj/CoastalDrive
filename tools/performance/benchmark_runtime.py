"""固定路线窗口短测，记录尾延迟、窗口状态和测量期间丢时。"""

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from itertools import pairwise
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shape", choices=("straight", "curves", "hills"), default="hills")
    parser.add_argument("--seconds", type=float, default=45)
    parser.add_argument("--baseline-compute", action="store_true")
    parser.add_argument("--pipeline", choices=("single", "draw", "cull-draw"), default="draw")
    parser.add_argument("--trace-streaming", action="store_true")
    args = parser.parse_args()
    if not 30 <= args.seconds <= 60:
        parser.error("短测限于30–60秒")
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    streaming_phases = {}
    tracing = False
    if args.trace_streaming:
        from environment import expressway_route

        original_steps = expressway_route.segment_steps

        def traced_steps(*a, **kw):
            steps = original_steps(*a, **kw)
            try:
                while True:
                    started = time.perf_counter()
                    try:
                        phase = next(steps)
                    except StopIteration:
                        return
                    elapsed = (time.perf_counter()-started)*1000
                    if tracing:
                        values = streaming_phases.setdefault(phase, {"count": 0, "total_ms": 0, "max_ms": 0})
                        values["count"] += 1
                        values["total_ms"] += elapsed
                        values["max_ms"] = max(values["max_ms"], elapsed)
                    yield phase
            finally:
                steps.close()

        expressway_route.segment_steps = traced_steps
    if args.baseline_compute:
        for name in ("highway_curve", "vehicle", "simulation", "ui.hud", "application"):
            source = subprocess.check_output(
                ["git", "show", f"f9431dd:src/{name.replace('.', '/')}.py"],
                cwd=ROOT, text=True, encoding="utf-8",
            )
            module = ModuleType(name)
            sys.modules[name] = module
            exec(compile(source, name, "exec"), module.__dict__)  # noqa: S102
        # 保留PERF-02已交接的精确采样缓存，只隔离本轮计算修改。
        from functools import lru_cache

        curve_type = sys.modules["highway_curve"].HighwayCurve
        original_init = curve_type.__init__

        def cached_init(self, *a, **kw):
            original_init(self, *a, **kw)
            self.sample = lru_cache(maxsize=8192)(self.sample)

        curve_type.__init__ = cached_init
    from endurance_check import EnduranceDriver
    from panda3d.core import CallbackObject, Filename, loadPrcFileData

    from application import CoastalDrive

    pipelines = {"single": "", "draw": "/Draw", "cull-draw": "Cull/Draw"}
    loadPrcFileData("performance-pipeline", "threading-model " + pipelines[args.pipeline])
    app = CoastalDrive(smoke=True, onscreen=True, track="endless", road_shape=args.shape,
                       seed=23, output=args.output, render_size=(1920, 1080),
                       threading_model=pipelines[args.pipeline])
    app.taskMgr.remove("finish-smoke")
    app.session.set_controller(EnduranceDriver(app.session.simulation, 724))
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    handle = app.win.getWindowHandle().getIntHandle()
    user32.ShowWindow(handle, 9)
    user32.SetForegroundWindow(handle)
    samples, windows = [], []
    work_samples = []
    previous = time.perf_counter()
    last_second = -1
    start_dropped = None
    final = {}
    draw_times = []
    measuring_draw = False

    def count_draw(data):
        if measuring_draw:
            draw_times.append(time.perf_counter())
        data.upcall()

    # 末个活动显示区每个实际窗口绘制调用一次；避免把主线程超前更新当作显示FPS。
    region = max((r for r in app.win.getDisplayRegions() if r.isActive()),
                 key=lambda r: r.getSort())
    region.setDrawCallback(CallbackObject.make(count_draw))

    def observe(task):
        nonlocal previous, last_second, start_dropped, measuring_draw, tracing
        now = time.perf_counter()
        if task.time >= 3:
            if start_dropped is None:
                start_dropped = app.session.stepper.dropped_time
                app.scene.segment_work["max_step_ms"] = 0
                measuring_draw = True
                tracing = True
            samples.append({"second": task.time, "ms": (now - previous) * 1000})
            work_samples.append(dict(app.scene.segment_work))
        previous = now
        if int(task.time) != last_second:
            props = app.win.getProperties()
            windows.append({"second": int(task.time), "minimized": props.getMinimized(),
                            "foreground": props.getForeground()})
            last_second = int(task.time)
        if task.time >= args.seconds:
            measuring_draw = False
            tracing = False
            values = sorted(row["ms"] for row in samples)
            draw_values = sorted((b - a) * 1000 for a, b in pairwise(draw_times))
            valid = all(not w["minimized"] and w["foreground"] for w in windows)
            state = app.session.current
            distance = app.session.simulation.road.locate(state.player)[0] - 8
            final.update({
                "kind": "45-second comparison; not final performance or human gate",
                "shape": args.shape, "seed": 23, "resolution": [1920, 1080],
                "traffic_count": len(state.traffic), "pipeline": args.pipeline,
                "baseline_compute": args.baseline_compute, "window_sampling_valid": valid,
                "renderer": app.win.getGsg().getDriverRenderer(),
                "streaming_phases": streaming_phases,
                "wall_seconds": task.time, "sample_seconds": sum(values) / 1000,
                "frames": len(values), "average_fps": len(values) * 1000 / sum(values),
                "display_draw_frames": len(draw_values),
                "display_draw_fps": len(draw_values) * 1000 / sum(draw_values),
                "display_draw_p95_ms": draw_values[int(len(draw_values) * .95)],
                "display_draw_p99_ms": draw_values[int(len(draw_values) * .99)],
                "display_draw_max_ms": max(draw_values),
                "display_draw_over_50ms": sum(v > 50 for v in draw_values),
                "p95_ms": values[int(len(values) * .95)],
                "p99_ms": values[int(len(values) * .99)], "max_ms": max(values),
                "frames_over_50ms": sum(v > 50 for v in values),
                "frames_over_100ms": sum(v > 100 for v in values),
                "dropped_simulation_seconds": app.session.stepper.dropped_time - start_dropped,
                "warmup_dropped_seconds": start_dropped, "distance_m": distance,
                "collisions": app.session.simulation.collision_count,
                "frames_slow": sorted(samples, key=lambda row: row["ms"], reverse=True)[:12],
                "segment_work_max_ms": max(w["frame_ms"] for w in work_samples),
                "segment_step_max_ms": max(w["max_step_ms"] for w in work_samples),
                "near_pending_frames": sum(w["near_pending"] > 0 for w in work_samples),
                "segment_work_slow": sorted(work_samples, key=lambda w: w["frame_ms"],
                                            reverse=True)[:12],
                "windows": windows,
                "passed": valid and distance > 600 and not app.session.simulation.collision_count,
            })
            final["short_performance_passed"] = (
                final["passed"] and final["display_draw_fps"] >= 60
                and final["display_draw_p95_ms"] <= 25
                and final["display_draw_over_50ms"] == 0
                and final["dropped_simulation_seconds"] == 0
                and final["near_pending_frames"] == 0
            )
            app.userExit()
            return task.done
        return task.cont

    app.taskMgr.add(observe, "performance-observe", sort=55)
    try:
        app.run()
        app.graphicsEngine.syncFrame()
        app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output / "final.png")))
    finally:
        app.close_game()
    final["git_head"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
    ).strip()
    final["git_status"] = subprocess.check_output(
        ["git", "status", "--short"], cwd=ROOT, text=True, encoding="utf-8",
    ).strip()
    (args.output / "report.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in final.items()
                      if k not in ("windows", "frames_slow", "git_status", "segment_work_slow")},
                     indent=2))
    return 0 if final["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
