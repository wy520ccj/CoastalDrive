"""轮胎标定量经实际GUI进入物理与导出，并检查新增字段排版。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename

from lab_application import VehicleLab
from lab_records import load_record


def check(output, height):
    output.mkdir(parents=True, exist_ok=False)
    app = VehicleLab(offscreen=True, output=output / "records", render_size=(round(height * 16 / 9), height))
    try:
        app.entries["tire_load"].enterText("4100")
        app.entries["duration"].enterText("0.1")
        assert app.read_options().tire_reference_load == 4100.
        app.start_experiment()
        while not app.run_state.done:
            app.taskMgr.step()
        assert app.run_state.config.tire_reference_load == 4100.
        app.export()
        record = load_record(app.last_report.parent)
        assert record.metadata["vehicle_config"]["tire_reference_load"] == 4100.
        assert record.metadata["summary"]["options"]["tire_reference_load"] == 4100.
        app.toggle_advanced()
        app.taskMgr.step()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        path = output / "advanced-tire-reference.png"
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        (output / "result.json").write_text(json.dumps(
            {"height": height, "gui_value_N": 4100., "physical_value_N": 4100.,
             "exported_value_N": 4100., "samples": len(record.samples)}, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--height", type=int, choices=(720, 1080), required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.height)
