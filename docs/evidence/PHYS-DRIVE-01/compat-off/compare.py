"""逐tick比较全部A旧字段，并统计确实比较的单元总数。"""
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
    directory = Path(sys.argv[1])
    a = json.loads((directory / "frozen-a.json").read_text(encoding="utf-8"))
    b = json.loads((directory / "current-b-explicit-off.json").read_text(encoding="utf-8"))
    a_config, b_config = leaves(a["car_config"]), leaves(b["car_config"])
    config_missing = sorted(set(a_config) - set(b_config))
    config_changed = sorted(key for key in a_config.keys() & b_config.keys()
                            if a_config[key] != b_config[key])
    report = {
        "comparison": "exact value equality on every A snapshot leaf at every tick; B-only leaves allowed",
        "a_snapshot_leaf_fields": len(leaves(a["cases"]["acceleration"][0])),
        "b_snapshot_leaf_fields": len(leaves(b["cases"]["acceleration"][0])),
        "b_only_snapshot_leaf_fields": sorted(
            set(leaves(b["cases"]["acceleration"][0])) -
            set(leaves(a["cases"]["acceleration"][0]))
        ),
        "a_only_snapshot_leaf_fields": sorted(
            set(leaves(a["cases"]["acceleration"][0])) -
            set(leaves(b["cases"]["acceleration"][0]))
        ),
        "a_config_fields_missing_in_b": config_missing,
        "common_config_fields_changed": config_changed,
        "b_explicit_finite_drivetrain": b["finite_drivetrain"],
        "cases": {},
    }
    for case, a_rows in a["cases"].items():
        b_rows = b["cases"][case]
        compared = 0
        mismatches = Counter()
        missing = []
        first = None
        for tick, (a_row, b_row) in enumerate(zip(a_rows, b_rows)):
            a_values, b_values = leaves(a_row), leaves(b_row)
            for field, a_value in a_values.items():
                if field not in b_values:
                    missing.append({"tick": tick, "field": field})
                    continue
                compared += 1
                if a_value != b_values[field]:
                    mismatches[field] += 1
                    if first is None:
                        first = {"tick": tick, "field": field, "a": a_value, "b": b_values[field]}
        report["cases"][case] = {
            "a_snapshots": len(a_rows),
            "b_snapshots": len(b_rows),
            "compared_old_field_cells": compared,
            "mismatch_cells": sum(mismatches.values()),
            "mismatch_count_by_field": dict(sorted(mismatches.items())),
            "first_mismatch": first,
            "missing_old_fields": missing,
        }
    report["total_compared_old_field_cells"] = sum(
        case["compared_old_field_cells"] for case in report["cases"].values()
    )
    report["all_old_fields_present"] = not any(
        case["missing_old_fields"] for case in report["cases"].values()
    ) and not report["a_only_snapshot_leaf_fields"]
    report["all_common_config_equal"] = not config_missing and not config_changed
    report["all_old_field_values_exactly_equal"] = all(
        case["mismatch_cells"] == 0 for case in report["cases"].values()
    ) and report["all_old_fields_present"] and report["all_common_config_equal"]
    (directory / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for name, case in report["cases"].items():
        print(f"{name}: compared={case['compared_old_field_cells']}, mismatches={case['mismatch_cells']}, first={case['first_mismatch']}")
    print("total_compared_old_field_cells=", report["total_compared_old_field_cells"])
    print("all_old_fields_present=", report["all_old_fields_present"])
    print("all_common_config_equal=", report["all_common_config_equal"])
    print("all_old_field_values_exactly_equal=", report["all_old_field_values_exactly_equal"])


if __name__ == "__main__":
    main()
