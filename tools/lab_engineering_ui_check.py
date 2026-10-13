"""工程指标/新曲线/数学说明实际渲染与真实鼠标F1检查。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import ButtonThrower, Filename, KeyboardButton, MouseWatcher, Point3, VirtualMouse

from lab_application import VehicleLab
from lab_records import load_record


def check(output, records, steady_record, height):
    output.mkdir(parents=True, exist_ok=False)
    width = round(height*16/9)
    app = VehicleLab(offscreen=True, render_size=(width, height))
    screenshots = []

    def step():
        for _ in range(4):
            app.taskMgr.step()
            app.graphicsEngine.renderFrame()

    def capture(name):
        step()
        screenshots.append(name+".png")
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/screenshots[-1])))

    try:
        app.import_record(records/"dry-braking")
        assert app.record is not None
        app.engineering_panel.show()
        capture("01-braking-metrics")
        bounds = app.engineering_panel.notes.getTightBounds(app.engineering_panel.root)
        assert bounds[0].z > -.66 and bounds[1].x < 1.50
        mouse = VirtualMouse("engineering-mouse")
        mouse.setWindowSize(width, height)
        mouse.setMouseOn(True)
        watcher = app.dataRoot.attachNewNode(mouse).attachNewNode(MouseWatcher("engineering-watcher"))
        watcher.attachNewNode(ButtonThrower("engineering-keys"))
        app.aspect2d.node().setMouseWatcher(watcher.node())
        app.mouseWatcherNode = watcher.node()
        point = app.render2d.getRelativePoint(app.root, Point3(-1.15, 0, .35))
        mouse.setMousePos(round((point.x+1)*width/2), round((1-point.z)*height/2))
        step()
        assert app.hovered_parameter == "metric.mfdd"
        mouse.pressButton(KeyboardButton.f1())
        step()
        mouse.releaseButton(KeyboardButton.f1())
        step()
        assert app.parameter_help.key == "metric.mfdd"
        assert len(app.parameter_help.formula_nodes) == 1
        capture("02-mfdd-formula")
        assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z > -.73
        mouse.pressButton(KeyboardButton.escape())
        step()
        mouse.releaseButton(KeyboardButton.escape())
        step()
        assert app.parameter_help.root.isHidden() and not app.engineering_panel.root.isHidden()
        app.engineering_panel.hide()
        app.baseline = app.record
        app.import_record(records/"low-grip-braking")
        assert app.record.samples == load_record(records/"low-grip-braking").samples
        app.engineering_panel.show()
        assert "A 8.931" in app.engineering_panel.rows[0].getText()
        assert "B 5.889" in app.engineering_panel.rows[0].getText()
        capture("02b-ab-metrics")
        app.engineering_panel.hide()
        app.baseline = None
        app.import_record(steady_record)
        assert app.record.samples == load_record(steady_record).samples
        app.engineering_panel.show()
        capture("03-handling-metrics")
        assert "7.362" in app.engineering_panel.rows[1].getText()
        for key in ("metric.yaw_gain", "metric.beta", "metric.ltr_front", "metric.utilization_rr"):
            app.parameter_help.show(key)
            step()
            assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z > -.73
        app.parameter_help.hide()
        app.engineering_panel.hide()
        for index, name in enumerate(("轮胎侧偏角", "附着利用率", "车身侧偏 / 侧倾", "左右载荷转移")):
            app.plot_menu.set(app.plot_menu["items"].index(name))
            app.show_sample(len(app.record.samples)-1)
            capture(f"04-{index}-engineering-curves")
        assert app.run_state is None
        (output/"result.json").write_text(json.dumps({"height": height, "f1_metric": True,
                                                    "no_physics_world_started": True,
                                                    "screenshots": screenshots}, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--steady-record", type=Path, required=True)
    parser.add_argument("--height", type=int, choices=(720, 1080), required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.records.resolve(), args.steady_record.resolve(), args.height)
