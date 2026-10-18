"""真实键盘请求完成定点刹停并捕获实际界面；不改写车辆位姿。"""

import argparse
import gzip
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename

from application import CoastalDrive
from lab_runtime import runtime_fingerprint
from session import Phase


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output / "user-data")
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    captures = []

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.session.phase != Phase.MENU:
            # 手动推进物理后拍静态预览，纯显示相机重新贴到当前真实车位。
            app.chase_camera.position = None
            app.apply_scene(app.session.current, 0.)
            app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                track=app.session.simulation.track, countdown="", notice="")
        app.refresh_panel()
        before = app.session.simulation.snapshot()
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert before == app.session.simulation.snapshot()
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
        captures.append({"name": name, "tick": before.tick, "physics_frozen_during_capture": True})

    try:
        app.back_to_menu()
        app._shown_phase = None
        capture("menu")
        app.choose_highway()
        capture("highway-menu")
        app.buttons[4]["command"]()
        capture("lesson-rules")
        config = app.session.vehicle_config
        app.buttons[0]["command"]()
        for _ in range(360):
            app.session.tick()
        assert app.session.phase == Phase.DRIVING
        app.countdown.update("driving", 0, 0.)
        app.session.set_controller(app.session.keyboard)
        app.session.keyboard.press("w")
        rows, braking = [], False
        shown = set()
        for _ in range(3601):
            lesson = app.session.highway.snapshot.braking
            if lesson.position >= 128.:
                app.session.keyboard.release("w")
                braking = True
            if braking:
                if app.session.current.player.speed > .3:
                    app.session.keyboard.press("s")
                else:
                    app.session.keyboard.release("s")
            app.session.tick()
            state = app.session.current
            lesson = app.session.highway.snapshot.braking
            rows.append({"tick": state.tick, "time": state.time, "position": state.player.position,
                "velocity": state.player.velocity, "keys": sorted(app.session.keyboard.pressed),
                "lesson": asdict(lesson)})
            for label, distance in (("approach", 75.), ("braking", 140.)):
                if lesson.position >= distance and label not in shown:
                    capture(label)
                    shown.add(label)
            if app.session.phase == Phase.RESULTS:
                break
        result = app.session.highway.snapshot
        assert result.succeeded, result
        assert app.session.current.collisions == 0 and app.session.vehicle_config == config
        capture("result")
        counts = app.session.simulation._world.getNumRigidBodies()
        before = app.session.simulation.snapshot()
        app.scene.braking_markers.apply(None, 0.)
        assert before == app.session.simulation.snapshot()
        assert counts == app.session.simulation._world.getNumRigidBodies()
        with gzip.open(output/"actual-drive.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(rows, stream, ensure_ascii=False)
        app.buttons[0]["command"]()
        assert app.session.highway.snapshot.braking is None  # 倒计时完成才建立新一轮规则。
        for _ in range(360):
            app.session.tick()
        assert app.session.highway.snapshot.braking.best_error == result.braking.best_error
        assert app.session.highway.snapshot.braking.entry_kph is None
        window = app.win
        app.session.finish()
        app._shown_phase = None
        app.refresh_panel()
        app.buttons[1]["command"]()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == "lab" and app.win is window
        assert app.lab.engineered_config is not None
        assert app.lab.engineered_config == app.workspace_vehicle.config
        assert app.workspace_vehicle.with_electronics(config) == app.workspace_vehicle
        app.taskMgr.remove("lab-update")
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/"returned-lab.png")))
        app.lab.back_to_game()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == "game" and app.win is window
        assert app.session.mode.value == "braking_lesson" and app.session.vehicle_config == config
        summary = {"passed": True, "runtime": runtime_fingerprint(), "size": size,
            "result": asdict(result), "vehicle_config": asdict(config), "captures": captures,
            "rigid_bodies": counts, "marker_physics_unchanged": True,
            "restart_restores_best": True, "driver": "真实Session.keyboard请求；128m开始制动，低速松开S防止既有自动倒车",
            "same_window_lab_return": True, "lab_returns_to_same_lesson": True,
            "capture_camera": "冻结物理，按当前真实车位重置展示相机；不作为动态跟车性能测试",
            "human_gate": "pending"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "bits": summary["runtime"]["math_scalar_bits"], "result": asdict(result)}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", nargs=2, type=int, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size), ensure_ascii=False))
