"""检查自然海岸背景在主菜单、加载与实验台中的真实排版。"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from direct.gui.DirectGuiBase import DirectGuiWidget
from panda3d.core import Filename

from application import CoastalDrive


def check(output, width, height):
    output.mkdir(parents=True, exist_ok=False)
    app = CoastalDrive(smoke=True, output=output, lab_output=output/"records", render_size=(width, height))
    app.taskMgr.remove("finish-smoke")
    images = []

    def capture(name):
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        path = output/f"{name}.png"
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        images.append(path.name)

    try:
        window = app.win
        app.back_to_menu()
        app.taskMgr.step()
        assert not app.main_menu.root.isHidden()
        app.main_menu.select(6)
        capture("menu")
        gui_count = len(DirectGuiWidget.guiDict)
        low, high = app.main_menu.vehicle_note.getTightBounds(app.main_menu.content)
        assert -1.78 <= low.x < high.x <= 1.70
        app.main_menu.activate()
        captured_loading = False
        for _ in range(30):
            app.taskMgr.step()
            assert app.win is window
            if not app.workspace_loading.root.isHidden() and not captured_loading:
                capture("loading")
                captured_loading = True
            if app._workspace_steps is None:
                break
        assert app.workspace == "lab" and captured_loading
        capture("lab")
        app.lab.back_to_game()
        for _ in range(30):
            app.taskMgr.step()
            assert app.win is window
            if app._workspace_steps is None:
                break
        assert app.workspace == "game" and app.main_menu.root.isHidden() is False
        assert (app.win.getXSize(), app.win.getYSize()) == (width, height)
        assert len(DirectGuiWidget.guiDict) == gui_count
        capture("returned-menu")
        report = {"passed": True, "size": [width, height], "images": images,
                  "single_window": True, "human_visual_acceptance": "pending"}
        (output/"report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", nargs=2, type=int, default=(1280, 720))
    args = parser.parse_args()
    os.environ["LOCALAPPDATA"] = str(args.output.resolve()/"user-data")
    print(json.dumps(check(args.output, *args.size)))
