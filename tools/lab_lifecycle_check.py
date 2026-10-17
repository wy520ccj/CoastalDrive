"""真实游戏/实验室往返，核对世界关闭和实验室控件释放。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from direct.gui.DirectGuiBase import DirectGuiWidget
from panda3d.core import Filename

from application import CoastalDrive
from lab_application import VehicleLab


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    rounds = []
    for index in range(2):
        game = CoastalDrive(smoke=True, output=output/f"game-{index}", track="test")
        game.taskMgr.remove("finish-smoke")
        world = game.session.simulation
        try:
            game.back_to_menu()
            game.taskMgr.step()
            game.graphicsEngine.renderFrame()
            if index == 0:
                game.win.saveScreenshot(Filename.fromOsSpecific(str(output/"main-menu-lab-entry.png")))
            game.main_menu.select(6)
            game.main_menu.activate()
            assert game.next_workspace == "lab"
        finally:
            game.close_game()
        assert world.closed
        assert not game.taskMgr.getTasksNamed("render-frame-pacing")
        assert not game.taskMgr.getTasksNamed("simplepbr update")
        gui_before = len(DirectGuiWidget.guiDict)
        lab = VehicleLab(offscreen=True, output=output/f"lab-{index}")
        try:
            lab.start_experiment()
            lab.toggle_pause()
            lab.single_step()
            lab.engine.taskMgr.step()
            lab_world = lab.run_state.experiment.simulation
            lab.back_to_game()
            assert lab.next_workspace == "game"
        finally:
            lab.close_game()
        assert lab_world.closed
        assert not lab.engine.taskMgr.getTasksNamed("lab-update")
        assert not lab.engine.taskMgr.getTasksNamed("simplepbr update")
        gui_after = len(DirectGuiWidget.guiDict)
        assert gui_after == gui_before
        rounds.append({"game_world_closed": world.closed, "lab_world_closed": lab_world.closed,
                       "gui_before_lab": gui_before, "gui_after_lab": gui_after})
    report = {"passed": True, "rounds": rounds, "human_acceptance": "pending"}
    (output/"summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve()), ensure_ascii=False))
