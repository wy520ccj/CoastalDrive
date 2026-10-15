"""拟合轮胎台架CSV并导出完整工程候选；验证不通过时只保留报告。"""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lab_records import model_fingerprint
from tire_calibration import fit_tire, load_bench, predict
from vehicle_designs import vehicle_design
from vehicle_parameters import save_vehicle_config


def calibrate(csv_path, conditions_path, output, vehicle_id):
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(csv_path, output/"input.csv")
    shutil.copyfile(conditions_path, output/"conditions.json")
    try:
        bench = load_bench(csv_path, conditions_path)
        config, report = fit_tire(bench, vehicle_design(vehicle_id).config)
    except (ValueError, ArithmeticError) as error:
        (output/"fit-report.json").write_text(json.dumps({"passed": False, "error": str(error)},
                                                      ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(error))
        return False
    report["definition_fingerprint"] = model_fingerprint()
    report["base_vehicle"] = vehicle_id
    (output/"fit-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                   allow_nan=False), encoding="utf-8")
    with (output/"predictions.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*bench.rows[0], "predicted_fx_N", "predicted_fy_N"])
        writer.writeheader()
        for row, force in zip(bench.rows, predict(bench.rows, config), strict=True):
            writer.writerow({**row, "predicted_fx_N": force[0], "predicted_fy_N": force[1]})
    if report["passed"]:
        metadata = {"tire_calibration": report,
                    "basis": "合成部件算法验证，非实测标定" if bench.conditions["source_kind"] == "synthetic"
                             else "指定台架条件下的数据拟合；整车验证另行记录"}
        save_vehicle_config(output/"candidate-vehicle.json", config, metadata=metadata)
    print(json.dumps({"passed": report["passed"], "rank": report["rank"],
                      "condition_number": report["condition_number"], "parameters": report["parameters"]}))
    return report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--conditions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vehicle", default="reference-rwd")
    args = parser.parse_args()
    passed = calibrate(args.csv.resolve(), args.conditions.resolve(), args.output.resolve(), args.vehicle)
    raise SystemExit(0 if passed else 2)
