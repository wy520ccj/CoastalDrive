"""颠簸制动预设、真实鼠标F1和可选A/B记录的两尺寸渲染。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from panda3d.core import ButtonThrower, Filename, KeyboardButton, MouseWatcher, Point3, VirtualMouse

from lab_application import VehicleLab
from lab_experiment import MANEUVERS
from lab_records import load_record


def check(output,height,records):
    output.mkdir(parents=True,exist_ok=False)
    width = round(height*16/9)
    app = VehicleLab(offscreen=True,render_size=(width,height))
    screenshots = []

    def step():
        for _ in range(4):app.taskMgr.step();app.graphicsEngine.renderFrame()

    def capture(name):
        step();screenshots.append(name+".png")
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/screenshots[-1])))

    try:
        app.import_engineering(ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
        app.maneuver_menu.set(tuple(MANEUVERS).index("ride_braking"))
        options = app.read_options()
        assert options.maneuver=="ride_braking" and options.speed_kph==30. and options.onset==.6
        assert app.run_state is None
        app.advanced_panel.show()
        capture("01-braking-protocol")
        mouse = VirtualMouse("braking-mouse")
        mouse.setWindowSize(width,height);mouse.setMouseOn(True)
        watcher = app.dataRoot.attachNewNode(mouse).attachNewNode(MouseWatcher("braking-watcher"))
        watcher.attachNewNode(ButtonThrower("braking-keys"))
        app.aspect2d.node().setMouseWatcher(watcher.node());app.mouseWatcherNode = watcher.node()
        point = app.render2d.getRelativePoint(app.root,Point3(.53,0,.22))
        mouse.setMousePos(round((point.x+1)*width/2),round((1-point.z)*height/2))
        step();assert app.hovered_parameter=="onset"
        mouse.pressButton(KeyboardButton.f1());step();mouse.releaseButton(KeyboardButton.f1());step()
        assert app.parameter_help.key=="onset" and len(app.parameter_help.formula_nodes)==2
        assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z>-.73
        capture("02-braking-onset-formula")
        app.parameter_help.hide();app.advanced_panel.hide()
        if records is not None:
            app.import_record(records/"mass-65")
            app.baseline = load_record(records/"mass-25")
            app.present_summary(app.record.metadata["summary"])
            app.set_plot_group("制动响应")
            app.show_sample(len(app.record.samples)-1)
            capture("03-braking-comparison")
            app.engineering_panel.show()
            capture("04-braking-metrics")
            assert app.engineering_panel.notes.getTightBounds(app.engineering_panel.root)[0].z>-.66
            app.parameter_help.show("metric.mfdd")
            capture("05-mfdd-reference")
            assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z>-.73
        (output/"result.json").write_text(json.dumps({"height":height,"screenshots":screenshots,
            "real_hover_f1":True,"record_comparison":records is not None,"physics_started":app.run_state is not None},indent=2),encoding="utf-8")
    finally:app.close_game()


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--height",type=int,choices=(720,1080),required=True)
    parser.add_argument("--records",type=Path)
    args = parser.parse_args()
    check(args.output.resolve(),args.height,None if args.records is None else args.records.resolve())
