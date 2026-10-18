"""真实键盘铜→银→金、当前车历史与新最佳幽灵；独立重启只读检查。"""

import argparse
import gzip
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from coastal_medal_probe import keyboard_request
from panda3d.core import Filename
from route_driver import RouteDriver
from slalom_driver import apply_keys

from application import CoastalDrive
from coastal_medals import result_medal
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from race import BestTimes, GameMode
from session import Phase
from tracks import COASTAL_CIRCUIT


def check(output, size, restore=False):
    output.mkdir(parents=True, exist_ok=restore)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    source_start, runtime_start = model_fingerprint(), runtime_fingerprint()
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    captures, results = [], []

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.scene is not None:
            app.chase_camera.position = None
            app.apply_scene(app.session.current, 0.)
            app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                           track="coastal", countdown="", notice="")
        app.refresh_panel()
        before = app.session.current
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.session.current == before
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
        captures.append({"name": name, "updates_frozen": True})

    try:
        app.back_to_menu()
        app._shown_phase = None
        app.refresh_panel()
        config = app.session.vehicle_config
        path = app.session.race.scores.path
        if restore:
            raw = path.read_bytes()
            prior = json.loads((output/"summary.json").read_text(encoding="utf-8"))
            assert "金牌" in app.main_menu.time_goal.getText()
            capture("restored-menu")
            app.main_menu.buttons[0]["command"]()
            for _ in range(360):
                app.session.tick()
            state = app.session.race.snapshot
            assert state.reference_lap == prior["results"][-1]["last_lap"]
            assert list(state.reference_splits) == prior["results"][-1]["splits"]
            assert app.session.reference_ghost is not None and path.read_bytes() == raw
            assert app.session.reference_ghost.frames == prior["ticks"][-1]+1
            summary = {"passed": True, "scope": "independent_restart_no_lap_drive", "size": size,
                "runtime": runtime_start, "best": state.reference_lap, "ghost_frames": app.session.reference_ghost.frames,
                "scores_unchanged": True, "captures": captures, "human_gate": "pending"}
            (output/"restore-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"passed": True, "scope": summary["scope"], "best": state.reference_lap}
        capture("empty-menu")
        app.main_menu.buttons[0]["command"]()
        counts = []
        for index, (speed, expected) in enumerate(((35., "铜"), (45., "银"), (90., "金"))):
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING
            app.countdown.update("driving", 0, 0.)
            if index:
                assert app.session.race.snapshot.reference_lap == results[-1]["last_lap"]
                assert app.session.reference_ghost is not None
                assert app.session.reference_ghost.frames == counts[-1]+1
            app.session.set_controller(app.session.keyboard)
            driver, rows, shown = RouteDriver(speed), [], False
            for _ in range(120*130):
                apply_keys(app.session.keyboard, keyboard_request(driver.sample(app.session.current, 1/120)))
                keys = sorted(app.session.keyboard.pressed)
                app.session.tick()
                state, race = app.session.current, app.session.race.snapshot
                rows.append({"tick": state.tick, "time": state.time, "position": state.player.position,
                    "speed": state.player.speed, "collisions": state.collisions, "keys": keys,
                    "request": asdict(app.session.last_control), "race": {**asdict(race), "mode": race.mode.value}})
                if race.checkpoints == 2 and not shown:
                    capture(f"run-{index+1}-hud")
                    shown = True
                if app.session.phase == Phase.RESULTS:
                    break
            assert race.finished and not race.invalidated and result_medal(race, "coastal") == expected, race
            assert not race.save_error and race.new_best and "已保存" in race.ghost_notice
            assert state.collisions == 0 and app.session.vehicle_config == config
            capture(f"run-{index+1}-result")
            with gzip.open(output/f"run-{index+1}.json.gz", "wt", encoding="utf-8") as stream:
                json.dump(rows, stream, ensure_ascii=False)
            (output/f"best-after-{index+1}.json").write_bytes(path.read_bytes())
            results.append({**asdict(race), "mode": race.mode.value})
            counts.append(len(rows))
            if index < 2:
                app.buttons[0]["command"]()
        app.back_to_menu()
        app._shown_phase = None
        app.refresh_panel()
        assert "金牌" in app.main_menu.time_goal.getText()
        capture("gold-menu")
        assert BestTimes(path).get(GameMode.TIME_TRIAL, COASTAL_CIRCUIT.score_id+":"+app.session.score_variant()) == results[-1]["last_lap"]
        source_end, runtime_end = model_fingerprint(), runtime_fingerprint()
        assert source_start == source_end and runtime_start == runtime_end
        summary = {"passed": True, "size": size, "source_start": source_start, "source_end": source_end,
            "runtime_start": runtime_start, "runtime_end": runtime_end, "vehicle_config": asdict(config),
            "score_variant": app.session.score_variant(), "results": results, "ticks": counts,
            "captures": captures, "driver": "实际KeyboardController二值请求；非人工驾驶", "human_gate": "pending"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "bits": runtime_end["math_scalar_bits"], "seconds": [row["last_lap"] for row in results]}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, nargs=2, default=(1280, 720))
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.restore), ensure_ascii=False))
