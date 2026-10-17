"""轮跳曲线/指标/数学排版与高级几何输入的实际渲染和鼠标F1核验。"""

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
    MouseWatcher,
    Point3,
    Vec3,
    VirtualMouse,
)

from lab_application import VehicleLab
from lab_records import load_record


def check(output, records, height):
    output.mkdir(parents=True, exist_ok=False)
    width = round(height*16/9)
    app = VehicleLab(offscreen=True, render_size=(width,height))
    screenshots = []

    def step():
        for _ in range(4):
            app.engine.taskMgr.step()
            app.engine.graphicsEngine.renderFrame()

    def capture(name):
        step()
        screenshots.append(name+".png")
        assert app.engine.win.saveScreenshot(Filename.fromOsSpecific(str(output/screenshots[-1])))

    try:
        app.import_record(records / "mass-65")
        assert app.record is not None and app.run_state is None
        app.baseline = load_record(records / "mass-25")
        app.show_sample(150)
        for index, label in enumerate(("车身 / 轮心振动","悬架行程 / 速度","轮胎径向压缩","质心运动")):
            app.set_plot_group(label)
            capture(f"{index+1:02}-curves")
        assert app.scene.surface_node.find("**/left-bump-top").getZ()==Vec3(0,0,app.read_options().bump_height_m).z
        app.engineering_panel.show()
        assert app.engineering_panel.group_menu.selectedIndex==1
        capture("05-ride-metrics")
        assert app.engineering_panel.notes.getTightBounds(app.engineering_panel.root)[0].z>-.66
        mouse = VirtualMouse("ride-mouse")
        mouse.setWindowSize(width,height)
        mouse.setMouseOn(True)
        watcher = app.dataRoot.attachNewNode(mouse).attachNewNode(MouseWatcher("ride-watcher"))
        watcher.attachNewNode(ButtonThrower("ride-keys"))
        app.engine.aspect2d.node().setMouseWatcher(watcher.node())
        app.engine.mouseWatcherNode = watcher.node()
        point = app.engine.render2d.getRelativePoint(app.root,Point3(-1.15,0,.35))
        mouse.setMousePos(round((point.x+1)*width/2),round((1-point.z)*height/2))
        step()
        assert app.hovered_parameter=="metric.ride.body_rms"
        mouse.pressButton(KeyboardButton.f1())
        step()
        mouse.releaseButton(KeyboardButton.f1())
        step()
        assert app.parameter_help.key=="metric.ride.body_rms" and len(app.parameter_help.formula_nodes)==2
        capture("06-rms-formula")
        for key in ("body_rms","body_peak","hub_peak","max_travel","unload_fraction",
                    "min_load_fl","min_load_fr","min_load_rl","min_load_rr","load_cv_fl"):
            app.parameter_help.show("metric.ride."+key)
            step()
            assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z>-.73,key
        capture("07-load-formula")
        app.parameter_help.hide()
        app.engineering_panel.group_menu.set(0)
        assert app.engineering_panel.group_menu.selectedIndex==0
        app.engineering_panel.group_menu.set(1)
        assert app.engineering_panel.group_menu.selectedIndex==1
        app.engineering_panel.hide()
        app.advanced_panel.show()
        app.entries["bump_height"].enterText("0.025")
        assert app.read_options().bump_height_m==.025
        capture("08-bump-inputs")
        app.parameter_help.show("bump_height")
        assert "0.025" in app.parameter_help.details.getText() and "0.01" in app.parameter_help.details.getText()
        capture("09-bump-help")
        app.parameter_help.show("speed")
        assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z>-.73
        capture("10-loaded-radius-formula")
        assert app.run_state is None
        (output / "result.json").write_text(json.dumps({"height":height,"screenshots":screenshots,
            "actual_mouse_f1":True,"ten_metric_formula_bounds":True,"groups_switch_without_recursion":True,
            "pending_geometry_distinguished":True,"physical_world_started":False},indent=2),encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--records",type=Path,required=True)
    parser.add_argument("--height",type=int,choices=(720,1080),required=True)
    args = parser.parse_args()
    check(args.output.resolve(),args.records.resolve(),args.height)
