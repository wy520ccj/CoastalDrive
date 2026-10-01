"""与模式接线前固定正常游戏样本逐tick对照。"""

import argparse
import gzip
import hashlib
import json
import math
import struct
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "evidence" / "PHYS-MODES-01" / "normal-baseline"
sys.path.insert(0, str(ROOT / "src"))

from driver_assist import GAME_INPUT
from simulation import FIXED_DT, Control, Simulation
from vehicle_brakes import BrakeConfig
from vehicle_config import CAR

GEOMETRY_FIELDS = {
    "position", "orientation", "contact_point", "contact_normal", "suspension_length",
    "compression",
}
IGNORED_KEYS = {"contact_epoch", "source_id", "source_ids", "sources"}
UNUSED_OLD_CONFIG_FIELDS = {"road_grip", "grass_grip"}
GEOMETRY_MIN_TOLERANCE = 5e-7
MAX_MISMATCH_DETAILS = 30
CASES = {
    "test-straight": ("test", "straight", 0),
    "coastal-straight": ("coastal", "straight", 2),
    "endless-hills": ("endless", "hills", 2),
}


def _json_value(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _float32_ulp(value):
    rounded = abs(struct.unpack(">f", struct.pack(">f", abs(value)))[0])
    bits = struct.unpack(">I", struct.pack(">f", rounded))[0]
    if bits >= 0x7F7FFFFF:
        return math.inf
    following = struct.unpack(">f", struct.pack(">I", bits + 1))[0]
    return following - rounded


def _geometry_tolerance(left, right):
    return max(
        GEOMETRY_MIN_TOLERANCE,
        2 * max(_float32_ulp(left), _float32_ulp(right)),
    )


def compare_record(baseline, current):
    stats = {
        "compared_values": 0,
        "geometry_values": 0,
        "max_geometry_abs_delta": 0.0,
        "max_geometry_path": None,
        "max_geometry_tolerance": 0.0,
        "max_other_numeric_abs_delta": 0.0,
        "max_other_numeric_path": None,
        "mismatch_count": 0,
        "mismatches": [],
        "extra_current_paths": [],
    }

    def mismatch(path, old, new, reason):
        stats["mismatch_count"] += 1
        if len(stats["mismatches"]) < MAX_MISMATCH_DETAILS:
            stats["mismatches"].append({
                "path": ".".join(str(part) for part in path),
                "baseline": old,
                "current": new,
                "reason": reason,
            })

    def ignored(path):
        return path[-1:] and path[-1] in IGNORED_KEYS or path == ("input", "direction")

    def visit(old, new, path):
        if isinstance(old, dict):
            if not isinstance(new, dict):
                mismatch(path, type(old).__name__, type(new).__name__, "type")
                return
            for key in old:
                child_path = path + (key,)
                if ignored(child_path):
                    continue
                if key not in new:
                    mismatch(child_path, old[key], None, "missing_current_field")
                else:
                    visit(old[key], new[key], child_path)
            for key in new.keys() - old.keys():
                child_path = path + (key,)
                if not ignored(child_path):
                    stats["extra_current_paths"].append(".".join(map(str, child_path)))
            return
        if isinstance(old, list):
            if not isinstance(new, list):
                mismatch(path, type(old).__name__, type(new).__name__, "type")
                return
            if len(old) != len(new):
                mismatch(path, len(old), len(new), "length")
                return
            for index, (old_item, new_item) in enumerate(zip(old, new)):
                visit(old_item, new_item, path + (index,))
            return
        if isinstance(old, bool) or isinstance(new, bool):
            stats["compared_values"] += 1
            if old != new:
                mismatch(path, old, new, "value")
            return
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            stats["compared_values"] += 1
            delta = abs(float(old) - float(new))
            if any(part in GEOMETRY_FIELDS for part in path if isinstance(part, str)):
                stats["geometry_values"] += 1
                tolerance = _geometry_tolerance(float(old), float(new))
                stats["max_geometry_tolerance"] = max(
                    stats["max_geometry_tolerance"], tolerance
                )
                if delta > stats["max_geometry_abs_delta"]:
                    stats["max_geometry_abs_delta"] = delta
                    stats["max_geometry_path"] = ".".join(map(str, path))
                if delta > tolerance:
                    mismatch(path, old, new, f"geometry_delta>{tolerance:.9g}")
            else:
                if delta > stats["max_other_numeric_abs_delta"]:
                    stats["max_other_numeric_abs_delta"] = delta
                    stats["max_other_numeric_path"] = ".".join(map(str, path))
                if old != new:
                    mismatch(path, old, new, "exact_numeric_difference")
            return
        stats["compared_values"] += 1
        if old != new:
            mismatch(path, old, new, "value")

    visit(baseline, current, ())
    return stats


def _config_comparison(old_config, config=CAR):
    current_config = {**asdict(config), **asdict(GAME_INPUT)}
    old_normalized = _json_value(old_config)
    current_normalized = _json_value(current_config)
    differences = []
    for key, old_value in old_normalized.items():
        if key in UNUSED_OLD_CONFIG_FIELDS:
            continue
        if key not in current_normalized:
            differences.append({"field": key, "baseline": old_value, "current": None})
        elif old_value != current_normalized[key]:
            differences.append({
                "field": key,
                "baseline": old_value,
                "current": current_normalized[key],
            })
    return current_config, differences


def _source_hashes():
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"):
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "src").rglob("*.py"))
    }


