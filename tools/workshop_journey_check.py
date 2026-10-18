"""实际初章菜单/历史成绩派生/同窗定位与重启；不伪造或重复道路圈。"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename

from application import CoastalDrive
from lab_runtime import runtime_fingerprint
from session import Phase


def finish(app, target):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == target and app._workspace_steps is None
    app.taskMgr.remove("lab-update" if target == "lab" else "drive-update")


def check(output, source, size, restore):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    app = CoastalDrive(smoke=True, output=output, lab_output=output/"reports", render_size=tuple(size))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.back_to_menu()
    app._shown_phase = None
    app.refresh_panel()
    captures = []

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png"))))
        captures.append({"name": name, "workspace": app.workspace, "updates_frozen": True})

    try:
        if restore:
            app.scheme_root = source
            app.open_workshop_journey()
            assert app.journey.data["steps"] == 2
            capture("restarted-journey")
        else:
            capture("main-menu")
            app.main_menu.buttons[7]["command"]()
            assert app.journey.data["steps"] == 0
            capture("new-journey")
            app.journey.hide()
            shutil.copytree(source, app.scheme_root)
            app.open_workshop_journey()
            assert app.journey.data["steps"] == 2
            assert app.journey.data["projects"][1]["steps"] == 2
            capture("saved-journey")
            identity = app.journey.data["projects"][1]["scheme_id"]
            window = app.win
            app.journey.buttons[1]["command"]()
            finish(app, "lab")
            assert app.win is window and app.lab.schemes.selected(1).id == identity
            capture("continued-scheme")
            app.lab.schemes.load_right()
            assert app.lab.workshop.topic == 1 and app.lab.workshop.result["medal"] == "金"
            app.lab.workshop.show()
            capture("continued-trial")
            app.lab.back_to_game()
            finish(app, "game")
            assert app.session.phase == Phase.MENU
            app.open_workshop_journey()
            assert app.journey.data["steps"] == 2
            capture("returned-journey")
            app.journey.buttons[2]["command"]()
            assert app.braking_menu and "170米" in app.panel_note.getText()
            capture("braking-rules")
        summary = {"passed": True, "runtime": runtime_fingerprint(), "size": size,
                   "restored": restore, "source_library": str(source), "scheme_root": str(app.scheme_root),
                   "steps": app.journey.data["steps"],
                   "projects": [{key: value for key, value in item.items() if key != "vehicle"}
                                for item in app.journey.data["projects"]],
                   "captures": captures, "human_gate": "pending",
                   "road_evidence": "复用DESIGN-SCHEMES-01实际圈原始记录；本工具只读派生进度/同窗导航，不重跑道路或生成奖牌"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"passed": True, "steps": summary["steps"], "restored": restore,
                "bits": summary["runtime"]["math_scalar_bits"]}
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--schemes", type=Path, required=True)
    parser.add_argument("--size", type=int, nargs=2, default=(1280, 720))
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.schemes.resolve(), args.size, args.restore)))
