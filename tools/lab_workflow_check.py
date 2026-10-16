"""试验台全流程与多窗口比例渲染检查；不把自动检查记成人工体验。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename

from lab_application import VehicleLab
from lab_experiment import MANEUVERS, LabOptions
from lab_records import LabRecord, load_record
from parameter_help import group_parameters
from vehicle_designs import DESIGN_VEHICLES


def check(output, width, height, full, maneuver):
    output.mkdir(parents=True, exist_ok=False)
    app = VehicleLab(offscreen=True, output=output/"records", render_size=(width, height))
    app.taskMgr.remove("lab-update")
    screenshots = []
    results = {}

    def capture(name):
        app.taskMgr.step()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        path = output/f"{name}.png"
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        screenshots.append(path.name)

    def run(options, engineering=False):
        app.set_options(options)
        if engineering:
            app.import_engineering(ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
        app.start_experiment()
        assert app.run_state is not None and app.run_state.options == options
        while not app.run_state.done:
            app.run_state.step()
        assert app.run_state.error is None
        app.record = LabRecord.from_run(app.run_state)
        app.status.setText("制动完成" if app.run_state.reason == "stopped" else "时长完成")
        app.present_summary(app.run_state.summary())
        app.refresh_plots()
        app.show_sample(len(app.run_state.samples)-1)
        assert app.plots[0].labels == ["B"]
        return app.record

    try:
        capture("01-ready")
        app.toggle_advanced()
        app.entries["duration"].enterText("22wd")
        app.start_experiment()
        assert "时长须填写数字" in app.notice.getText()
        assert not app.notice.root.isHidden()
        assert app.entries["duration"].get() == "22wd"
        capture("02-chinese-error")
        app.notice.dismiss()
        app.set_options(LabOptions())
        app.advanced_panel.hide()
        if full:
            for design in DESIGN_VEHICLES:
                # 每个车型先选默认硬件；后续完整独立轮心工况另有来源。
                app.engineered_config = None
                app.engineered_vehicle_id = None
                app.parameter_metadata = None
                trial = run(LabOptions(vehicle_id=design.id, speed_kph=18, duration=.05))
                results[design.id] = trial.metadata["summary"]["ticks"]
            for mode in MANEUVERS:
                ride = mode in ("ride_bump", "ride_braking")
                trial = run(LabOptions(maneuver=mode, speed_kph=30 if mode == "ride_braking" else 18,
                    duration=3. if ride else .1, onset=.6 if ride else .025), engineering=ride)
                results[mode] = {"ticks": trial.metadata["summary"]["ticks"],
                                 "reason": trial.metadata["summary"]["reason"]}
        else:
            trial = run(LabOptions(maneuver=maneuver, speed_kph=30 if maneuver == "ride_braking" else 18,
                                   onset=.6 if maneuver == "ride_braking" else .5, duration=3.), engineering=True)
            results[maneuver] = trial.metadata["summary"]
        app.set_plot_group("车身 / 轮心振动")
        capture("03-completed-trial")
        app.pin_baseline()
        app.clear_baseline()
        app.toggle_advanced()
        capture("04-advanced")
        app.toggle_details()
        capture("05-signals")
        app.toggle_details()
        app.show_engineering()
        capture("06-engineering")
        app.engineering_panel.hide()
        app.parameter_help.show("suspension_installation_curves")
        capture("07-help-top")
        app.parameter_help.content_scroll.verticalScroll["value"] = 1
        capture("08-help-bottom")
        app.parameter_help.hide()
        if full:
            help_count = 0
            deepest = (0., "suspension_installation_curves")
            for group in ("chassis", "tires", "suspension", "powertrain", "electronics"):
                for key in group_parameters(group):
                    app.parameter_help.show(key)
                    bounds = app.parameter_help.notes.getTightBounds(app.parameter_help.content)
                    assert app.parameter_help.content_scroll["canvasSize"][2] <= bounds[0].z
                    if bounds[0].z < deepest[0]:
                        deepest = (bounds[0].z, key)
                    help_count += 1
            results["help_fields"] = help_count
            results["longest_help"] = {"key": deepest[1], "content_bottom": deepest[0]}
            app.parameter_help.show(deepest[1])
            capture("10-longest-help-top")
            app.parameter_help.content_scroll.verticalScroll["value"] = 1
            capture("11-longest-help-bottom")
            app.parameter_help.hide()
            app.export()
            assert app.last_report is not None
            saved = load_record(app.last_report.parent)
            assert saved.samples == app.record.samples
            app.import_record(app.last_report.parent)
            assert app.run_state is None
            assert "已保存试验模型" in app.model_note.getText()
            app.show_sample(0)
            app.toggle_playback()
            app.toggle_pause()
            assert not app.playing
            app.single_step()
            assert app.view_index == 1 and app.run_state is None
            app.pin_baseline()
            app.clear_baseline()
            app.toggle_record_menu()
            capture("09-record-menu")
            app.toggle_record_menu()
            results["record_export_load_replay"] = "passed"
        report = {"passed": True, "resolution": [width, height], "full": full,
                  "results": results, "screenshots": screenshots, "human_acceptance": "pending"}
        (output/"summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        return report
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--maneuver", choices=("ride_bump", "ride_braking"), default="ride_bump")
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.width, args.height, args.full, args.maneuver), ensure_ascii=False))
