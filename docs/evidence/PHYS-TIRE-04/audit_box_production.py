"""只读核对最终碰撞矩阵的完整配置、输入和有限数值，保存原始差异。"""

import csv
import gzip
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def finite_count(records):
    count = 0
    for row in records:
        for key, value in row.items():
            try:
                number = float(value)
            except ValueError:
                continue
            if not math.isfinite(number):
                raise ValueError(f"非有限读数：tick={row['tick']} {key}={value}")
            count += 1
    return count


def audit():
    matrix = json.loads((HERE / "box-partition-collision-ab/summary.json").read_text(encoding="utf-8"))
    recontact = json.loads((HERE / "box-partition-recontact/summary.json").read_text(encoding="utf-8"))
    substeps = json.loads((HERE / "box-partition-tire-substeps/summary.json").read_text(encoding="utf-8"))
    if any(report["status"] != "completed" or not report["source_unchanged"] for report in (matrix, recontact, substeps)):
        raise ValueError("矩阵未完成或运行中源码改变")
    pairs = []
    numbers = 0
    csv_rows = 0
    for index in range(0, len(matrix["trials"]), 2):
        a, b = matrix["trials"][index:index+2]
        ca, cb = a["config"].copy(), b["config"].copy()
        if ca.pop("centered_collision_support") is not False or cb.pop("centered_collision_support") is not True or ca != cb:
            raise ValueError("A/B完整配置并非仅支撑表示不同")
        ra, rb = (rows(HERE / "box-partition-collision-ab" / trial["csv_gz"]) for trial in (a, b))
        commands = [key for key in ra[0] if key.startswith("command.")]
        if not commands:
            raise ValueError("缺少原始逐tick指令")
        differences = []
        different_cells = 0
        for old, new in zip(ra, rb, strict=True):
            if any(old[key] != new[key] for key in commands):
                raise ValueError("A/B指令不同")
            for key in old:
                if old[key] != new[key]:
                    different_cells += 1
                    if len(differences) < 8:
                        differences.append({"tick": old["tick"], "field": key, "A": old[key], "B": new[key]})
        numbers += finite_count(ra)+finite_count(rb)
        csv_rows += len(ra)+len(rb)
        metrics = ("path_distance_m", "peak_abs_unwrapped_heading_deg", "time_to_stop_s", "esc_active_seconds")
        pairs.append({"mode": a["mode"], "case": a["case"], "rows_each": len(ra),
                      "same_config_except_support": True, "same_every_tick_command": True,
                      "different_csv_cells": different_cells, "first_differences": differences,
                      "A": {key: a[key] for key in metrics}, "B": {key: b[key] for key in metrics}})
    for trial in recontact["trials"]:
        records = rows(HERE / "box-partition-recontact" / trial["csv_gz"])
        numbers += finite_count(records)
        csv_rows += len(records)
    for trial in substeps["trials"]:
        for steps in ("2", "8"):
            records = rows(HERE / "box-partition-tire-substeps" / trial[steps]["csv_gz"])
            numbers += finite_count(records)
            csv_rows += len(records)
    report = {"status": "completed", "collision_trials": len(matrix["trials"]),
              "recontact_trials": len(recontact["trials"]), "csv_rows": csv_rows,
              "standard_substep_trials": len(substeps["trials"])*2,
              "finite_numeric_values": numbers, "pairs": pairs,
              "maximum_recorded_force_residual_n": max(t["maximum_force_residual_n"]
                  for t in matrix["trials"]+recontact["trials"]+
                  [pair[steps] for pair in substeps["trials"] for steps in ("2", "8")]),
              "scope": "all saved numeric values and every command; signed work retained, no substep-work inference from final-substep fields"}
    (HERE / "box-partition-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                          allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "pairs"}))


if __name__ == "__main__":
    audit()
