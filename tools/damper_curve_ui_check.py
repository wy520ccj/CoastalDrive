"""非线性减振器台架导入/拒绝及实际F1排版，旧记录不套用新公式。"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))

from damper_bench_reference import document
from panda3d.core import Filename

from lab_application import VehicleLab


def check(output,height):
    output.mkdir(parents=True,exist_ok=False)
    app=VehicleLab(offscreen=True,output=output/"imports",render_size=(round(height*16/9),height))
    try:
        app.import_engineering(ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
        old=app.engineered_config
        bad=output/"rejected.json"
        bad.write_text(json.dumps(document(bad_validation=True),ensure_ascii=False,indent=2),encoding="utf-8")
        app.import_suspension_bench(bad)
        assert app.engineered_config is old
        good=output/"input.json"
        good.write_text(json.dumps(document(),ensure_ascii=False,indent=2),encoding="utf-8")
        app.import_suspension_bench(good)
        assert app.engineered_config.suspension_damper_curves is not None
        for key in ("suspension_damper_curves","suspension_compression_damping","suspension_extension_damping"):
            app.parameter_help.show(key)
            assert len(app.parameter_help.formula_nodes)==3
            assert app.parameter_help.formula_nodes[0].getTexture().getFilename().getBasename()=="suspension_damper_curves-0.png"
            assert "合成数据，非实测" in app.parameter_help.notes.getText()
            assert "分段力速表生效" in app.parameter_help.notes.getText()
            for _ in range(4):app.taskMgr.step();app.graphicsEngine.renderFrame()
            bottom=app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z
            assert bottom>-.73,(key,bottom)
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/(key+".png"))))
        legacy=asdict(old)
        del legacy["suspension_damper_curves"]
        app.record=SimpleNamespace(metadata={"vehicle_config":legacy,"summary":{"options":{"vehicle_id":"reference-rwd"}},
                                             "parameter_metadata":None})
        app.parameter_help.show("suspension_compression_damping")
        assert app.parameter_help.formula_nodes[0].getTexture().getFilename().getBasename()=="suspension_compression_damping-0.png"
        app.record=None
        app.choose_vehicle("GR86")
        app.vehicle_menu.set(4)
        app.parameter_help.show("suspension_damper_curves")
        assert "车型账本未提供" in app.parameter_help.notes.getText()
        for _ in range(4):app.taskMgr.step();app.graphicsEngine.renderFrame()
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(output/"unprovided-oem.png")))
        assert app.run_state is None
        (output/"result.json").write_text(json.dumps({"height":height,"formula_fields":3,
            "rejected_preserves_hardware":True,"accepted_table_imported":True,"legacy_uses_legacy_equation":True,
            "source_missing_not_measured":True,"physics_started":False,"input_method":"programmatic import/show; established hover/F1 route reused"},indent=2),encoding="utf-8")
    finally:
        app.close_game()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--height",type=int,choices=(720,1080),required=True)
    args=parser.parse_args()
    check(args.output.resolve(),args.height)
