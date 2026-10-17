"""真实窗口/独立物理会话往返与同车对照证据；不代替人工驾驶。"""

import argparse
import json
import multiprocessing
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename

from application import CoastalDrive
from lab_application import VehicleLab
from lab_experiment import LabExperiment, LabOptions
from lab_game_comparison import GameComparison
from lab_records import LabRecord
from vehicle_designs import REFERENCE_DESIGN
from vehicle_workspace import WorkspaceVehicle


def capture(app, path):
    app.taskMgr.step()
    app.graphicsEngine.renderFrame()
    app.graphicsEngine.renderFrame()
    assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(path)))


def check(output, ui_only=False):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    records = []
    # 标准工况与工程改型方向分别留证；没有自动标定或合格阈值。
    cases = () if ui_only else (("base", {}), ("lower-cg", {"center_of_mass_height": .40}))
    for name, changes in cases:
        config = replace(REFERENCE_DESIGN, tire_substeps=2, **changes)
        for options in (LabOptions(duration=12.), LabOptions(maneuver="step_steer", speed_kph=60,
                                                            duration=3., onset=.3)):
            run = LabExperiment(options, config=config)
            try:
                while not run.done:
                    run.step()
                record = LabRecord.from_run(run)
            finally:
                run.close()
            comparison = GameComparison(record)
            try:
                while not comparison.done:
                    comparison.advance(.05)
                path = comparison.export(output/(name+"-"+options.maneuver))
                records.append({"name": name, "maneuver": options.maneuver, "report": str(path),
                                "reference": record.metadata["summary"], "game": comparison.run.summary()})
            finally:
                comparison.close()

    app = VehicleLab(offscreen=True, output=output/"records")
    app.taskMgr.remove("lab-update")
    try:
        app.set_options(LabOptions(maneuver="step_steer", speed_kph=60, duration=1., onset=.2,
                                   cg_height=.42, tire_reference_load=3600.))
        app.start_experiment()
        while not app.run_state.done:
            app.run_state.step()
        app.present_summary(app.run_state.summary())
        app.refresh_plots()
        app.show_sample(len(app.run_state.samples)-1)
        capture(app, output/"lab-trial.png")
        app.design_loop.show()
        capture(app, output/"lab-design-loop.png")
        app.design_loop.start_comparison()
        while app.design_loop.comparison is not None:
            app.design_loop.update()
        capture(app, output/"lab-compared.png")
        assert app.last_report.exists()
        app.userExit = lambda: None
        app.design_loop.drive()
        assert app.next_workspace == "game" and app.next_drive
        vehicle = WorkspaceVehicle.load()
        assert vehicle == app.workspace_vehicle
    finally:
        app.close_game()

    # 正式游戏独立会话进程，实际读取其Simulation配置与完成拍快照。
    game = CoastalDrive(smoke=True, independent_clock=True, output=output/"game", workspace_vehicle=vehicle)
    game.taskMgr.remove("finish-smoke")
    try:
        assert game.session.simulation.config == replace(vehicle.config, tire_substeps=1)
        assert game.session.current.tick >= 0
        capture(game, output/"game-drive.png")
        game.session.menu()
        game.refresh_panel()
        capture(game, output/"game-menu.png")
        game.userExit = lambda: None
        game.open_vehicle_lab()
        returned = game.workspace_vehicle
        assert returned.config == vehicle.config
        game_info = {"config": asdict(game.session.simulation.config), "tick": game.session.current.tick,
                     "pid": game.session.process.pid, "mode": game.session.driving_mode.value}
    finally:
        game.close_game()
    assert game.session.closed

    lab = VehicleLab(offscreen=True, output=output/"return-records", render_size=(1024, 768),
                     workspace_vehicle=returned)
    lab.taskMgr.remove("lab-update")
    try:
        assert lab.engineered_config == vehicle.config
        assert lab.read_options().friction == vehicle.config.road_friction
        capture(lab, output/"lab-return-1024.png")
    finally:
        lab.close_game()
    (output/"summary.json").write_text(json.dumps({"passed": True, "comparisons": records,
        "game": game_info, "vehicle": asdict(vehicle.config), "human_driving": "pending"},
        ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"passed": True, "output": str(output), "comparisons": len(records)}))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ui-only", action="store_true", help="只验证界面/进程往返，不重复标准工况")
    args = parser.parse_args()
    check(args.output.resolve(), args.ui_only)
