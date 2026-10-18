"""从驾驶进阶进入两项真实键盘课题、返回查看成长，并独立启动读回。"""

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


def check(output, size, restore=False):
    output.mkdir(parents=True, exist_ok=restore)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    source_start, runtime_start = model_fingerprint(), runtime_fingerprint()
    scores_before = {name: (output/name).read_bytes() for name in ("braking-best.json", "slalom-best.json")} if restore else {}
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    captures, results, stages = [], [], []

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.scene is not None:
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
        captures.append({"name": name, "updates_frozen": True})

    try:
        app.back_to_menu()
        app._shown_phase = None
        app.refresh_panel()
        app.open_workshop_journey()
        app.messenger.send("tab")
        app.messenger.send("tab-up")
        panel = app.driving_journey
        assert not panel.root.isHidden() and app.journey.root.isHidden()
        if restore:
            assert panel.data["steps"] == 6 and panel.data["next_index"] is None
            assert all((output/name).read_bytes() == raw for name, raw in scores_before.items())
            capture("restored-progress")
            summary = {"passed": True, "scope": "independent_restart_read_only_no_drive",
                "data": panel.data, "size": size, "runtime": runtime_start,
                "score_files_unchanged": True, "captures": captures, "human_gate": "pending"}
            (output/"restore-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"passed": True, "steps": panel.data["steps"], "scope": summary["scope"]}
        assert panel.data["steps"] == 0
        capture("empty-progress")
        config = app.session.vehicle_config
        for index, topic in enumerate(("braking", "slalom")):
            stages.append(panel.data)
            assert panel.data["next_index"] == index
            panel.buttons[index]["command"]()
            assert panel.root.isHidden() and app.driving_journey_return
            capture(topic+"-rules")
            app.buttons[0]["command"]()
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING
            app.countdown.update("driving", 0, 0.)
            app.session.set_controller(app.session.keyboard)
            driver = SlalomDriver(60., config, origin=app.session.current.player.position[1])
            rows = []
            if topic == "braking":
                app.session.keyboard.press("w")
            for _ in range(40*120+2):
                if topic == "slalom":
                    apply_keys(app.session.keyboard, driver.sample(app.session.current, 1/120))
                elif app.session.highway.snapshot.braking.position >= 128.:
                    app.session.keyboard.release("w")
                    app.session.keyboard.press("s") if app.session.current.player.speed > .3 else app.session.keyboard.release("s")
                keys = sorted(app.session.keyboard.pressed)
                app.session.tick()
                state, highway = app.session.current, app.session.highway.snapshot
                result = highway.braking if topic == "braking" else highway.slalom
                rows.append({"tick": state.tick, "time": state.time, "position": state.player.position,
                    "velocity": state.player.velocity, "speed": state.player.speed, "heading": state.player.heading,
                    "collisions": state.collisions, "keys": keys, "result": asdict(result)})
                if app.session.phase == Phase.RESULTS:
                    break
            assert result.succeeded and result.medal == "金" and state.collisions == 0, result
            assert app.session.vehicle_config == config
            capture(topic+"-result")
            assert app.buttons[2]["text"] == "查看驾驶进阶"
            with gzip.open(output/(topic+"-drive.json.gz"), "wt", encoding="utf-8") as stream:
                json.dump(rows, stream, ensure_ascii=False)
            results.append({"topic": topic, "result": asdict(result), "ticks": len(rows)})
            app.buttons[2]["command"]()
            assert app.session.phase == Phase.MENU and not panel.root.isHidden()
            assert panel.data["steps"] == (3 if index == 0 else 6)
            capture(topic+"-progress")
        stages.append(panel.data)
        source_end, runtime_end = model_fingerprint(), runtime_fingerprint()
        assert source_start == source_end and runtime_start == runtime_end
        summary = {"passed": True, "size": size, "source_start": source_start, "source_end": source_end,
            "runtime_start": runtime_start, "runtime_end": runtime_end, "vehicle_config": asdict(config),
            "score_variant": app.session.score_variant(), "stages": stages, "results": results,
            "captures": captures, "driver": "实际KeyboardController二值请求；非人工驾驶", "human_gate": "pending"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "bits": runtime_end["math_scalar_bits"], "steps": [item["steps"] for item in stages]}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, nargs=2, default=(1280, 720))
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.restore), ensure_ascii=False))
