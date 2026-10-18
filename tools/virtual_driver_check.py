"""同窗方案库真实道路复测、原记录保留与布局采集；隔离玩家数据。"""

import argparse
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename

from application import CoastalDrive
from lab_experiment import LabOptions
from lab_runtime import runtime_fingerprint
from vehicle_schemes import list_schemes, save_scheme


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    app = CoastalDrive(smoke=True, output=output, lab_output=output/"reports", render_size=tuple(size))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    captures = []
    try:
        app.back_to_menu()
        window = app.win
        app.open_vehicle_lab()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == "lab" and app.win is window
        app.taskMgr.remove("lab-update")
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
        original = save_scheme(lab.scheme_root, "原配35k · 道路复测", baseline)
        better = max(schemes, key=lambda item: item.vehicle.config.lateral_stiffness)
        lab.set_options(LabOptions(duration=.1, speed_kph=20))
        lab.start_experiment()
        while not lab.run_state.done:
            lab.run_state.step()
        old, record = lab.run_state, lab.active_record()
        lab.entries["cg"].enterText(".48")
        files = {str(path.relative_to(lab.scheme_root)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in lab.scheme_root.rglob("*") if path.is_file()}
        lab.schemes.show()
        lab.schemes.indices = [next(i for i, item in enumerate(lab.schemes.schemes) if item.id == original.id),
                              next(i for i, item in enumerate(lab.schemes.schemes) if item.id == better.id)]
        lab.schemes.build_menu(0)
        lab.schemes.build_menu(1)
        lab.schemes.present()
        panel = lab.schemes.virtual_driver
        panel.show()

        def capture(name):
            lab.resize()
            for _ in range(6):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
            captures.append(name)

        capture("ready")
        panel.start()
        assert old.closed and lab.run_state is None
        shown = set()
        while not panel.comparison.done:
            panel.update()
            index = panel.comparison.index
            if index not in shown:
                capture("running-"+"AB"[index])
                shown.add(index)
        assert panel.comparison.status == "complete" and panel.comparison.run.closed
        a, b = panel.comparison.records
        assert not a.metadata["metrics"]["completed"] and b.metadata["metrics"]["completed"]
        assert a.metadata["metrics"]["valid_seconds"] is None and panel.report.is_file()
        capture("actual-results")
        assert lab.entries["cg"].get() == ".48" and lab.record.snapshots == record.snapshots
        assert all(hashlib.sha256((lab.scheme_root/name).read_bytes()).hexdigest() == sha for name, sha in files.items())
        panel.hide()
        assert not lab.schemes.root.isHidden()
        capture("returned-schemes")
        summary = {"passed": True, "runtime": runtime_fingerprint(), "size": size,
                   "metrics": [item.metadata["metrics"] for item in (a, b)], "report": str(panel.report),
                   "captures": captures, "same_window": app.win is window, "original_world_closed": old.closed,
                   "scheme_files_unchanged": True, "original_trial_and_draft_preserved": True,
                   "updates_player_progress": False, "human_gate": "pending",
                   "scope": "实际逐步物理/闭环Control；截图冻结更新，非人工驾驶或实时基准"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "bits": summary["runtime"]["math_scalar_bits"], "metrics": summary["metrics"]}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size), ensure_ascii=False))
