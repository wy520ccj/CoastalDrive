"""真实F1键/鼠标/焦点的参数说明检查；不启动新物理试验。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import (
    ButtonThrower,
    Filename,
    KeyboardButton,
    MouseButton,
    MouseWatcher,
    PGMouseWatcherBackground,
    Point3,
    VirtualMouse,
)

from lab_application import VehicleLab
from parameter_formulas import formula_key
from parameter_help import group_parameters
from vehicle_parameters import PARAMETER_GROUPS


def check(output, height):
    output.mkdir(parents=True, exist_ok=False)
    width = round(height * 16 / 9)
    app = VehicleLab(offscreen=True, render_size=(width, height))
    mouse = VirtualMouse("parameter-pointer")
    mouse.setWindowSize(width, height)
    mouse.setMouseOn(True)
    watcher = app.dataRoot.attachNewNode(mouse).attachNewNode(MouseWatcher("parameter-watcher"))
    watcher.attachNewNode(ButtonThrower("parameter-keys"))
    app.engine.mouseWatcherNode = watcher.node()
    app.engine.aspect2d.node().setMouseWatcher(watcher.node())
    watcher.node().addRegion(PGMouseWatcherBackground())
    screenshots = []

    def step(count=4):
        for _ in range(count):
            app.engine.taskMgr.step()
            app.engine.graphicsEngine.renderFrame()

    def point(x, z):
        pos = app.engine.render2d.getRelativePoint(app.root, Point3(x, 0, z))
        mouse.setMousePos(round((pos.x + 1) * width / 2), round((1 - pos.z) * height / 2))
        step()

    def press(button):
        mouse.pressButton(button)
        step()
        mouse.releaseButton(button)
        step()

    def capture(name):
        step()
        screenshots.append(name + ".png")
        assert app.engine.win.saveScreenshot(Filename.fromOsSpecific(str(output / screenshots[-1])))

    try:
        app.advanced_panel.show()
        point(.49, .080)
        assert app.hovered_parameter == "tire_load"
        press(KeyboardButton.f1())
        assert not app.parameter_help.root.isHidden() and app.parameter_help.key == "tire_load"
        assert len(app.parameter_help.formula_nodes) == 3
        capture("01-hover-tire-load")
        press(KeyboardButton.escape())
        assert app.parameter_help.root.isHidden() and not app.advanced_panel.isHidden()
        point(.87, .077)
        press(MouseButton.one())
        assert app.focused_parameter == "tire_load"
        app.entries["tire_load"].enterText("not-a-number")
        point(1.65, -.80)
        press(KeyboardButton.f1())
        assert app.parameter_help.key == "tire_load"
        assert "not-a-number" in app.parameter_help.details.getText()
        assert "2943" in app.parameter_help.details.getText()
        capture("02-focused-unsubmitted-input")
        app.parameter_help.show("braking.response_time")
        assert len(app.parameter_help.formula_nodes) == 1
        capture("03-abs-response")
        for group in PARAMETER_GROUPS:
            for key in group_parameters(group):
                app.parameter_help.show(key)
                assert app.parameter_help.key == key and app.parameter_help.title.getText()
                step(1)
                assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z > -.73, key
        app.parameter_help.show("body_inertia")
        capture("04-inertia")
        app.parameter_help.show("steer")
        capture("04b-steering")
        app.parameter_help.show("mass")
        assert not app.parameter_help.formula_nodes
        capture("04c-input-data")
        for key in ("speed", "onset", "cg", "radius", "manual.clutch"):
            app.parameter_help.show(key)
            step(1)
            assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z > -.73, key
        app.parameter_help.hide()
        app.manual_panel.show()
        point(-.55, .312)
        press(KeyboardButton.f1())
        assert app.parameter_help.key == "manual.throttle"
        capture("04d-manual-hover")
        press(KeyboardButton.escape())
        assert not app.manual_panel.isHidden()
        app.manual_panel.hide()
        for key in ("tire_load", "braking.response_time", "steer"):
            app.parameter_help.show(key)
            entries = app.parameter_help.formula_manifest["formulas"][formula_key(key)]
            for node, entry in zip(app.parameter_help.formula_nodes, entries, strict=True):
                assert node.getTexture().getXSize() == entry["texture_width"]
                assert node.getTexture().getYSize() == entry["texture_height"]
        assert app.run_state is None and app.entries["tire_load"].get() == "not-a-number"
        app.parameter_help.hide()
        app.entries["tire_load"].enterText("4100")
        app.entries["duration"].enterText("0.1")
        app.start_experiment()
        while not app.run_state.done:
            step(1)
        app.entries["tire_load"].enterText("5000")
        app.parameter_help.show("tire_load")
        assert "5000" in app.parameter_help.details.getText()
        assert "4100" in app.parameter_help.details.getText()
        assert app.run_state.config.tire_reference_load == 4100.
        capture("05-running-config-vs-pending")
        result = {"height": height, "hover_f1": True, "focused_f1": True,
                  "invalid_pending_input_preserved": True, "physics_started_by_help": False,
                  "explicit_context_trial": True, "current_N": 4100., "pending_N": 5000.,
                  "parameter_count": sum(len(group_parameters(g)) for g in PARAMETER_GROUPS),
                  "screenshots": screenshots}
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--height", type=int, choices=(720, 1080), required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.height)
