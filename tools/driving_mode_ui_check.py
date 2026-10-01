"""离屏核对模式入口、菜单说明及两模式驾驶HUD，不代替人工驾驶验收。"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, Vec3

from application import CoastalDrive
from controls import ConstantController
from driving_modes import DrivingMode
from race import GameMode
from vehicle_state import Control, VehicleCommand


def run(output, height):
    output.mkdir(parents=True, exist_ok=False)
    app = CoastalDrive(smoke=True, output=output, render_size=(round(height * 16 / 9), height),
                       driving_mode=DrivingMode.GAME)
    app.taskMgr.remove("finish-smoke")
    captures = []

    def capture(name):
        app.taskMgr.step()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        path = output / f"{name}.png"
        if not app.win.saveScreenshot(Filename.fromOsSpecific(str(path))):
            raise RuntimeError("模式页面截图未保存")
        captures.append(path.name)

    try:
        app.back_to_menu()
        capture("game-menu")
        app.choose_driving_mode()
        app.set_driving_mode(DrivingMode.SIMULATION)
        capture("simulation-settings")
        app.toggle_abs()
        capture("simulation-abs-off-settings")
        assert not app.session.abs_enabled
        app.toggle_abs()
        app.back_from_driving_mode()
        capture("simulation-menu")
        app.start_game(mode=GameMode.FREE_DRIVE, track="test")
        for _ in range(360):
            app.session.tick()
        app.key_down("q")
        app.key_up("q")
        app.key_down("w")
        for _ in range(180):
            app.session.tick()
        app.key_up("w")
        capture("simulation-reverse-hud")
        assert app.session.current.player.gear == -1
        assert app.session.current.player.speed < 0
        reverse_speed = app.session.current.player.speed
        # 只设一次研究初值；随后压力、轮速和车身速度均由权威物理步推进。
        simulation = app.session.simulation
        simulation.reset_player((95, 0, .55))
        for _ in range(240):
            simulation.step(VehicleCommand())
        simulation.player._chassis.setLinearVelocity(Vec3(0, 100 / 3.6, 0))
        simulation.player.tires.initialize_rolling(100 / 3.6)
        app.session.keyboard.clear()
        for tick in range(120):
            simulation.step(VehicleCommand(brake=1, direction=1))
            state = simulation.snapshot()
            if any(brake.abs_active for brake in state.player.brake_states):
                break
        else:
            raise RuntimeError("截图工况未产生真实ABS介入")
        app.session.current = state
        app.session.previous = state
        app.session.set_controller(ConstantController(Control(brake=1)))
        capture("simulation-abs-active-hud")
        assert "ABS介入" in app.hud.help.getText()
        state = app.session.current
        report = {"resolution": [app.win.getXSize(), app.win.getYSize()],
                  "screenshots": captures, "simulation_reverse_speed_mps": reverse_speed,
                  "driving_mode": app.session.driving_mode.value,
                  "abs_active_trial_tick": tick + 1,
                  "brake_states": [asdict(brake) for brake in state.player.brake_states],
                  "human_acceptance": "pending", "passed": True}
        (output / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.height), indent=2))
