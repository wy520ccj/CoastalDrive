"""复用归档真实道路完成步检查复盘；不重新驾驶或生成玩家成绩。"""

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
from road_comparison import RoadRecord, export_comparison
from snapshot_wire import decode_snapshots
from vehicle_state import Control


class SavedComparison:
    """验证工具只提供已结束的原始记录，不持有Simulation。"""
    done = True
    status = "complete"

    def __init__(self, records):
        self.records = records

    def close(self):
        pass


def archived_records(sdk):
    base = ROOT/"docs/evidence/VIRTUAL-DRIVER-01"/sdk/"report"
    records = []
    for side in ("A", "B"):
        document = json.loads(gzip.decompress((base/side/"trial.json.gz").read_bytes()))
        payload = gzip.decompress((base/side/"snapshots.bin.gz").read_bytes())
        if hashlib.sha256(payload).hexdigest() != document["snapshot_sha256"]:
            raise ValueError("归档道路快照SHA不一致")
        states, _ = decode_snapshots(payload)
        metadata = {key: value for key, value in document.items()
                    if key not in ("snapshot_sha256", "controls", "rows", "gate_crossings")}
        records.append(RoadRecord(metadata, states, tuple(Control(**row) for row in document["controls"]),
                                  tuple(document["rows"])))
    return tuple(records)


def check(output, sdk, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    records = archived_records(sdk)
    app = CoastalDrive(smoke=True, output=output, lab_output=output/"reports", render_size=tuple(size), startup_workspace="lab")
    app.taskMgr.remove("finish-smoke")
    captures = []
    try:
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == "lab"
        app.taskMgr.remove("lab-update")
        lab = app.lab
        panel = lab.schemes.virtual_driver
        panel.names = ("原配35k · 归档真实记录", "循迹50k · 归档真实记录")
        panel.scheme_names.setText(f"A：{panel.names[0]}\nB：{panel.names[1]}")
        panel.comparison = SavedComparison(records)
        lab.schemes.root.show()
        panel.root.show()
        panel.present()
        panel.review.show()
        review = panel.review

        def capture(name):
            lab.resize()
            for _ in range(6):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
            captures.append(name)

        assert review.slider["value"] == 240.
        assert "漏门" in review.details[0].getText() and "通过" in review.details[1].getText()
        capture("failure-gate")
        review.slider["value"] = 220.
        review.seek()
        capture("approaching-gate")
        review.select_gate(5)
        assert "未到达" in review.details[0].getText()
        capture("final-gate-no-extrapolation")
        before = tuple(record.snapshots for record in records)
        for value in range(321):
            review.slider["value"] = value
            review.seek()
        assert before == tuple(record.snapshots for record in records)
        lab.escape()
        assert review.root.isHidden() and not panel.root.isHidden()
        capture("returned-results")
        report = export_comparison(panel.comparison, output/"review-report", panel.names)
        summary = {"passed": True, "size": size, "archive_sdk": sdk, "captures": captures,
            "scope": "复用VIRTUAL-DRIVER-01实际完成步；本次物理驾驶未跑，321位置读取/末点不外推/退出已验",
            "source_archives": str(ROOT/"docs/evidence/VIRTUAL-DRIVER-01"/sdk), "report": str(report),
            "records_unchanged": True, "human_gate": "pending", "physics_rerun": False}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "archive_sdk": sdk, "physics_rerun": False}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-sdk", choices=("normal", "double"), default="normal")
    parser.add_argument("--size", type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.archive_sdk, args.size), ensure_ascii=False))
