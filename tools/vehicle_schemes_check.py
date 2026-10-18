"""实际方案保存/曲线/同车道路圈/独立进程恢复，隔离用户存档。"""

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
from vehicle_schemes import compare_schemes, list_schemes, load_scheme
from vehicle_workspace import WorkspaceVehicle


def finish(app, target):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == target and app._workspace_steps is None
    app.taskMgr.remove("lab-update" if target == "lab" else "drive-update")


def check(output, size, restore):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    vehicle = WorkspaceVehicle.load(restore/"test-workspace-vehicle.json") if restore else None
    app = CoastalDrive(smoke=True, output=output, lab_output=output/"reports", render_size=tuple(size),
                       workspace_vehicle=vehicle, startup_workspace="lab")
    app.taskMgr.remove("finish-smoke")
    captures = []

    def capture(name):
        if app.workspace == "game":
            app.chase_camera.position = None
            app.apply_scene(app.session.current, 0.)
            app.refresh_panel()
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
        captures.append({"name": name, "workspace": app.workspace, "updates_frozen": True})

    try:
        finish(app, "lab")
        panel = app.lab.schemes
        if restore:
            app.scheme_root = restore/"test-schemes"
            app.lab.scheme_root = app.scheme_root
            panel.show()
            assert len(panel.schemes) == 2
            assert panel.selected(1).id == vehicle.scheme_id
            assert panel.selected(1).vehicle.workshop_result["road_validated"]
            assert not panel.selected(0).vehicle.workshop_result["road_validated"]
            capture("restarted-schemes")
            panel.menus[1].showPopupMenu()
            capture("restarted-popup")
            panel.menus[1].hidePopupMenu()
            panel.load_right()
            assert app.lab.engineered_config == cornering.build_config(2, False, False)
            assert app.lab.workshop.result["medal"] == "金"
            capture("restarted-trial")
            summary = {"passed": True, "restored": True, "road_state_isolated": True,
                       "scheme_id": vehicle.scheme_id, "runtime": runtime_fingerprint(), "captures": captures}
        else:
            panel.show()
            capture("empty-schemes")
            panel.hide()
            for index, name in ((1, "轻预算45k"), (2, "循迹50k")):
                work = app.lab.workshop
                work.show()
                work.set_topic(1)
                work.share.set(index)
                work.start()
                while work.phase is not None:
                    while not app.lab.run_state.done:
                        app.lab.run_state.step()
                    app.lab.update(SimpleNamespace(cont=None))
                assert work.result["passed"]
                panel.show()
                panel.name_entry.enterText(name)
                panel.save_current()
                assert len(panel.schemes) == index
                panel.hide()
            panel.show()
            comparison = compare_schemes(panel.selected(0), panel.selected(1))
            assert comparison["comparable"] and len(comparison["rows"]) == 5
            capture("two-schemes")
            panel.show_curves()
            app.lab.plot_menu.set("路径跟踪")
            app.lab.notice.dismiss()
            capture("scheme-curves")
            panel.show()
            panel.drive_right()
            finish(app, "game")
            window = app.win
            current = app.workspace_vehicle
            assert current.scheme_id is not None and current.config == cornering.build_config(2, False, False)
            assert app.session.mode == GameMode.TIME_TRIAL
            assert app.session.vehicle_config == DrivingMode.GAME.configured_vehicle(base_config=current.config)
            for _ in range(360):
                app.session.tick()
            app.session.set_controller(RouteDriver(60))
            for _ in range(180*120):
                app.session.tick()
                if app.session.phase == Phase.RESULTS:
                    break
            race = app.session.race.snapshot
            assert race.finished and not race.invalidated
            app._shown_phase = None
            app.refresh_panel()
            assert app.workspace_vehicle.workshop_result["road_validated"]
            saved = load_scheme(app.scheme_root, current.scheme_id)
            assert saved.vehicle.workshop_result["road_validated"]
            schemes, errors = list_schemes(app.scheme_root)
            assert not errors and not schemes[0].vehicle.workshop_result["road_validated"]
            capture("actual-road-result")
            app.buttons[1]["command"]()
            finish(app, "lab")
            assert app.win is window and app.lab.workshop.result["medal"] == "金"
            app.lab.schemes.show()
            assert app.lab.schemes.selected(1).id == current.scheme_id
            capture("returned-schemes")
            summary = {"passed": True, "runtime": runtime_fingerprint(), "size": size,
                       "comparison": comparison, "actual_road_lap": asdict(race), "same_window": True,
                       "road_state_isolated": True, "scheme_id": current.scheme_id, "captures": captures}
        summary["human_gate"] = "pending"
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2,
            default=lambda value: value.value), encoding="utf-8")
        return {"passed": True, "restored": bool(restore), "bits": summary["runtime"]["math_scalar_bits"]}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", nargs=2, type=int, default=(1280, 720))
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.restore.resolve() if args.restore else None)))
