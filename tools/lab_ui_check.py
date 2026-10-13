"""真实GUI计算、A/B、单步、回放与重开；离屏证据不替代人工体验。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename

from lab_application import VehicleLab
from lab_experiment import LabOptions
from lab_records import load_record


def check(output, height):
    output.mkdir(parents=True, exist_ok=False)
    app = VehicleLab(offscreen=True, output=output/"records", render_size=(round(height*16/9), height))
    screenshots = []

    def capture(name):
        app.taskMgr.step()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        path = output/f"{name}.png"
        if not app.win.saveScreenshot(Filename.fromOsSpecific(str(path))):
            raise RuntimeError("实验室截图未保存")
        screenshots.append(path.name)

    def finish():
        for _ in range(3000):
            app.taskMgr.step()
            if app.run_state.done:
                assert app.run_state.reason == "stopped"
                return
        raise RuntimeError("GUI未完成制动试验")

    try:
        capture("01-ready")
        app.start_experiment()
        app.toggle_pause()
        tick = app.run_state.current.tick
        for _ in range(4):
            app.taskMgr.step()
        assert app.run_state.current.tick == tick
        app.single_step()
        assert app.run_state.current.tick == tick+1
        app.toggle_pause()
        finish()
        baseline_summary = app.run_state.summary()
        capture("02-brake-A")
        app.pin_baseline()
        app.entries["mu"].enterText("0.6")
        app.start_experiment()
        finish()
        candidate_summary = app.run_state.summary()
        assert candidate_summary["distance_m"] > baseline_summary["distance_m"]
        assert app.baseline.metadata["summary"]["distance_m"] == baseline_summary["distance_m"]
        capture("03-brake-AB")
        app.set_plot_group("四轮法向载荷")
        capture("04-four-wheel-loads")
        app.set_plot_group("制动响应")
        tick = app.run_state.current.tick
        app.timeline["value"] = 1.
        app.timeline_hover = True
        app.set_pointer(True)
        app.seek()
        app.set_pointer(False)
        assert app.view_index == 120
        assert app.run_state.current.tick == tick
        capture("05-time-cursor")
        app.export()
        report = app.last_report
        assert report is not None and report.is_file()
        loaded = load_record(report.parent)
        assert loaded.samples == app.record.samples
        app.import_record(report.parent)
        assert app.run_state is None
        app.toggle_playback()
        for _ in range(10):
            app.taskMgr.step()
        assert app.run_state is None
        app.playing = False
        loaded_replay_has_world = app.run_state is not None
        capture("06-loaded-playback")
        app.set_options(LabOptions(maneuver="manual", speed_kph=40, duration=1))
        app.start_experiment()
        app.toggle_pause()
        app.entries["steer"].enterText("2")
        app.manual_entries["throttle"].enterText("30")
        app.apply_manual()
        app.single_step()
        assert app.run_state.commands[-1].steering == 2.
        assert app.run_state.commands[-1].throttle == .3
        app.show_manual()
        capture("07-actuator-input")
        app.clear_baseline()
        maneuvers = {}
        for mode, speed, name in (("constant_radius", 60, "08-constant-radius"),
                                  ("double_lane_change", 60, "09-double-lane-change"),
                                  ("split_braking", 100, "10-split-braking")):
            app.set_options(LabOptions(maneuver=mode, speed_kph=speed, duration=12))
            app.start_experiment()
            for _ in range(3000):
                app.taskMgr.step()
                if app.run_state.done:
                    break
            assert app.run_state.done and app.run_state.error is None
            maneuvers[mode] = app.run_state.summary()
            app.scene.camera_mode = 1
            app.show_sample(len(app.run_state.samples)-1)
            capture(name)
        app.toggle_details()
        capture("11-signal-details")
        app.toggle_details()
        app.toggle_advanced()
        capture("12-advanced-parameters")
        report = {"passed": True, "resolution": [app.win.getXSize(), app.win.getYSize()],
                  "renderer": app.win.getGsg().getDriverRenderer(), "screenshots": screenshots,
                  "A": baseline_summary, "B": candidate_summary,
                  "single_step_ticks": 1, "scrub_index": 120,
                  "loaded_replay_has_world": loaded_replay_has_world,
                  "maneuvers": maneuvers,
                  "human_acceptance": "pending"}
        (output/"summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        return report
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    result = check(args.output.resolve(), args.height)
    print(json.dumps({"passed": result["passed"], "resolution": result["resolution"],
                      "A_stop_m": result["A"]["stopping_distance_m"],
                      "B_stop_m": result["B"]["stopping_distance_m"]}, ensure_ascii=False))
