"""实际安装曲线导入/拒绝与两种分辨率的公式显示；不启动物理世界。"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))

from panda3d.core import Filename
from suspension_motion_reference import document, rejected_document

from lab_application import VehicleLab


def check(output,height):
    output.mkdir(parents=True,exist_ok=False)
    app=VehicleLab(offscreen=True,output=output/"imports",render_size=(round(height*16/9),height))
    try:
        app.import_engineering(ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
        original=app.engineered_config
        old=asdict(original)
        bad=output/"rejected.json"
        bad.write_text(json.dumps(rejected_document(),ensure_ascii=False,indent=2),encoding="utf-8")
        app.import_suspension_bench(bad)
        assert app.engineered_config is original
        good=output/"input.json"
        good.write_text(json.dumps(document(),ensure_ascii=False,indent=2),encoding="utf-8")
        app.import_suspension_bench(good)
        assert app.engineered_config.suspension_installation_curves is not None
        expected={"suspension_installation_curves":3,"suspension_spring_rates":3,"suspension_spring_preloads":3,
                  "suspension_coil_enabled":3,"suspension_compression_damping":2,"suspension_extension_damping":2}
        for key,count in expected.items():
            app.parameter_help.show(key)
            assert len(app.parameter_help.formula_nodes)==count
            filename=app.parameter_help.formula_nodes[0].getTexture().getFilename().getBasename()
            assert filename==("installation_damping-0.png" if key.endswith("damping") else "suspension_installation_curves-0.png")
            assert "合成数据，非实测" in app.parameter_help.notes.getText()
            for _ in range(4):app.taskMgr.step();app.graphicsEngine.renderFrame()
            bottom=app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z
            assert bottom>-.73,(key,bottom)
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/(key+".png"))))
        del old["suspension_installation_curves"]
        app.record=SimpleNamespace(metadata={"vehicle_config":old,"summary":{"options":{"vehicle_id":"reference-rwd"}},
                                             "parameter_metadata":None})
        app.parameter_help.show("suspension_spring_rates")
        assert app.parameter_help.formula_nodes[0].getTexture().getFilename().getBasename()=="suspension_spring_rates-0.png"
        app.record=None
        app.parameter_help.hide()
        app.vehicle_menu.set(4)
        app.choose_vehicle("GR86")
        app.parameter_help.show("suspension_installation_curves")
        assert "车型账本未提供" in app.parameter_help.notes.getText()
        for _ in range(4):app.taskMgr.step();app.graphicsEngine.renderFrame()
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/"unprovided-oem.png")))
        assert app.run_state is None
        (output/"result.json").write_text(json.dumps({"height":height,"formula_fields":expected,
            "rejected_preserves_hardware":True,"legacy_formula_preserved":True,"missing_oem_not_measured":True,
            "physics_started":False,"input_method":"programmatic import/show; established hover/F1 route reused"},indent=2),encoding="utf-8")
    finally:
        app.close_game()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--height",type=int,choices=(720,1080),required=True)
    args=parser.parse_args()
    check(args.output.resolve(),args.height)
