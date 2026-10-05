"""导出当前四份工程硬件，供既有标准试验与无窗口入口直接加载。"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from physics.export_reference import BRAKE_FIELDS, STABILITY_FIELDS, TRACTION_FIELDS, VEHICLE_FIELDS

from vehicle_designs import DESIGN_VEHICLES
from vehicle_parameters import save_vehicle_config


def export_designs(output):
    output.mkdir(parents=True, exist_ok=False)
    source = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
        "src/vehicle_config.py", "src/driving_modes.py", "src/vehicle_designs.py",
        "src/vehicle_parameters.py", "assets/game/vehicles/classic_coupe_v1.glb")}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for design in DESIGN_VEHICLES:
        metadata = {
            "design_id": design.id, "name": design.name, "basis": design.basis,
            "kind": "generic_design", "git_head_at_export": head, "source_sha256": source,
            "vehicle_fields": {name: {"unit": unit, "definition": definition}
                               for name, (unit, definition) in VEHICLE_FIELDS.items()},
            "nested_field_metadata": {
                group: {name: {"unit": unit, "definition": definition}
                        for name, (unit, definition) in fields.items()}
                for group, fields in (("braking", BRAKE_FIELDS), ("traction", TRACTION_FIELDS),
                                      ("stability", STABILITY_FIELDS))},
            "geometry_source": "2026-10-06实读既有classic_coupe_v1.glb车身米制外廓",
            "inertia_source": "沿用reference-v28显式设计惯量，非实车测量；不根据显示网格推断",
            "layout_source": "三个参考车仅改变前轴驱动份额；共用纵置轴系与其余硬件",
            "input_mode": "游戏/仿真输入辅助独立；选择同一文件不改变硬件",
        }
        save_vehicle_config(output/(design.id+".json"), design.config, metadata=metadata)
    (output/"manifest.json").write_text(json.dumps(
        {"designs": [d.id for d in DESIGN_VEHICLES], "source_sha256": source},
        ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    export_designs(parser.parse_args().output)
