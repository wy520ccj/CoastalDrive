"""只渲染初章新增的进阶入口，不执行课题。"""
import argparse
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root/"src"))
from panda3d.core import Filename
from application import CoastalDrive
from lab_runtime import runtime_fingerprint

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--size", type=int, nargs=2, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
app = CoastalDrive(smoke=True, output=args.output, render_size=tuple(args.size))
app.taskMgr.remove("finish-smoke")
app.taskMgr.remove("drive-update")
try:
    app.back_to_menu()
    app._shown_phase = None
    app.refresh_panel()
    app.main_menu.resize(app.getAspectRatio())
    app.open_workshop_journey()
    before = app.session.current
    for _ in range(6):
        app.taskMgr.step()
    app.graphicsEngine.syncFrame()
    assert before == app.session.current
    assert app.win.getScreenshot().write(Filename.fromOsSpecific(str((args.output/"chapter.png").resolve())))
    (args.output/"summary.json").write_text(json.dumps({"passed": True, "scope": "layout_only_no_course_drive",
        "size": args.size, "runtime": runtime_fingerprint(), "human_gate": "pending"}), encoding="utf-8")
finally:
    app.close_game()
