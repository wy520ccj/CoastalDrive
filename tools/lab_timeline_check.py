"""通过窗口输入设备走真实PGSlider拖动链路，不直接调用seek或设置拖动标记。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from direct.gui import DirectGuiGlobals as DGG
from direct.showbase.DirectObject import DirectObject
from panda3d.core import Filename, MouseButton, Point3

from lab_application import VehicleLab
from lab_experiment import LabOptions
from lab_records import LabRecord, export_record


def check(output, probe=False):
    output.mkdir(parents=True, exist_ok=False)
    app = VehicleLab(output=output/"records")
    app.taskMgr.remove("lab-update")
    device = app.win.getInputDevice(0)
    device.enablePointerEvents()
    observed = []
    listener = DirectObject()
    listener.accept("mouse1", lambda: observed.append("global-mouse1"))
    listener.accept(DGG.B1PRESS+app.timeline.guiId, lambda event: observed.append("slider-press"))
    listener.accept(DGG.B1PRESS+app.timeline.thumb.guiId, lambda event: observed.append("thumb-press"))

    def pump():
        for _ in range(3):
            app.taskMgr.step()

    def pixel(node, x=0, z=0):
        point = app.render2d.getRelativePoint(node, Point3(x, 0, z))
        return (point.x+1)*app.win.getXSize()/2, (1-point.z)*app.win.getYSize()/2

    def move(node, x=0, z=0):
        target = pixel(node, x, z)
        assert app.win.movePointer(0, round(target[0]), round(target[1]))
        pump()

    def drag(ratio, *, outside=False):
        move(app.timeline, -.266+.532*app.timeline.getRatio())
        device.buttonDown(MouseButton.one())
        pump()
        pressed = app.pointer_pressed
        button_down = app.mouseWatcherNode.isButtonDown(MouseButton.one())
        start = -.266+.532*app.timeline.getRatio()
        target = -.266+.532*ratio
        for part in range(1, 49):
            move(app.timeline, start+(target-start)*part/48)
        if outside:
            move(app.timeline, -.266+.532*ratio, .09)
        device.buttonUp(MouseButton.one())
        pump()
        return {"pressed": pressed, "released": not app.pointer_pressed,
                "button_down": button_down, "events": list(observed),
                "slider_seconds": app.timeline.getValue(), "display_index": app.view_index,
                "display_seconds": app.view_index/120, "cursor": app.cursor_label.getText(),
                "global_mouse1_events": observed.count("global-mouse1"), "position": list(app.scene.vehicle.getPos())}

    def capture(name):
        pump()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/f"{name}.png")))

    results = {}
    try:
        app.set_options(LabOptions(maneuver="step_steer", speed_kph=40., duration=1., onset=.2))
        app.start_experiment()
        while not app.run_state.done:
            app.run_state.step()
        app.record = LabRecord.from_run(app.run_state)
        app.refresh_plots()
        app.show_sample(120)
        capture("01-end")
        results["completed"] = drag(.35)
        capture("02-dragged")
        if probe:
            results["broken_observed"] = app.view_index == 120 and app.timeline.getValue() < .5
        else:
            assert abs(app.view_index-42) <= 2, results["completed"]
            assert not app.pointer_pressed
            state = app.record.snapshots[app.view_index].player
            assert all(abs(a-b) < 1e-4 for a, b in zip(app.scene.vehicle.getPos(), state.position, strict=True))
            assert f"{app.view_index/120:.3f}" in app.cursor_label.getText()
            assert app.telemetry.getText().startswith(f"t  {app.view_index/120:.3f} s")
            move(app.timeline, -.266+.532*.8)
            device.buttonDown(MouseButton.one())
            pump()
            device.buttonUp(MouseButton.one())
            pump()
            assert abs(app.view_index-96) <= 1 and not app.pointer_pressed
            results["track_click_index"] = app.view_index
            report = export_record(app.record, output/"saved")
            app.import_record(report.parent)
            app.show_sample(120)
            results["loaded_release_outside"] = drag(.6, outside=True)
            assert abs(app.view_index-72) <= 2 and not app.pointer_pressed, results["loaded_release_outside"]
            app.start_experiment()
            for _ in range(30):
                app.run_state.step()
            app.run_state.paused = False
            app.refresh_plots()
            app.show_sample(30)
            pump()
            assert not app.run_state.paused
            tick = app.run_state.current.tick
            results["running"] = drag(.4)
            assert app.run_state.paused and app.run_state.current.tick == tick
            assert abs(app.view_index-12) <= 2, results["running"]
            capture("03-running-scrub-paused")
            results["passed"] = True
        (output/"summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(results, ensure_ascii=True))
    finally:
        listener.ignoreAll()
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    check(args.output.resolve(), args.probe)