def _record(snapshot, control):
    return _json_value({
        "tick": snapshot.tick,
        "time": snapshot.time,
        "input": asdict(control),
        "player": asdict(snapshot.player),
        "traffic": [asdict(car) for car in snapshot.traffic],
        "origin_y": snapshot.origin_y,
        "collisions": snapshot.collisions,
        "events": snapshot.events,
    })


def run_case(case, old_metadata, output, config=CAR):
    track, road_shape, traffic_count = CASES[case]
    case_metadata = next(item for item in old_metadata["cases"] if item["file"] == f"{case}.jsonl.gz")
    baseline_path = BASELINE / case_metadata["file"]
    baseline_hash = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    if baseline_hash != case_metadata["sha256"]:
        raise ValueError(f"baseline SHA-256 mismatch: {case_metadata['file']}")

    simulation = Simulation(
        case_metadata["seed"],
        track=track,
        road_shape=road_shape,
        traffic_count=traffic_count,
        config=config,
        input_config=GAME_INPUT,
        traffic_input_config=GAME_INPUT,
    )
    candidate_path = output / f"current-{case}.jsonl.gz"
    aggregate = {
        "case": case,
        "ticks": 0,
        "compared_values": 0,
        "geometry_values": 0,
        "max_geometry_abs_delta": 0.0,
        "max_geometry_path": None,
        "max_geometry_tick": None,
        "max_geometry_tolerance": 0.0,
        "max_other_numeric_abs_delta": 0.0,
        "max_other_numeric_path": None,
        "mismatch_count": 0,
        "mismatches": [],
        "extra_current_paths": set(),
    }
    try:
        with gzip.open(baseline_path, "rt", encoding="utf-8") as old_stream, gzip.open(
            candidate_path, "wt", encoding="utf-8"
        ) as new_stream:
            for expected_tick, line in enumerate(old_stream, 1):
                old_record = json.loads(line)
                old_input = old_record["input"]
                control = Control(
                    steering=old_input["steering"],
                    throttle=old_input["throttle"],
                    brake=old_input["brake"],
                    direction=old_input.get("direction", 1),
                )
                simulation.step(control)
                current_record = _record(simulation.snapshot(), control)
                new_stream.write(json.dumps(
                    current_record, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                ) + "\n")
                if old_record["tick"] != expected_tick or current_record["tick"] != expected_tick:
                    raise ValueError(f"nonsequential tick in {case} at {expected_tick}")
                comparison = compare_record(old_record, current_record)
                aggregate["ticks"] += 1
                aggregate["compared_values"] += comparison["compared_values"]
                aggregate["geometry_values"] += comparison["geometry_values"]
                aggregate["mismatch_count"] += comparison["mismatch_count"]
                aggregate["extra_current_paths"].update(comparison["extra_current_paths"])
                aggregate["max_geometry_tolerance"] = max(
                    aggregate["max_geometry_tolerance"], comparison["max_geometry_tolerance"]
                )
                aggregate["max_other_numeric_abs_delta"] = max(
                    aggregate["max_other_numeric_abs_delta"],
                    comparison["max_other_numeric_abs_delta"],
                )
                if comparison["max_geometry_abs_delta"] > aggregate["max_geometry_abs_delta"]:
                    aggregate["max_geometry_abs_delta"] = comparison["max_geometry_abs_delta"]
                    aggregate["max_geometry_path"] = comparison["max_geometry_path"]
                    aggregate["max_geometry_tick"] = expected_tick
                if comparison["max_other_numeric_abs_delta"] == aggregate["max_other_numeric_abs_delta"]:
                    aggregate["max_other_numeric_path"] = comparison["max_other_numeric_path"]
                if len(aggregate["mismatches"]) < MAX_MISMATCH_DETAILS:
                    for detail in comparison["mismatches"]:
                        if len(aggregate["mismatches"]) == MAX_MISMATCH_DETAILS:
                            break
                        aggregate["mismatches"].append({"tick": expected_tick, **detail})
            if aggregate["ticks"] != old_metadata["ticks"]:
                raise ValueError(f"baseline tick count mismatch in {case}")
    finally:
        simulation.close()

    aggregate["extra_current_paths"] = sorted(aggregate["extra_current_paths"])
    aggregate["passed"] = aggregate["mismatch_count"] == 0
    aggregate["candidate_file"] = candidate_path.name
    aggregate["baseline_sha256"] = baseline_hash
    aggregate["candidate_sha256"] = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    return aggregate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="必须是尚不存在的新证据目录")
    parser.add_argument("--case", choices=tuple(CASES), action="append", help="默认运行全部旧基线工况")
    parser.add_argument("--legacy-actuator", action="store_true", help="显式使用旧零迟滞/无ABS制动器，检验接口迁移")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        parser.error(f"输出路径必须尚不存在：{output}")
    if not math.isclose(FIXED_DT, 1 / 120, rel_tol=0, abs_tol=1e-15):
        raise RuntimeError(f"unexpected simulation step: {FIXED_DT}")

    old_metadata = json.loads((BASELINE / "metadata.json").read_text(encoding="utf-8"))
    if old_metadata["fixed_dt"] != FIXED_DT:
        raise RuntimeError("baseline and current fixed step differ")
    config = replace(CAR, braking=BrakeConfig(response_time=0, abs_enabled=False),
                     traction=replace(CAR.traction, tcs_enabled=False),
                     stability=replace(CAR.stability, esc_enabled=False),
                     tire_peak_load_exponent=1, longitudinal_load_exponent=1,
                     lateral_load_exponent=1, tire_compliance=False) if args.legacy_actuator else CAR
    current_config, config_differences = _config_comparison(old_metadata["config"], config)
    output.mkdir(parents=True)
    results = [run_case(case, old_metadata, output, config) for case in (args.case or list(CASES))]
    report = {
        "baseline_git_head": old_metadata["git_head"],
        "current_git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "driving_mode": "GAME",
        "legacy_actuator": args.legacy_actuator,
        "fixed_dt": FIXED_DT,
        "ticks_per_case": old_metadata["ticks"],
        "seed": 23,
        "config_matches_baseline": not config_differences,
        "config_differences": config_differences,
        "unused_old_config_fields_ignored": sorted(UNUSED_OLD_CONFIG_FIELDS),
        "current_config": _json_value(current_config),
        "source_sha256": _source_hashes(),
        "geometry_float32_tolerance": {
            "rule": "max(5e-7, 2 ULP of the compared float32 magnitudes)",
            "max_used": max(item["max_geometry_tolerance"] for item in results),
        },
        "ignored_identity_fields": sorted(IGNORED_KEYS),
        "ignored_added_input_field": "input.direction (default 1)",
        "cases": results,
        "passed": not config_differences and all(item["passed"] for item in results),
    }
    (output / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "passed": report["passed"],
        "output": str(output),
        "config_matches_baseline": report["config_matches_baseline"],
        "cases": [
            {
                "case": item["case"],
                "passed": item["passed"],
                "ticks": item["ticks"],
                "mismatch_count": item["mismatch_count"],
                "max_geometry_abs_delta": item["max_geometry_abs_delta"],
                "max_geometry_path": item["max_geometry_path"],
                "max_other_numeric_abs_delta": item["max_other_numeric_abs_delta"],
            }
            for item in results
        ],
    }, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
