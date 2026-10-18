"""复用真实虚拟试车记录，实际键盘驾驶B过门并同窗返回原复盘。"""

import argparse
import gzip
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename
from road_review_check import SavedComparison, archived_records
from slalom_driver import SlalomDriver, apply_keys

from application import CoastalDrive
from lab_experiment import LabOptions
from lab_runtime import runtime_fingerprint
from race import GameMode
from session import Phase
from vehicle_schemes import list_schemes, save_scheme


def finish(app, target):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == target and app._workspace_steps is None
    app.taskMgr.remove("lab-update" if target == "lab" else "drive-update")


def prepare(app, sdk):
    app.open_vehicle_lab()
    finish(app, "lab")
    lab = app.lab
    source = ROOT/"docs/evidence/DESIGN-SCHEMES-01/normal/schemes"
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        dest = lab.scheme_root/path.relative_to(source)
        dest = dest.with_suffix("") if path.suffix == ".gz" else dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())
    schemes, errors = list_schemes(lab.scheme_root)
    assert len(schemes) == 2 and not errors
    baseline, _, _ = schemes[0].records()
    original = save_scheme(lab.scheme_root, "原配35k", baseline)
    better = max(schemes, key=lambda item: item.vehicle.config.lateral_stiffness)
    lab.set_options(LabOptions(duration=.1, speed_kph=20))
    lab.start_experiment()
    while not lab.run_state.done:
        lab.run_state.step()
    lab.record = lab.active_record()
    lab.entries["cg"].enterText(".48")
    lab.schemes.show()
    lab.schemes.indices = [next(i for i, item in enumerate(lab.schemes.schemes) if item.id == identity)
                          for identity in (original.id, better.id)]
    for side in (0, 1):
        lab.schemes.build_menu(side)
    lab.schemes.present()
    panel = lab.schemes.virtual_driver
    panel.show()
    panel.comparison = SavedComparison(archived_records(sdk))
    panel.present()
    panel.review.show()
    panel.review.slider["value"] = 220.
    panel.review.seek()
    return panel, better


def check(output, sdk, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    app = CoastalDrive(smoke=True, output=output, lab_output=output/"reports", render_size=tuple(size))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    captures = []
    try:
        panel, better = prepare(app, sdk)
        old_lab, window = app.lab, app.win
        record, frozen = old_lab.record, panel.comparison.records
        files = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in app.scheme_root.rglob("*") if path.is_file()}

        def capture(name):
            if app.workspace == "lab":
                app.lab.resize()
            else:
                app.hud.resize(app.getAspectRatio())
                app.chase_camera.position = None
                app.apply_scene(app.session.current, 0.)
                app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                               track=app.session.simulation.track, countdown="", notice="")
                app.refresh_panel()
            for _ in range(6):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
            captures.append(name)

        capture("original-review")
        panel.review.drive_button["command"]()
        finish(app, "game")
        assert app.win is window and old_lab._closed
        assert app.session.mode == GameMode.SLALOM_LESSON
        assert app.workspace_vehicle.config == better.vehicle.config
        assert app.workspace_vehicle.scheme_id == better.id
        assert app.session.vehicle_config.road_friction == better.vehicle.config.road_friction
        for _ in range(360):
            app.session.tick()
        assert app.session.phase == Phase.DRIVING
        app.countdown.update("driving", 0, 0.)
        capture("scheme-course-start")
        app.session.set_controller(app.session.keyboard)
        driver = SlalomDriver(60., app.session.vehicle_config, origin=app.session.current.player.position[1])
        rows = []
        for _ in range(40*120+2):
            apply_keys(app.session.keyboard, driver.sample(app.session.current, 1/120))
            keys = sorted(app.session.keyboard.pressed)
            app.session.tick()
            state, result = app.session.current, app.session.highway.snapshot.slalom
            rows.append({"tick": state.tick, "time": state.time, "position": state.player.position,
                "heading": state.player.heading, "velocity": state.player.velocity, "keys": keys,
                "collisions": state.collisions, "result": asdict(result)})
            if app.session.phase == Phase.RESULTS:
                break
        assert app.session.phase == Phase.RESULTS
        result = app.session.highway.snapshot.slalom
        capture("actual-player-result")
        with gzip.open(output/"actual-player-drive.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(rows, stream, ensure_ascii=False)
        player_config = app.session.vehicle_config
        app.open_vehicle_lab()
        finish(app, "lab")
        restored = app.lab.schemes.virtual_driver
        assert app.win is window and not restored.review.root.isHidden()
        assert restored.review.slider["value"] == 220. and app.lab.entries["cg"].get() == ".48"
        assert app.lab.record.snapshots == record.snapshots
        assert tuple(restored.comparison.records) == tuple(frozen)
        assert all(hashlib.sha256(path.read_bytes()).hexdigest() == sha for path, sha in files.items())
        capture("returned-original-review")
        summary = {"passed": True, "runtime": runtime_fingerprint(), "size": size,
            "archive_sdk": sdk, "captures": captures, "player_result": asdict(result),
            "player_config": asdict(player_config), "saved_vehicle": asdict(better.vehicle),
            "same_window": True, "record_and_draft_preserved": True, "comparison_and_cursor_preserved": True,
            "scheme_files_unchanged": True, "virtual_evidence": "复用VIRTUAL-DRIVER-01原真实A/B，不重跑虚拟驾驶",
            "player_evidence": "本次真实KeyboardController二值请求；非人工驾驶", "human_gate": "pending"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "bits": summary["runtime"]["math_scalar_bits"], "player_result": asdict(result)}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-sdk", choices=("normal", "double"), default="normal")
    parser.add_argument("--size", type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.archive_sdk, args.size), ensure_ascii=False))
