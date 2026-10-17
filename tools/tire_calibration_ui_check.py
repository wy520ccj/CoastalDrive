"""实际工程文件进入GUI→唯一物理→记录/F1，原生文件选择器未自动操作。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import ButtonThrower, Filename, KeyboardButton, MouseWatcher, Point3, VirtualMouse

from lab_application import VehicleLab
from tire_calibration import PARAMETERS


def check(model, output, height):
    output.mkdir(parents=True, exist_ok=False)
    document = json.loads(model.read_text(encoding="utf-8"))
    width = round(height*16/9)
    app = VehicleLab(offscreen=True, render_size=(width, height))
    mouse = VirtualMouse("calibration-pointer")
    mouse.setWindowSize(width, height)
    mouse.setMouseOn(True)
    watcher = app.dataRoot.attachNewNode(mouse).attachNewNode(MouseWatcher("calibration-watcher"))
    watcher.attachNewNode(ButtonThrower("calibration-keys"))
    app.engine.aspect2d.node().setMouseWatcher(watcher.node())
    app.engine.mouseWatcherNode = watcher.node()
    screenshots = []

    def step():
        for _ in range(4):
            app.engine.taskMgr.step()
            app.engine.graphicsEngine.renderFrame()

    def capture(name):
        step()
        screenshots.append(name+".png")
        assert app.engine.win.saveScreenshot(Filename.fromOsSpecific(str(output/screenshots[-1])))

    def press(button):
        mouse.pressButton(button)
        step()
        mouse.releaseButton(button)
        step()

    try:
        app.import_engineering(model)
        assert app.run_state is None and app.engineered_config is not None
        assert "合成" in app.notice.getText()
        capture("01-imported-engineering")
        bad = json.loads(model.read_text(encoding="utf-8"))
        bad["metadata"]["tire_calibration"]["passed"] = False
        invalid = output/"rejected-model.json"
        invalid.write_text(json.dumps(bad), encoding="utf-8")
        preserved = app.engineered_config
        app.import_engineering(invalid)
        assert app.engineered_config is preserved and app.run_state is None
        assert "未通过" in app.notice.getText()
        app.import_engineering(model)
        position = app.engine.render2d.getRelativePoint(app.root, Point3(-1.59, 0, .074))
        mouse.setMousePos(round((position.x+1)*width/2), round((1-position.z)*height/2))
        step()
        assert app.hovered_parameter == "mu"
        press(KeyboardButton.f1())
        assert "合成算法恢复值" in app.parameter_help.notes.getText()
        assert "230kPa" in app.parameter_help.notes.getText()
        capture("02-effective-mu-source")
        press(KeyboardButton.escape())
        app.entries["duration"].enterText("0.25")
        app.start_experiment()
        while not app.run_state.done:
            step()
        for key in PARAMETERS:
            assert app.record.metadata["vehicle_config"][key] == document["metadata"]["tire_calibration"]["parameters"][key]
        assert app.record.metadata["parameter_metadata"] == document["metadata"]
        app.parameter_help.show("longitudinal_stiffness")
        capture("03-applied-stiffness")
        assert "合成算法恢复值" in app.parameter_help.notes.getText()
        assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z > -.73
        app.parameter_help.hide()
        app.vehicle_menu.set(2)
        assert app.engineered_config is None and app.parameter_metadata is None
        (output/"result.json").write_text(json.dumps({"height": height, "import_did_not_start_world": True,
                                                    "actual_f1_source": True, "solver_parameters_match": True,
                                                    "selector_clears_override": True, "screenshots": screenshots},
                                                   indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--height", type=int, choices=(720, 1080), required=True)
    args = parser.parse_args()
    check(args.model.resolve(), args.output.resolve(), args.height)
