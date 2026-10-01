"""离屏核对模式入口、菜单说明及两模式驾驶HUD，不代替人工驾驶验收。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename

from application import CoastalDrive
from driving_modes import DrivingMode
from race import GameMode


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
        report = {"resolution": [app.win.getXSize(), app.win.getYSize()],
                  "screenshots": captures, "simulation_reverse_speed_mps": app.session.current.player.speed,
                  "driving_mode": app.session.driving_mode.value,
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
