"""真实键盘完成连续过门，采集逐拍记录/实际界面与同窗课题往返。"""

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
from lab_runtime import runtime_fingerprint
from session import Phase
from slalom_lesson import SlalomScores


def finish(app, target):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == target and app._workspace_steps is None
    app.taskMgr.remove("lab-update" if target == "lab" else "drive-update")


def check(output, size, layout_only=False):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    app = CoastalDrive(smoke=True, output=output, lab_output=output/"reports", render_size=tuple(size))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    captures = []

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.workspace == "game" and app.scene is not None:
            app.chase_camera.position = None
            app.apply_scene(app.session.current, 0.)
            app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                           track=app.session.simulation.track, countdown="", notice="")
        if app.workspace == "game":
            app.refresh_panel()
        before = app.session.current if app.session is not None else None
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        if before is not None:
            assert app.session.current == before
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
        captures.append({"name": name, "workspace": app.workspace, "updates_frozen": True})

    try:
        app.back_to_menu()
        app._shown_phase = None
        app.choose_highway()
        capture("highway-menu")
        app.buttons[5]["command"]()
        capture("slalom-rules")
        app.buttons[0]["command"]()
        for _ in range(360):
            app.session.tick()
        assert app.session.phase == Phase.DRIVING
        app.countdown.update("driving", 0, 0.)
        if layout_only:
            capture("layout-ready")
            assert app.hud.status_frame.getX() > -app.getAspectRatio()
            assert app.hud.speed_frame.getX() < app.getAspectRatio()
            summary = {"passed": True, "scope": "layout_only_no_course_drive", "size": size,
                "runtime": runtime_fingerprint(), "captures": captures, "human_gate": "pending"}
            (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"passed": True, "scope": summary["scope"]}
        config = app.session.vehicle_config
        app.session.set_controller(app.session.keyboard)
        driver = SlalomDriver(60, config, origin=app.session.current.player.position[1])
        rows, shown = [], set()
        for _ in range(40*120+2):
            apply_keys(app.session.keyboard, driver.sample(app.session.current, 1/120))
            keys = sorted(app.session.keyboard.pressed)
            app.session.tick()
            state = app.session.current
            lesson = app.session.highway.snapshot.slalom
            rows.append({"tick": state.tick, "time": state.time, "position": state.player.position,
                "velocity": state.player.velocity, "heading": state.player.heading,
                "collisions": state.collisions, "keys": keys, "lesson": asdict(lesson)})
            for name, distance in (("approach", 65.), ("left-gate", 112.), ("right-gate", 150.)):
                if lesson.position >= distance and name not in shown:
                    capture(name)
                    shown.add(name)
            if app.session.phase == Phase.RESULTS:
                break
        result = app.session.highway.snapshot
        assert result.succeeded and result.slalom.medal == "金", result
        assert app.session.vehicle_config == config and app.session.current.collisions == 0
        capture("actual-result")
        count = app.session.simulation._world.getNumRigidBodies()
        before = app.session.simulation.snapshot()
        app.scene.slalom_markers.apply(None, 0.)
        assert before == app.session.simulation.snapshot() and count == app.session.simulation._world.getNumRigidBodies()
        with gzip.open(output/"actual-drive.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(rows, stream, ensure_ascii=False)
        scores = SlalomScores(app.session.race.scores.path.with_name("slalom-best.json"),
                              "slalom-v1:"+app.session.score_variant())
        assert scores.best == result.slalom.run_seconds
        app.buttons[0]["command"]()
        for _ in range(360):
            app.session.tick()
        assert app.session.highway.snapshot.slalom.best_seconds == scores.best
        capture("retry")
        window = app.win
        app.open_vehicle_lab()
        finish(app, "lab")
        assert app.lab_return_slalom
        capture("returned-lab")
        app.lab.back_to_game()
        finish(app, "game")
        assert app.win is window and app.session.mode.value == "slalom_lesson"
        assert app.session.vehicle_config == config
        summary = {"passed": True, "runtime": runtime_fingerprint(), "size": size,
            "result": asdict(result), "vehicle_config": asdict(config), "captures": captures,
            "rigid_bodies": count, "markers_physics_unchanged": True, "restart_best": True,
            "same_window_returns_to_slalom": True, "driver": "实际KeyboardController二值按键请求；非人工驾驶",
            "capture": "冻结更新并重置展示相机到真实车位，仅作布局检查", "human_gate": "pending"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "bits": summary["runtime"]["math_scalar_bits"],
                "medal": result.slalom.medal, "run_seconds": result.slalom.run_seconds}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, nargs=2, default=(1280, 720))
    parser.add_argument("--layout-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.layout_only), ensure_ascii=False))
