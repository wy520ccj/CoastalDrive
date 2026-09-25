"""Short garage flow check and renders of the ten bundled appearances."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panda3d.core import ClockObject, Filename

from application import CoastalDrive
from controls import ConstantController
from race import GameMode
from session import Phase
from settings import AppearanceStore
from simulation import Control
from skins import MODELS, SKINS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("logs/phase6a"))
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    AppearanceStore(output / "test-appearance.json").save("sports", "orange")
    app = CoastalDrive(smoke=True, output=output)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.clock.setMode(ClockObject.MNonRealTime)
    app.clock.setDt(1 / 60)
    task = type("Frame", (), {"cont": None})()

    def render(name):
        for _ in range(3):
            app.taskMgr.step()
            app.update(task)
            app.graphicsEngine.renderFrame()
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output / f"{name}.png")))

    try:
        app.session.menu()
        before = app.session.simulation.snapshot()
        app.choose_garage()
        for model in MODELS:
            assert app.garage_model_id == model.id
            for skin in SKINS:
                assert SKINS[app.garage_skin_index].id == skin.id
                render(f"{model.id}-{skin.id}")
                app.cycle_garage_skin(1)
            app.cycle_garage_model()
        assert app.session.simulation.snapshot() == before
        app.cycle_garage_model()
        app.cycle_garage_skin(1)
        app.key_down("enter")
        app.key_down("enter")  # Key repeat must not start a race after saving.
        app.key_up("enter")
        assert app.session.phase == Phase.MENU
        assert app.garage is None and not app.scene.render.isHidden()
        saved = AppearanceStore(output / "test-appearance.json")
        assert (saved.model_id, saved.skin_id) == ("sedan", "blue")
        app.choose_garage()
        app.cycle_garage_model()
        app.cycle_garage_skin(1)
        app.key_down("escape")
        app.key_up("escape")
        assert app.vehicle_model_id == "sedan" and SKINS[app.skin_index].id == "blue"
        assert AppearanceStore(output / "test-appearance.json").skin_id == "blue"
        assert app.session.simulation.snapshot() == before

        app.choose_garage()
        path = app.appearance.path
        app.appearance.path = output  # Replacing a directory must fail visibly.
        app.apply_garage()
        assert app.garage is not None and app.appearance.notice
        render("save-error")
        app.appearance.path = path
        app.cancel_garage()

        app.start_game(mode=GameMode.FREE_DRIVE, track="endless")
        for _ in range(360):
            app.session.tick()
        app.session.set_controller(ConstantController(Control(throttle=0.5)))
        start = app.session.current.player.position
        for _ in range(240):
            app.session.tick()
        render("sedan-driving")
        assert app.session.current.player.position[1] > start[1] + 0.5
        assert app.scene.player.getName() == "sedan"
        assert app.vehicle_model_id == "sedan" and app.skin_index == 1
        assert app.render.findAllMatches("**/garage-preview").getNumPaths() == 0
        (output / "garage-check.json").write_text(json.dumps({
            "passed": True, "appearances": 10,
            "checks": ["frozen_simulation", "apply", "cancel", "key_repeat", "save_error", "driving"],
        }, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
