"""新回正曲线和数学说明的实际渲染/键盘检查；不替代人工体验。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import ButtonThrower, Filename, KeyboardButton, MouseWatcher, VirtualMouse

from lab_application import VehicleLab
from parameter_formulas import formula_key


def check(output, height):
    output.mkdir(parents=True, exist_ok=False)
    width = round(height*16/9)
    app = VehicleLab(offscreen=True, render_size=(width,height))
    mouse = VirtualMouse("aligning-pointer")
    mouse.setWindowSize(width,height)
    mouse.setMouseOn(True)
    watcher = app.dataRoot.attachNewNode(mouse).attachNewNode(MouseWatcher("aligning-watcher"))
    watcher.attachNewNode(ButtonThrower("aligning-keys"))
    app.aspect2d.node().setMouseWatcher(watcher.node())
    app.mouseWatcherNode = watcher.node()
    images = []

    def step():
        for _ in range(4):
            app.taskMgr.step()
            app.graphicsEngine.renderFrame()

    def capture(name):
        step()
        images.append(name+".png")
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/images[-1])))

    def press(key):
        mouse.pressButton(key)
        step()
        mouse.releaseButton(key)
        step()

    try:
        app.maneuver_menu.set(1)
        app.entries["speed"].enterText("60")
        app.entries["duration"].enterText("0.5")
        app.entries["onset"].enterText("0.1")
        app.start_experiment()
        while not app.run_state.done:
            step()
        assert app.run_state.config.tire_aligning_enabled
        app.plot_menu.set(len(app.plot_menu["items"])-1)
        assert app.plots[0].keys == ("mz_fl","mz_fr")
        assert any(abs(row["mz_fl"])>1. for row in app.run_state.samples)
        expected = app.run_state.samples[app.view_index]["mz_fl"]
        assert f"A {expected:.2f}" in app.plots[0].readout.getText()
        capture("01-actual-aligning-curves")
        for key in ("tire_contact_half_length", "tire_aligning_enabled"):
            app.focused_parameter = key
            app.hovered_parameter = None
            press(KeyboardButton.f1())
            assert app.parameter_help.key == key and not app.parameter_help.root.isHidden()
            assert app.parameter_help.formula_nodes
            for node, entry in zip(app.parameter_help.formula_nodes,
                                  app.parameter_help.formula_manifest["formulas"][formula_key(key)], strict=True):
                assert node.getTexture().getXSize() == entry["texture_width"]
            assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z > -.73
            capture("02-"+key)
            press(KeyboardButton.escape())
            assert app.parameter_help.root.isHidden()
        (output/"result.json").write_text(json.dumps({"height":height,"actual_key_F1":True,
            "actual_plot_menu_callback":True,"trial_has_nonzero_Mz":True,
            "texture_not_downsized":True,"notes_inside_card":True,"screenshots":images},indent=2),encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--height", required=True, choices=(720,1080), type=int)
    args = parser.parse_args()
    check(args.output.resolve(), args.height)
