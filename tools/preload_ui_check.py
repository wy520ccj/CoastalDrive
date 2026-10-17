"""安装预载F1真实排版与当前/旧记录公式选择；不启动物理世界。"""

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
from suspension_preload_reference import document

from lab_application import VehicleLab


def check(output,height):
    output.mkdir(parents=True,exist_ok=False)
    app=VehicleLab(offscreen=True,output=output/"imports",render_size=(round(height*16/9),height))
    try:
        app.import_engineering(ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
        old_config=asdict(app.engineered_config)
        path=output/"input.json"
        path.write_text(json.dumps(document(),ensure_ascii=False,indent=2),encoding="utf-8")
        app.import_suspension_bench(path)
        assert app.engineered_config.suspension_coil_enabled
        assert app.engineered_config.suspension_spring_preloads[0]>900.
        for key in ("suspension_spring_preloads","suspension_coil_enabled","suspension_spring_rates"):
            app.parameter_help.show(key)
            assert len(app.parameter_help.formula_nodes)==3
            texture=app.parameter_help.formula_nodes[0].getTexture().getFilename().getBasename()
            assert texture=="suspension_spring_preloads-0.png",texture
            assert "合成数据，非实测" in app.parameter_help.notes.getText()
            for _ in range(4):app.engine.taskMgr.step();app.engine.graphicsEngine.renderFrame()
            bottom=app.parameter_help.notes.getTightBounds(app.parameter_help.root)[0].z
            assert bottom>-.73,(key,bottom)
            assert app.engine.win.saveScreenshot(Filename.fromOsSpecific(str(output/(key+".png"))))
        # 已保存旧记录的配置优先；不能用待运行新硬件给旧结果换公式。
        for key in ("suspension_coil_enabled","suspension_spring_preloads"):
            del old_config[key]
        app.record=SimpleNamespace(metadata={"vehicle_config":old_config,
            "summary":{"options":{"vehicle_id":"reference-rwd"}},"parameter_metadata":None})
        app.parameter_help.show("suspension_spring_rates")
        assert app.parameter_help.formula_nodes[0].getTexture().getFilename().getBasename()=="suspension_spring_rates-0.png"
        app.record=None
        app.parameter_help.hide()
        app.vehicle_menu.set(len(app.vehicle_menu["items"])-1)
        app.choose_vehicle("GR86")
        app.parameter_help.show("suspension_spring_preloads")
        assert "车型账本未提供" in app.parameter_help.notes.getText()
        for _ in range(4):app.engine.taskMgr.step();app.engine.graphicsEngine.renderFrame()
        assert app.engine.win.saveScreenshot(Filename.fromOsSpecific(str(output/"gr86-unprovided.png")))
        assert app.run_state is None
        (output/"result.json").write_text(json.dumps({"height":height,"installed_formula_fields":3,
            "saved_legacy_uses_legacy_formula":True,"missing_oem_data_not_claimed_measured":True,
            "source_kind":"synthetic","physics_started":False,"input_method":"programmatic import/show; hover/F1 route unchanged"},indent=2),encoding="utf-8")
    finally:
        app.close_game()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--height",type=int,choices=(720,1080),required=True)
    args=parser.parse_args()
    check(args.output.resolve(),args.height)
