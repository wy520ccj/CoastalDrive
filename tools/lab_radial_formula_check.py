"""径向材料力/实际施力/虚功数学排版的两尺寸真实渲染；不启动物理世界。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from panda3d.core import Filename

from lab_application import VehicleLab


def check(output,height):
    output.mkdir(parents=True,exist_ok=False)
    app = VehicleLab(offscreen=True,render_size=(round(height*16/9),height))
    try:
        app.import_engineering(ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
        screenshots = []
        expected = {"tire_radial_stiffness":3,"tire_radial_damping":3,"unsprung_enabled":2,
                    "suspension_spring_rates":2,"suspension_compression_damping":2,"suspension_extension_damping":2}
        for key,count in expected.items():
            app.parameter_help.show(key)
            assert len(app.parameter_help.formula_nodes)==count
            for _ in range(4):
                app.taskMgr.step();app.graphicsEngine.renderFrame()
            assert app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z>-.73
            name=key+".png"
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/name)))
            screenshots.append(name)
        assert app.run_state is None
        (output/"result.json").write_text(json.dumps({"height":height,"screenshots":screenshots,
            "formula_lines_per_field":expected,"physics_world_started":False,"formula_bounds":True},indent=2),encoding="utf-8")
    finally:
        app.close_game()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--height",type=int,choices=(720,1080),required=True)
    args=parser.parse_args()
    check(args.output.resolve(),args.height)
