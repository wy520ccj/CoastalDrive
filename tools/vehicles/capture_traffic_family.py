"""在真实滨海场景中摆放三款交通车，留存正后和侧后视觉检查图。"""

import argparse
import math
import sys
from pathlib import Path

from panda3d.core import Filename, Quat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from application import CoastalDrive
from skins import apply_skin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    app = CoastalDrive(smoke=True, onscreen=True, seed=23, output=args.output,
                       render_size=(1920, 1080))
    app.taskMgr.remove("finish-smoke")
    try:
        app.taskMgr.step()
        app.hud.root.hide()
        app.panel.hide()
        app.main_menu.root.hide()
        state = app.session.current.traffic[0]
        if state.active:
            x, y, z = state.position
            angle = math.radians(state.heading)
            app.camera.setPos(x - 9 * math.sin(angle), y - 9 * math.cos(angle), z + 2.4)
            app.camera.lookAt(x, y, z + 0.3)
            app.graphicsEngine.renderFrame()
            path = args.output / "traffic-in-game.png"
            app.win.saveScreenshot(Filename.fromOsSpecific(str(path.resolve())))
            print(path)
        for index, (car, wheels) in enumerate(zip(app.scene.traffic, app.scene.traffic_wheels)):
            if index >= 3:
                car.hide()
                for wheel in wheels:
                    wheel.hide()
                continue
            x, y, z = 95 + (index - 1) * 3.1, 15, 0.48
            car.setPos(x, y, z)
            car.setHpr(0, 0, 0)
            car.show()
            apply_skin(car.getChild(0), index + 1)
            for wheel, (side, axle) in zip(wheels, ((-1, 1), (1, 1), (-1, -1), (1, -1))):
                wheel.setPos(x + side * 0.84, y + axle * 1.1, z - 0.12)
                wheel.setQuat(Quat.identQuat())
                wheel.show()
        app.scene.player.hide()
        for wheel in app.scene.wheels:
            wheel.hide()
        app.hud.root.hide()
        app.panel.hide()
        app.main_menu.root.hide()
        for name, position in (("rear", (95, -5, 3.8)),
                               ("quarter", (107, 3, 3.0))):
            app.camera.setPos(*position)
            app.camera.lookAt(95, 15, 0.6)
            app.graphicsEngine.renderFrame()
            path = args.output / f"traffic-{name}.png"
            app.win.saveScreenshot(Filename.fromOsSpecific(str(path.resolve())))
            print(path)
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
