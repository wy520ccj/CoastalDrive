"""用真实车库灯光记录主车各面和五种车漆，并保存完整车库界面。"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename

from application import CoastalDrive
from skins import SKINS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    app = CoastalDrive(smoke=True, output=args.output, render_size=(1920, 1080))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.session.menu()
    before = app.session.simulation.snapshot()
    app.choose_garage()
    captures = []

    def capture(name):
        app.taskMgr.step()
        for _ in range(12):
            app.graphicsEngine.renderFrame()
        path = args.output / (name + ".png")
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        captures.append(path.name)

    try:
        app.garage.update(0)
        capture("garage-ui")
        app.aspect2d.hide()
        app.camLens.setFov(44)
        for index, skin in enumerate(SKINS):
            app.garage.set_vehicle("sports", index)
            app.garage.car_root.setH(0)
            app.camera.setPos(4.6, -6.6, 2.8)
            app.camera.lookAt(0, -0.2, 0.78)
            capture("rear-" + skin.id)
        app.garage.set_vehicle("sports", 2)
        app.garage.car_root.setH(0)
        for name, eye, target in (
            ("front-red", (4.6, 6.6, 2.65), (0, 0.2, 0.73)),
            ("side-red", (7.2, 0, 2.0), (0, 0, 0.74)),
            ("rear-chase", (0, -7.8, 4.5), (0, 0, 0.65)),
            ("rear-level", (0, -7.8, 1.65), (0, -0.2, 0.74)),
            ("wheel-detail", (2.25, 2.50, 1.1), (0.78, 1.1, 0.43)),
        ):
            app.camera.setPos(*eye)
            app.camera.lookAt(*target)
            capture(name)
        assert app.session.simulation.snapshot() == before
        (args.output / "report.json").write_text(
            json.dumps(
                {
                    "resolution": [1920, 1080],
                    "renderer": app.win.getGsg().getDriverRenderer(),
                    "kind": "Actual garage render; close-up cameras are evidence-only",
                    "simulation_unchanged": True,
                    "captures": captures,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
