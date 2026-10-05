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
from skins import PLAYER_VEHICLES, SKINS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="+", choices=tuple(v.id for v in PLAYER_VEHICLES),
                        help="只记录指定工程车型的真实车库界面和车轮近景")
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
        if args.models:
            for model_id in args.models:
                app.garage_model_id = model_id
                app.garage_skin_index = 2
                app.garage.set_vehicle(model_id, 2)
                app._shown_phase = None
                app.refresh_panel()
                app.garage.update(0)
                capture(model_id+"-garage")
                app.aspect2d.hide()
                app.garage.car_root.setH(0)
                app.camLens.setFov(44)
                app.camera.setPos(2.25, 2.50, 1.1)
                app.camera.lookAt(.78, 1.1, .43)
                capture(model_id+"-wheel")
                app.aspect2d.show()
            assert app.session.simulation.snapshot() == before
            (args.output/"report.json").write_text(json.dumps({
                "resolution": [1920, 1080], "models": args.models,
                "kind": "actual offscreen garage render", "simulation_unchanged": True,
                "captures": captures,
            }, indent=2), encoding="utf-8")
            return
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
