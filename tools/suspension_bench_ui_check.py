"""通过真实工作台导入部件数据并检查公式/来源，物理和实际输入验收分开记录。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
sys.path.insert(0, str(ROOT/"tests"))

from panda3d.core import Filename
from suspension_bench_reference import write_bench

from lab_application import VehicleLab


def check(output, height):
    output.mkdir(parents=True, exist_ok=False)
    app = VehicleLab(offscreen=True, output=output/"imports", render_size=(round(height*16/9), height))
    try:
        app.import_engineering(ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
        old = app.engineered_config
        app.import_suspension_bench(write_bench(output/"rejected.json", bad_validation=True))
        assert app.engineered_config is old
        app.import_suspension_bench(write_bench(output/"accepted.json"))
        assert app.engineered_config is not old and app.engineered_config.unsprung_enabled
        for key in ("suspension_spring_rates", "suspension_compression_damping", "suspension_extension_damping"):
            app.parameter_help.show(key)
            assert len(app.parameter_help.formula_nodes) == 3
            assert "合成数据，非实测" in app.parameter_help.notes.getText()
            assert "部件系数" in app.parameter_help.notes.getText()
            for _ in range(4):
                app.taskMgr.step(); app.graphicsEngine.renderFrame()
            bottom = app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z
            assert bottom > -.73, (key, bottom)
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/(key+".png"))))
        app.parameter_help.hide()
        app.advanced_panel.show()
        for _ in range(4):
            app.taskMgr.step(); app.graphicsEngine.renderFrame()
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/"advanced.png")))
        assert app.run_state is None
        (output/"result.json").write_text(json.dumps({"height": height, "rejected_preserves_base": True,
            "accepted_config_applied": True, "formulas_per_field": 3, "physics_world_started": False,
            "input_kind": "programmatic import/show; existing hover/F1 route reused"}, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--height", type=int, choices=(720, 1080), required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.height)
