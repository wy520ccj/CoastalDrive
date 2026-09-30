"""同一可见驾驶窗口对照新旧N按键路径，不作为整体性能Gate。"""

import argparse
import cProfile
import importlib.util
import json
import os
import pstats
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import MethodType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename

from application import CoastalDrive
from controls import ConstantController
from race import GameMode
from session import Phase
from simulation import Control


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    source = subprocess.check_output(["git", "show", "fc2a16b:src/application.py"],
                                     cwd=ROOT).decode("utf-8")
    path = args.output / "baseline_application.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("baseline_application", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = CoastalDrive(onscreen=True, output=args.output)
    current_cycle = app.cycle_radio
    rows = []
    try:
        app.start_game(mode=GameMode.FREE_DRIVE)
        started = time.perf_counter()
        while app.session.phase != Phase.DRIVING or time.perf_counter()-started < 6:
            app.taskMgr.step()
            if time.perf_counter()-started > 30:
                raise RuntimeError("驾驶预热未完成")
        app.session.controller = ConstantController(Control(throttle=.28))
        for index in range(24):
            app.session.notice = ""
            app.hud.select_radio(None)
            case = "old_key_path" if index % 2 == 0 else "new_key_path"
            app.cycle_radio = (MethodType(module.CoastalDrive.cycle_radio, app)
                               if index % 2 == 0 else current_cycle)
            started = time.perf_counter()
            while time.perf_counter()-started < .25:
                frame_started = time.perf_counter()
                app.taskMgr.step()
                previous_step = (time.perf_counter()-frame_started)*1000
            previous_frame = app.clock.getDt()*1000
            started = time.perf_counter()
            app.key_down("n")
            app.key_up("n")
            key_ms = (time.perf_counter()-started)*1000
            profiler = cProfile.Profile() if args.profile and index == 1 else None
            if profiler is not None:
                profiler.enable()
            frame_started = time.perf_counter()
            app.taskMgr.step()
            next_step = (time.perf_counter()-frame_started)*1000
            if profiler is not None:
                profiler.disable()
                with (args.output / "switch-profile.txt").open("w") as stream:
                    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(35)
            properties = app.win.getProperties()
            rows.append({"case": case, "key_ms": key_ms,
                         "previous_frame_ms": previous_frame,
                         "next_frame_ms": app.clock.getDt()*1000,
                         "previous_step_ms": previous_step, "next_step_ms": next_step,
                         "foreground": properties.getForeground(),
                         "minimized": properties.getMinimized(),
                         "station": app.audio_settings.radio_station,
                         "phase": app.session.phase.value})
        summary = {}
        for name in ("old_key_path", "new_key_path"):
            values = [row["key_ms"] for row in rows if row["case"] == name]
            summary[name] = {"median_ms": statistics.median(values), "max_ms": max(values)}
        report = {"kind": "same visible driving window; both key paths use new preloaded music",
                  "passed": all(row["foreground"] and not row["minimized"]
                                and row["phase"] == "driving" for row in rows)
                  and summary["new_key_path"]["max_ms"] < 1,
                  "summary": summary, "frames": rows}
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        app.soundscape.music.select(2)
        app.session.notice = ""
        app.hud.select_radio(2)
        app.taskMgr.step()
        app.graphicsEngine.renderFrame()
        app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output / "radio-hud.png")))
        print(json.dumps({"passed": report["passed"], "summary": summary}))
        return 0 if report["passed"] else 1
    finally:
        app.cycle_radio = current_cycle
        app.close_game()


if __name__ == "__main__":
    raise SystemExit(main())
