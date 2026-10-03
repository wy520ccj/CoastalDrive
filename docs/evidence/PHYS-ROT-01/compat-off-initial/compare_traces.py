"""逐字段比较冻结A与当前B，旧快照字段完整纳入。"""
import json
import sys
from collections import Counter
from pathlib import Path


def leaves(value, path=""):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            result.update(leaves(child, f"{path}.{key}" if path else key))
        return result
    if isinstance(value, list):
        result = {}
        for index, child in enumerate(value):
            result.update(leaves(child, f"{path}.{index}"))
        return result
    return {path: value}


def main():
    output = Path(sys.argv[1])
    old = json.loads((output / "frozen-a.json").read_text(encoding="utf-8"))
    new = json.loads((output / "current-b.json").read_text(encoding="utf-8"))
    old_config, new_config = leaves(old["car_config"]), leaves(new["car_config"])
    config_missing = sorted(set(old_config) - set(new_config))
    config_changed = [key for key in old_config.keys() & new_config.keys()
                      if old_config[key] != new_config[key]]
    report = {
        "comparison": "exact equality for every A snapshot leaf at every tick; B-only leaves ignored",
        "a_snapshot_fields": sorted(leaves(old["cases"]["acceleration"][0])),
        "b_snapshot_fields": sorted(leaves(new["cases"]["acceleration"][0])),
        "b_only_snapshot_fields": sorted(set(leaves(new["cases"]["acceleration"][0])) -
                                           set(leaves(old["cases"]["acceleration"][0]))),
        "a_only_snapshot_fields": sorted(set(leaves(old["cases"]["acceleration"][0])) -
                                           set(leaves(new["cases"]["acceleration"][0]))),
        "common_car_config_missing_in_b": config_missing,
        "common_car_config_changed": config_changed,
        "cases": {},
    }
    for case in old["cases"]:
        counts = Counter()
        first = None
        missing = []
        for tick, (a_row, b_row) in enumerate(zip(old["cases"][case], new["cases"][case])):
            a_fields, b_fields = leaves(a_row), leaves(b_row)
            for field in a_fields:
                if field not in b_fields:
                    missing.append({"tick": tick, "field": field})
                    continue
                if a_fields[field] != b_fields[field]:
                    counts[field] += 1
                    if first is None:
                        first = {"tick": tick, "field": field,
                                 "a": a_fields[field], "b": b_fields[field]}
        report["cases"][case] = {
            "a_ticks_including_initial": len(old["cases"][case]),
            "b_ticks_including_initial": len(new["cases"][case]),
            "mismatch_count_by_field": dict(sorted(counts.items())),
            "total_mismatch_cells": sum(counts.values()),
            "first_mismatch": first,
            "missing_old_fields": missing[:10],
        }
    report["all_old_fields_present"] = not any(
        value["missing_old_fields"] for value in report["cases"].values()
    ) and not report["a_only_snapshot_fields"]
    report["all_common_config_equal"] = not config_missing and not config_changed
    report["all_old_snapshot_values_exactly_equal"] = all(
        value["total_mismatch_cells"] == 0 for value in report["cases"].values()
    ) and report["all_old_fields_present"] and report["all_common_config_equal"]
    (output / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for name, value in report["cases"].items():
        print(name, "mismatch_cells=", value["total_mismatch_cells"],
              "first=", value["first_mismatch"])
    print("all_old_fields_present=", report["all_old_fields_present"])
    print("all_common_config_equal=", report["all_common_config_equal"])
    print("all_old_snapshot_values_exactly_equal=", report["all_old_snapshot_values_exactly_equal"])


if __name__ == "__main__":
    main()
