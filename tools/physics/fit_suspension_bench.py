"""悬架部件台架JSON生成完整工程候选；拒绝不匹配的线性本构。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))

from lab_records import model_fingerprint
from suspension_bench import fit_bench
from vehicle_designs import vehicle_design
from vehicle_parameters import config_from_document, save_vehicle_config


def calibrate(path, output, base_document, vehicle_id="reference-rwd"):
    output.mkdir(parents=True, exist_ok=False)
    raw = Path(path).read_bytes()
    (output/"input.json").write_bytes(raw)
    (output/"base-vehicle.json").write_text(json.dumps(base_document, ensure_ascii=False, indent=2,
                                                    allow_nan=False), encoding="utf-8")
    base = config_from_document(base_document, vehicle_design(vehicle_id).config)
    try:
        config, report = fit_bench(json.loads(raw), base)
    except (ValueError, TypeError, KeyError, ArithmeticError) as error:
        report = {"passed": False, "error": str(error)}
    (output/"fit-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                   allow_nan=False), encoding="utf-8")
    (output/"source.json").write_text(json.dumps(model_fingerprint(), indent=2), encoding="utf-8")
    if report["passed"]:
        metadata = dict(base_document.get("metadata", {}))
        metadata["suspension_calibration"] = report
        metadata["basis"] = ("悬架合成数据算法验证，非实测；其余硬件沿用导入基准" if report["input"]["source_kind"] == "synthetic"
                             else "悬架指定台架条件下拟合/运动比换算；整车验证另记，其余硬件沿用基准")
        save_vehicle_config(output/"candidate-vehicle.json", config, metadata=metadata)
    return report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True, help="完整基准工程JSON；保留其质量/轮端/传动定义")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    passed = calibrate(args.input, args.output.resolve(), json.loads(args.base.read_text(encoding="utf-8")))
    print(json.dumps({"passed": passed, "output": str(args.output.resolve())}))
    raise SystemExit(0 if passed else 2)
