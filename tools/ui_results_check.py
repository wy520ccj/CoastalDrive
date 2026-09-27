"""在真实窗口记录结算键盘焦点；使用完成态夹具，不冒充人工跑圈。"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panda3d.core import Filename

from application import CoastalDrive
from race import GameMode
from session import Phase


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    app = CoastalDrive(smoke=True, onscreen=True, output=args.output, render_size=(1920, 1080))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    records = []

    def press(key):
        app.messenger.send(key)
        app.messenger.send(key + "-up")

    def capture(name):
        app.taskMgr.step()
        app.update(SimpleNamespace(cont=None))
        for _ in range(4):
            app.graphicsEngine.renderFrame()
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output / f"{name}.png")))
        records.append({"image": f"{name}.png", "selection": app.panel_selection})

    try:
        app.start_game(mode=GameMode.TIME_TRIAL)
        app.session.phase = Phase.DRIVING
        app.refresh_panel()
        app.session.race.snapshot = replace(
            app.session.race.snapshot, finished=True, last_lap=87.123, best_lap=87.123,
        )
        app.session.tick()
        assert app.session.phase == Phase.RESULTS
        frozen = app.session.current
        press("arrow_right")
        assert app.panel_selection == 1
        capture("right-select-menu")
        press("arrow_right")
        assert app.panel_selection == 2
        capture("right-select-exit")
        press("arrow_left")
        assert app.panel_selection == 1
        assert app.session.current == frozen
        press("enter")
        assert app.session.phase == Phase.MENU
        assert not app.main_menu.root.isHidden()
        capture("enter-return-menu")
        (args.output / "report.json").write_text(json.dumps({
            "passed": True, "resolution": [1920, 1080], "onscreen": True,
            "input": "registered Panda3D messenger keyboard events",
            "fixture": "completed race snapshot through Session.tick; not a human lap",
            "captures": records,
        }, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
