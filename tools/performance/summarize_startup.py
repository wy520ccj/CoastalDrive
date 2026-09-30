"""按中位数汇总并排序 PERF 启动时间线，避免从单次样本猜瓶颈。"""

import argparse
import json
import statistics
from pathlib import Path


def summarize(reports):
    def event_rows(key):
        timeline = reports[0][key]["timeline"] if key == "drive_transition" else reports[0]["timeline"]
        rows = []
        for item in timeline:
            if item["since_previous_s"] is None:
                continue
            name = item["event"]
            samples = []
            for report in reports:
                source = report[key]["timeline"] if key == "drive_transition" else report["timeline"]
                samples.append(next(row["since_previous_s"] for row in source
                                    if row["event"] == name))
            rows.append({"stage": name, "median_s": statistics.median(samples)})
        return sorted(rows, key=lambda row: row["median_s"], reverse=True)

    detail = {}
    if all("scene_stage_seconds" in report for report in reports):
        for phase in ("menu", "drive"):
            detail[phase] = sorted(
                ({"stage": name, "median_s": statistics.median(
                    report["scene_stage_seconds"][phase][name] for report in reports)}
                 for name in reports[0]["scene_stage_seconds"][phase]),
                key=lambda row: row["median_s"], reverse=True,
            )
    return {
        "runs": len(reports),
        "menu_usable_median_s": statistics.median(
            report["time_to_menu_usable_s"] for report in reports),
        "drive_transition_median_s": statistics.median(
            report["drive_transition_s"] for report in reports),
        "startup_stages": event_rows("timeline"),
        "drive_stages": event_rows("drive_transition"),
        "scene_substages": detail,
        "note": "Adjacent mark intervals; scene substages are nested and must not be summed with their parent.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.reports]
    result = summarize(reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for title, rows in (("Menu startup", result["startup_stages"]),
                        ("Drive transition", result["drive_stages"]),
                        ("Scene menu detail", result["scene_substages"].get("menu", [])),
                        ("Scene drive detail", result["scene_substages"].get("drive", []))):
        print(title)
        for row in rows:
            print(f"  {row['stage']:<31} {row['median_s']:>7.3f} s")
    print(f"Menu usable: {result['menu_usable_median_s']:.3f} s")
    print(f"Drive visible: +{result['drive_transition_median_s']:.3f} s")


if __name__ == "__main__":
    main()
