"""真实键盘完成后以较慢节奏重试，保存逐拍证据与实际逐门界面。"""

import argparse
import gzip
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename
from slalom_driver import SlalomDriver, apply_keys

from application import CoastalDrive
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from session import Phase
from slalom_lesson import SlalomScores


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    source_start, runtime_start = model_fingerprint(), runtime_fingerprint()
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    captures, results, counts = [], [], []

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        app.chase_camera.position = None
        app.apply_scene(app.session.current, 0.)
        app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                       track="endless", countdown="", notice="")
        app.refresh_panel()
        before = app.session.current
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.session.current == before
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
        captures.append({"name": name, "tick": before.tick, "updates_frozen": True})

    try:
        app.back_to_menu()
        app.start_slalom_lesson()
        config = app.session.vehicle_config
        path = app.session.race.scores.path.with_name("slalom-best.json")
        key = "slalom-v1:"+app.session.score_variant()
        for attempt, speed in enumerate((60., 55.)):
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING
            app.countdown.update("driving", 0, 0.)
            app.session.set_controller(app.session.keyboard)
            if attempt:
                assert app.session.highway.snapshot.slalom.reference_times == results[0].gate_times
            driver = SlalomDriver(speed, config, origin=app.session.current.player.position[1])
            rows, seen = [], set()
            capture(f"run-{attempt+1}-ready")
            for _ in range(40*120+2):
                apply_keys(app.session.keyboard, driver.sample(app.session.current, 1/120))
                keys = sorted(app.session.keyboard.pressed)
                app.session.tick()
                state, result = app.session.current, app.session.highway.snapshot.slalom
                rows.append({"tick": state.tick, "time": state.time, "position": state.player.position,
                    "velocity": state.player.velocity, "heading": state.player.heading,
                    "collisions": state.collisions, "keys": keys, "lesson": asdict(result)})
                if result.gates in (1, 3) and result.gates not in seen:
                    capture(f"run-{attempt+1}-gate-{result.gates}")
                    seen.add(result.gates)
                if app.session.phase == Phase.RESULTS:
                    break
            assert result.succeeded and len(result.gate_times) == 6 and state.collisions == 0, result
            assert result.gate_times[-1] == result.run_seconds and app.session.vehicle_config == config
            assert result.new_best == (attempt == 0)
            results.append(result)
            counts.append(len(rows))
            capture(f"run-{attempt+1}-result")
            with gzip.open(output/f"run-{attempt+1}.json.gz", "wt", encoding="utf-8") as stream:
                json.dump(rows, stream, ensure_ascii=False)
            if attempt == 0:
                first_file = path.read_bytes()
                (output/"best-after-first.json").write_bytes(first_file)
                app.buttons[0]["command"]()
            else:
                assert result.run_seconds > results[0].run_seconds and path.read_bytes() == first_file
                stored = SlalomScores(path, key)
                assert stored.best_run["gate_times"] == list(results[0].gate_times)
                assert stored.best_run["clearances"] == list(results[0].clearances)
                (output/"best-after-retry.json").write_bytes(path.read_bytes())
        source_end, runtime_end = model_fingerprint(), runtime_fingerprint()
        assert source_start == source_end and runtime_start == runtime_end
        summary = {"passed": True, "size": size, "source_start": source_start, "source_end": source_end,
            "runtime_start": runtime_start, "runtime_end": runtime_end, "vehicle_config": asdict(config),
            "results": [asdict(result) for result in results], "ticks": counts, "captures": captures,
            "score_key": key, "best_bytes_unchanged_after_slower_retry": True,
            "driver": "实际KeyboardController二值请求；非人工驾驶", "human_gate": "pending"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "bits": runtime_end["math_scalar_bits"], "ticks": counts,
                "seconds": [result.run_seconds for result in results]}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size), ensure_ascii=False))
