"""直接控制实验记录、同版本精确重放与同命令参数A/B。"""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from driving_experiment import (
    EXPERIMENT,
    RECORD_SCHEMA,
    DrivingExperiment,
    ExperimentOptions,
    observation_digest,
)
from driving_modes import REFERENCE_CAR, DrivingMode
from sensor_sampling import SensorConfig
from vehicle_parameters import load_vehicle_config, save_vehicle_config
from vehicle_state import VehicleCommand


def source_hashes():
    paths = (*sorted((ROOT / "src").rglob("*.py")), Path(__file__))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def sensor_config(values):
    if values is None:
        return None
    values = dict(values)
    for name in ("initial_accel_bias", "initial_gyro_bias", "gnss_position_std", "gnss_velocity_std"):
        values[name] = tuple(values[name])
    values["gnss_outages"] = tuple(tuple(interval) for interval in values["gnss_outages"])
    return SensorConfig(**values)


def record(commands, output, vehicle_config=REFERENCE_CAR, options=EXPERIMENT,
           *, mode=DrivingMode.SIMULATION, sensors=None, sensor_seed=100):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    experiment = DrivingExperiment(vehicle_config, options, mode=mode, sensors=sensors, sensor_seed=sensor_seed)
    document = {"schema": RECORD_SCHEMA, "status": "running", "options": asdict(options), "mode": mode.value,
                "sensors": asdict(sensors) if sensors is not None else None, "sensor_seed": sensor_seed,
                "physics_hz": 120, "control_hz": 20, "physics_ticks_per_control": 6,
                "source_before": before, "vehicle_file": "vehicle.json",
                "initial_digest": observation_digest(experiment.current), "steps": [],
                "comparison": "exact full physical/sensing observation except contact_epoch and ImpactEvent.epoch"}
    try:
        save_vehicle_config(output / "vehicle.json", vehicle_config)
        document["vehicle_sha256"] = hashlib.sha256((output / "vehicle.json").read_bytes()).hexdigest()
        for command in commands:
            result = experiment.step(command)
            if result.terminated or result.truncated:
                break
        document["status"] = "completed"
    except (ArithmeticError, ValueError, RuntimeError, OSError, AssertionError) as error:
        document.update(status="failed", error=str(error))
        raise
    finally:
        document["steps"] = experiment.records
        document["source_after"] = source_hashes()
        document["source_stable"] = document["source_after"] == before
        try:
            (output / "experiment.json").write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        finally:
            experiment.close()
    assert document["source_stable"]
    return document


def replay(path, output, candidate_config=None):
    path, output = Path(path), Path(output)
    document = json.loads(path.read_text(encoding="utf-8"))
    if document["schema"] != RECORD_SCHEMA or document["status"] != "completed" or not document["source_stable"]:
        raise ValueError("重放需要已完成且源码冻结的当前版本实验记录")
    if document["source_before"] != source_hashes():
        raise ValueError("重放源码与记录版本不同，请使用原版本后重放")
    vehicle_file = path.parent / document["vehicle_file"]
    if hashlib.sha256(vehicle_file.read_bytes()).hexdigest() != document["vehicle_sha256"]:
        raise ValueError("实验完整车辆工程文件与记录SHA不同")
    config = load_vehicle_config(candidate_config or vehicle_file, REFERENCE_CAR)
    commands = [VehicleCommand(**step["command"]) for step in document["steps"]]
    actual = record(commands, output, config, ExperimentOptions(**document["options"]),
                    mode=DrivingMode(document["mode"]), sensors=sensor_config(document["sensors"]),
                    sensor_seed=document["sensor_seed"])
    if candidate_config is None:
        expected_digests = [step["digest"] for step in document["steps"]]
        actual_digests = [step["digest"] for step in actual["steps"]]
        exact = actual["initial_digest"] == document["initial_digest"] and actual_digests == expected_digests
        result = {"status": "passed" if exact else "failed", "kind": "same_hardware_replay",
                  "full_observation_exact": exact, "expected_control_steps": len(expected_digests),
                  "actual_control_steps": len(actual_digests)}
    else:
        old = load_vehicle_config(vehicle_file, REFERENCE_CAR)
        changed = {name: {"baseline": value, "candidate": asdict(config)[name]} for name, value in asdict(old).items()
                   if value != asdict(config)[name]}
        result = {"status": "completed", "kind": "same_commands_parameter_ab", "changed_vehicle_fields": changed,
                  "baseline_final": document["steps"][-1]["observation"] if document["steps"] else None,
                  "candidate_final": actual["steps"][-1]["observation"] if actual["steps"] else None,
                  "baseline_control_steps": len(document["steps"]), "candidate_control_steps": len(actual["steps"])}
    (output / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if candidate_config is None and not result["full_observation_exact"]:
        raise AssertionError("同硬件完整观测重放不一致；差异记录保留")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "replay", "ab"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commands", type=Path, help="VehicleCommand字段对象组成的JSON数组")
    parser.add_argument("--record", type=Path, help="已有experiment.json")
    parser.add_argument("--vehicle-config", type=Path)
    parser.add_argument("--sensors", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.action == "record":
        if args.commands is None:
            parser.error("record需要--commands")
        commands = [VehicleCommand(**values) for values in json.loads(args.commands.read_text(encoding="utf-8"))]
        config = load_vehicle_config(args.vehicle_config, REFERENCE_CAR) if args.vehicle_config else REFERENCE_CAR
        result = record(commands, args.output, config, ExperimentOptions(seed=args.seed),
                        sensors=SensorConfig() if args.sensors else None)
        print(json.dumps({"status": result["status"], "control_steps": len(result["steps"]), "output": str(args.output)}, ensure_ascii=False))
    else:
        if args.record is None or args.action == "ab" and args.vehicle_config is None:
            parser.error("replay需要--record；ab还需要--vehicle-config")
        result = replay(args.record, args.output, args.vehicle_config if args.action == "ab" else None)
        print(json.dumps({key: value for key, value in result.items() if key not in ("baseline_final", "candidate_final")}, ensure_ascii=False))
