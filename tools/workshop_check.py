"""真实A/B、同窗试驾与恢复；结果页使用显式规则夹具，不代替人工驾驶。"""

import argparse
import json
import multiprocessing
import os
import sys
from dataclasses import replace
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename

from application import CoastalDrive
from lab_application import VehicleLab
from lab_runtime import runtime_fingerprint
from race import GameMode
from session import Phase
from vehicle_workspace import WorkspaceVehicle
from workshop import build_config


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check(output, vehicle_path=None):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    vehicle = WorkspaceVehicle.load(vehicle_path) if vehicle_path is not None else None
    if vehicle is not None:
        vehicle = replace(vehicle, workshop_result={**vehicle.workshop_result, "road_validated": False})
    app = CoastalDrive(smoke=True, output=output, lab_output=output/"records", independent_clock=False,
                       workspace_vehicle=vehicle)
    app.taskMgr.remove("finish-smoke")
    window = app.win
    results = []

    def pump(target):
        started = perf_counter()
        while app._workspace_steps is not None:
            require(perf_counter()-started < 90, "切换超时")
            app.taskMgr.step()
        require(app.workspace == target and app.win is window, "工作方式或窗口错误")

    def capture(name):
        for _ in range(3):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        require(app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/f"{name}.png"))), "截图失败")

    def trial(share, large):
        panel = app.lab.workshop
        panel.share.set(share)
        panel.brakes.set(int(large))
        panel.start()
        while panel.phase is not None:
            app.taskMgr.step()
        require(panel.result is not None, "挑战未产生结果")
        results.append(panel.result)
        return panel.result

    try:
        app.open_vehicle_lab()
        pump("lab")
        panel = app.lab.workshop
        panel.show()
        capture("01-brief")
        if vehicle_path is None:
            require(not trial(0, False)["passed"], "原方案不应通过")
            capture("02-original-fail")
            require(not trial(2, True)["passed"], "超预算组合不应通过")
            capture("03-over-budget")
            require(trial(2, False)["medal"] == "金", "节约方案未获得金牌")
        else:
            require(panel.result is not None and panel.result["medal"] == "金", "历史真实记录未恢复")
        capture("04-gold")
        panel.hide()
        capture("05-curves")
        panel.show()
        panel.drive()
        pump("game")
        require(app.session.mode == GameMode.TIME_TRIAL, "挑战试驾未进入计时")
        require(app.session.base_vehicle_config == build_config(2, False), "未使用试验车辆")
        require(app.workspace_vehicle.workshop_result["medal"] == "金", "成绩丢失")
        capture("06-road")
        # 仅验证结果页/保存绑定；实际驾驶通关与圈速另行人工验收。
        app.session.race.snapshot = replace(app.session.race.snapshot, finished=True,
                                            invalidated=True, last_lap=90., invalid_reason="车辆复位")
        app.session.phase = Phase.RESULTS
        app.refresh_panel()
        require(not app.workspace_vehicle.workshop_result["road_validated"], "无效圈错误获奖")
        capture("07-invalid-road-fixture")
        app.session.race.snapshot = replace(app.session.race.snapshot, invalidated=False, invalid_reason="")
        app._shown_phase = None
        app.refresh_panel()
        require(app.workspace_vehicle.workshop_result["road_validated"], "有效圈结果未保存")
        require(WorkspaceVehicle.load(app.workspace_path).workshop_result["road_validated"], "道路进度未落盘")
        capture("08-valid-road-fixture")
        vehicle = app.workspace_vehicle
        require(app.buttons[1]["text"] == "返回工坊", "结算缺少返回工坊入口")
        app.buttons[1]["command"]()
        pump("lab")
        app.lab.workshop.show()
        require(app.lab.workshop.result["medal"] == "金", "返回工坊丢失挑战结果")
        capture("09-restored")
        app.close_game()
        # 无内存工作区的新窗口，从真实导出记录恢复挑战。
        restarted = VehicleLab(offscreen=True, output=output/"restart", workspace_vehicle=vehicle)
        try:
            require(restarted.workshop.result is not None and restarted.workshop.result["passed"], "重启丢失挑战")
            restarted.workshop.show()
            for _ in range(3):
                restarted.engine.taskMgr.step()
                restarted.engine.graphicsEngine.renderFrame()
            restarted.engine.graphicsEngine.syncFrame()
            require(restarted.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/"10-restarted.png"))), "截图失败")
        finally:
            restarted.close_game()
        report = {"passed": True, "precision_bits": runtime_fingerprint()["math_scalar_bits"],
                  "real_trials": results, "same_window": True, "restart_from_record": True,
                  "reused_record": str(vehicle_path) if vehicle_path is not None else None,
                  "road_result_fixture_only": True, "human_driving": "not_run"}
        (output/"summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        app.close_game()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vehicle", type=Path, help="复用已有真实记录，仅补查界面/交接")
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.vehicle), ensure_ascii=False))
