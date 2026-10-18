"""实际F1来源展示与纯元数据修改核对；不运行或标定车辆。"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename

from lab_application import VehicleLab
from lab_runtime import runtime_fingerprint
from vehicle_designs import GR86_DESIGN, GR86_PROFILE_PATH
from vehicle_workspace import WorkspaceVehicle


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def check(output, before):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    previous = json.loads(before.read_text(encoding="utf-8"))
    document = json.loads(GR86_PROFILE_PATH.read_text(encoding="utf-8"))
    config = json.loads(json.dumps(asdict(GR86_DESIGN)))
    require(document["parameters"] == previous["parameters"], "参数分区发生变化")
    require(config == previous["config"], "实际导入硬件发生变化")
    fields = document["metadata"]["vehicle_fields"]
    require(set(fields) == set(config), "来源表未完整覆盖")
    require(all(fields[key]["value"] == value for key, value in config.items()), "来源值与配置不同")
    app = VehicleLab(offscreen=True, output=output/"records", workspace_vehicle=WorkspaceVehicle(
        "gr86-2022-premium-6mt", GR86_DESIGN))
    app.engine.taskMgr.remove("lab-update")
    cases = {}

    def capture(key, expected, *, name=None):
        name = key if name is None else name
        app.parameter_help.show(key)
        basis, current = app.parameter_help.context(key)
        require(expected in basis, "来源说明缺失："+key)
        app.parameter_help.content_scroll.verticalScroll["value"] = 1
        for _ in range(3):
            app.engine.taskMgr.step()
        app.engine.graphicsEngine.syncFrame()
        require(app.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+".png")))), "截图失败")
        cases[name] = {"basis": basis, "current": current}

    try:
        capture("unsprung_masses", "不是GR86簧下质量实测")
        capture("tire_contact_half_length", "无该车型轮胎Mz台架数据")
        capture("suspension_damper_curves", "不表示零阻尼")
        capture("wheelbase", "车型账本分类：原厂")
        app.engineered_config = replace(GR86_DESIGN, unsprung_masses=(41.,)*4)
        capture("unsprung_masses", "不沿用原来源分类", name="unsprung_masses_override")
        require("不是GR86簧下质量实测" not in cases["unsprung_masses_override"]["basis"], "覆盖值错误沿用原始来源")
        summary = {"passed": True, "precision_bits": runtime_fingerprint()["math_scalar_bits"],
                   "parameter_sha256": digest(document["parameters"]), "config_sha256": digest(config),
                   "parameters_unchanged": True, "config_unchanged": True, "fields": len(fields),
                   "added_fields": previous["missing"], "ui_cases": cases, "physics_run": "not_run"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.output.resolve(), args.before.resolve())
    print(json.dumps({key: result[key] for key in ("passed", "precision_bits", "fields", "parameters_unchanged",
                                                  "config_unchanged")}, ensure_ascii=False))
