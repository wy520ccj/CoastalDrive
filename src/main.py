"""Source and packaged entry point; headless runs never import the renderer."""

import argparse
import json
import logging
import os
import traceback
from dataclasses import asdict
from pathlib import Path

from paths import user_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--steps", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--road-shape", choices=("straight", "curves", "hills"), default="straight")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--window-smoke", action="store_true")
    parser.add_argument("--profile-startup", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--track", choices=("coastal", "highway", "endless", "test"), default="coastal"
    )
    args = parser.parse_args()
    if args.steps <= 0:
        parser.error("--steps must be positive")
    if args.profile_startup and (args.headless or args.smoke or args.window_smoke):
        parser.error("--profile-startup requires a visible menu run")
    if args.headless:
        from controls import ConstantController
        from simulation import FIXED_DT, Control, Simulation

        simulation = Simulation(args.seed, track=args.track, road_shape=args.road_shape)
        controller = ConstantController(Control(throttle=0.5))
        try:
            for _ in range(args.steps):
                simulation.step(controller.sample(simulation.snapshot(), FIXED_DT))
            print(json.dumps(asdict(simulation.snapshot()), indent=2))
        finally:
            simulation.close()
        return 0
    startup = None
    if args.profile_startup:
        from performance_baseline import StartupTrace

        origin = os.environ.get("COASTALDRIVE_STARTUP_ORIGIN_NS")
        startup = StartupTrace(int(origin) if origin is not None else None)
        startup.mark("entrypoint_ready")
    logging.basicConfig(filename=user_data() / "runtime.log", level=logging.INFO, encoding="utf-8")
    from application import CoastalDrive

    if startup is not None:
        startup.mark("application_imported")
        app = CoastalDrive(onscreen=True, output=args.output, seed=args.seed, track=args.track,
                           road_shape=args.road_shape, startup_trace=startup)
        try:
            app.taskMgr.step()
            startup.mark("first_rendered_frame")
            if app.main_menu.root.isHidden() or app.panel_option_count != 0:
                raise RuntimeError("主菜单首帧未准备好")
            startup.mark("main_menu_usable")
            report = startup.finish()
            report["scenario"] = "visible coastal main menu, then 8-car free drive"
            report["startup_traffic_count"] = len(app.scene.traffic)
            report["resolution"] = [app.win.getXSize(), app.win.getYSize()]
            report["renderer"] = app.win.getGsg().getDriverRenderer()
            from panda3d.core import Filename

            args.profile_startup.parent.mkdir(parents=True, exist_ok=True)
            screenshot = args.profile_startup.with_suffix(".png")
            if not app.win.getScreenshot().write(Filename.fromOsSpecific(str(screenshot))):
                raise RuntimeError("启动首帧截图未保存")
            report["first_frame_capture"] = screenshot.name
            from race import GameMode

            drive_trace = StartupTrace()
            app.startup_trace = drive_trace
            drive_trace.mark("drive_transition_started")
            app.start_game(mode=GameMode.FREE_DRIVE, track="coastal")
            app.taskMgr.step()
            drive_trace.mark("first_drive_frame")
            report["drive_transition"] = drive_trace.finish()
            report["drive_traffic_count"] = len(app.scene.traffic)
            report["drive_transition_s"] = round(
                (drive_trace.events[-1][1] - drive_trace.events[0][1]) / 1e9, 4
            )
            if report["drive_traffic_count"] != 8:
                raise RuntimeError("性能基线未创建预期的八辆交通车")
            args.profile_startup.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 0
        finally:
            app.close_game()

    smoke = args.smoke or args.window_smoke
    app = CoastalDrive(
        smoke=smoke,
        onscreen=args.window_smoke,
        output=args.output,
        seed=args.seed,
        track=args.track,
        road_shape=args.road_shape,
    )
    try:
        app.run()
        return 0 if not smoke or getattr(app, "smoke_passed", False) else 1
    finally:
        app.close_game()


if __name__ == "__main__":
    try:
        result = main()
    except Exception:
        # Report entry-point failures; exceptions are not swallowed in the game loop.
        user_data().joinpath("crash.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    raise SystemExit(result)
