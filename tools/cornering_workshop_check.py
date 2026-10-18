"""实际工坊A/B、同窗道路圈与重启恢复；所有驾驶由现有控制器请求推进。"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename
from route_driver import RouteDriver

import workshop_cornering as cornering
from application import CoastalDrive
from driving_modes import DrivingMode
from lab_runtime import runtime_fingerprint
from race import GameMode
from session import Phase
from vehicle_workspace import WorkspaceVehicle


def finish_workspace(app, target):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == target and app._workspace_steps is None
    app.taskMgr.remove("lab-update" if target == "lab" else "drive-update")


def check(output, size, restore):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    vehicle = WorkspaceVehicle.load(restore) if restore is not None else None
    app = CoastalDrive(smoke=True, output=output, lab_output=output/"reports", render_size=tuple(size),
                       workspace_vehicle=vehicle, startup_workspace="lab")
    app.taskMgr.remove("finish-smoke")
    captures = []

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.workspace == "game":
            app.chase_camera.position = None
            app.apply_scene(app.session.current, 0.)
            app.refresh_panel()
        run = app.lab.run_state if app.workspace == "lab" else None
        before = run.current if run is not None else None
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        if run is not None:
            assert run.current == before
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
        captures.append({"name": name, "workspace": app.workspace, "physics_frozen_for_capture": True})

    try:
        finish_workspace(app, "lab")
        panel = app.lab.workshop
        if restore is not None:
            assert panel.topic == 1 and panel.result["passed"] and panel.selection() == (2, False, False)
            assert vehicle.workshop_result["road_validated"]
            panel.show()
            capture("restored-cornering")
            panel.share.showPopupMenu()
            capture("restored-tyre-popup")
            panel.share.hidePopupMenu()
            result = {"passed": True, "restored": True, "saved_road_validated": True, "receipt": panel.result,
                      "runtime": runtime_fingerprint(), "captures": captures, "human_gate": "pending"}
            (output/"summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"passed": True, "restored": True}
        panel.show()
        panel.topic_menu.set(1)
        capture("cornering-start")
        panel.share.set(2)
        panel.start()
        while panel.phase is not None:
            while not app.lab.run_state.done:
                app.lab.run_state.step()
            app.lab.update(SimpleNamespace(cont=None))
        assert panel.result["passed"] and panel.result["medal"] == "金"
        receipt = panel.result
        capture("cornering-gold")
        app.lab.plot_menu.set("路径跟踪")
        panel.hide()
        capture("cornering-traces")
        panel.show()
        panel.drive()
        finish_workspace(app, "game")
        assert app.session.mode == GameMode.TIME_TRIAL
        assert app.session.vehicle_config == DrivingMode.GAME.configured_vehicle(
            base_config=cornering.build_config(2, False, False))
        assert app.workspace_vehicle.workshop_result == receipt
        window = app.win
        for _ in range(360):
            app.session.tick()
        assert app.session.phase == Phase.DRIVING
        app.session.set_controller(RouteDriver(60))
        for _ in range(180*120):
            app.session.tick()
            if app.session.phase == Phase.RESULTS:
                break
        race = app.session.race.snapshot
        assert race.finished and not race.invalidated and race.last_lap is not None, race
        app._shown_phase = None
        app.refresh_panel()
        assert app.workspace_vehicle.workshop_result["road_validated"]
        capture("actual-road-result")
        app.buttons[1]["command"]()
        finish_workspace(app, "lab")
        assert app.win is window and app.lab.workshop.topic == 1 and app.lab.workshop.result["passed"]
        assert app.lab.workshop.selection() == (2, False, False)
        capture("returned-cornering")
        saved = WorkspaceVehicle.load(app.workspace_path)
        assert saved.workshop_result["road_validated"] and saved.config == cornering.build_config(2, False, False)
        result = {"passed": True, "runtime": runtime_fingerprint(), "size": size, "receipt": receipt,
            "actual_road_lap": asdict(race), "same_window": True, "road_validated": True,
            "workspace_path": str(app.workspace_path), "report_path": saved.report_path,
            "captures": captures, "human_gate": "pending", "driver": "RouteDriver(60)，真实物理完整有效圈；拍摄时冻结"}
        (output/"summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=lambda value: value.value), encoding="utf-8")
        return {"passed": True, "bits": result["runtime"]["math_scalar_bits"],
                "medal": receipt["medal"], "lap": race.last_lap, "workspace_path": str(app.workspace_path)}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", nargs=2, type=int, default=(1280, 720))
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.restore), ensure_ascii=False))
