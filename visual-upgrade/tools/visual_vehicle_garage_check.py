"""真实 Panda3D 车库渲染截图与双车型生命周期检查。"""

import argparse
import json
import sys
from pathlib import Path

from panda3d.core import Filename

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from application import CoastalDrive
from skins import MODELS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    output = ROOT / "logs/vehicle-garage" / f"{args.width}x{args.height}"
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=output, render_size=(args.width, args.height))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    rows = []
    try:
        app.session.menu()
        app.choose_garage()
        for model_id, skin_index, name in (
            (MODELS[0].id, 0, "sports-orange"),
            (MODELS[1].id, 4, "sedan-white"),
        ):
            app.garage.set_vehicle(model_id, skin_index)
            app.garage.update(0)
            for _ in range(3):
                app.taskMgr.step()
                app.graphicsEngine.renderFrame()
            path = output / f"{name}.png"
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path))), (
                f"screenshot failed: {path}"
            )
            body = app.garage.body.getChild(0)
            rows.append(
                {
                    "model": model_id,
                    "skin_index": skin_index,
                    "detail_nodes": body.findAllMatches("**/headlamp").getNumPaths()
                    + body.findAllMatches("**/tail-lamp").getNumPaths(),
                    "wheels": len(app.garage.wheels),
                    "screenshot": str(path),
                }
            )
        assert all(row["detail_nodes"] == 4 and row["wheels"] == 4 for row in rows)
        app.close_garage()
        assert app.render.findAllMatches("**/garage-preview").getNumPaths() == 0
        (output / "garage-visual-check.json").write_text(
            json.dumps({"passed": True, "renders": rows, "garage_root_removed": True}, indent=2),
            encoding="utf-8",
        )
    finally:
        app.close_game()
    print(json.dumps({"passed": True, "renders": rows}, indent=2))


if __name__ == "__main__":
    main()
