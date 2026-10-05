"""通用参考车参数变化的独立平面 Bullet 对照。"""

import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from driver_assist import SIMULATION_INPUT
from driving_modes import REFERENCE_CAR
from vehicle import Vehicle
from vehicle_state import FIXED_DT, VehicleCommand
from world_step import advance_world, physical_substeps

DEFAULT_OUTPUT = ROOT / "docs" / "evidence" / "PHYS-MODES-01" / "reference-ab"
SETTLE_TICKS = 240
SAMPLE_STRIDE = 6
CASES = {
    "B1-wheel-inertia": (12 * 120, "full_throttle"),
    "B2-cg-height": (2 * 120, "brake_045"),
    "B3-asphalt-mu": (6 * 120, "full_brake_until_stop"),
}


def _flatten(prefix, value, row):
    if isinstance(value, dict):
        for key, child in value.items():
            _flatten(f"{prefix}.{key}" if prefix else key, child, row)
    elif isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            _flatten(f"{prefix}.{index}", child, row)
    else:
        row[prefix] = value


def _create_vehicle(config):
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("reference-ab-ground")
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
    ground.setIntoCollideMask(BitMask32.bit(0) | BitMask32.bit(1))
    world.attachRigidBody(ground)
    spawn_z = 0.55 + config.center_of_mass_height - REFERENCE_CAR.center_of_mass_height
    vehicle = Vehicle(
        world, lambda _x, _y: True, (0, 0, spawn_z),
        name="reference-ab-vehicle", config=config, input_config=SIMULATION_INPUT,
    )
    return world, vehicle


def _step(world, vehicle, command, *, world_substeps=None):
    # 旧Git运行必须显式给出其真实单步协议，不按缺失字段猜测旧接口。
    substeps = physical_substeps(vehicle.config) if world_substeps is None else world_substeps
    advance_world(world, [(vehicle, command)], substeps=substeps)


def _contact_loads(snapshot):
    front = sum(contact.normal_load for contact in snapshot.wheel_contacts[:2])
    rear = sum(contact.normal_load for contact in snapshot.wheel_contacts[2:])
    return front, rear


def run_trial(case, config, ticks=None, *, sample_stride=SAMPLE_STRIDE):
    if case not in CASES:
        raise ValueError(f"unknown reference comparison: {case}")
    default_ticks, scenario = CASES[case]
    max_ticks = default_ticks if ticks is None else ticks
    world, vehicle = _create_vehicle(config)
    try:
        neutral = VehicleCommand()
        for _ in range(SETTLE_TICKS):
            _step(world, vehicle, neutral)
        static_snapshot = vehicle.snapshot()
        static_front_load, static_rear_load = _contact_loads(static_snapshot)

        initial_speed = 0.0
        if case == "B2-cg-height":
            initial_speed = 20.0
        elif case == "B3-asphalt-mu":
            initial_speed = 100 / 3.6
        if initial_speed:
            vehicle._chassis.setLinearVelocity(Vec3(0, initial_speed, 0))
            vehicle.tires.initialize_rolling(initial_speed)
            vehicle.powertrain.initialize_rolling(initial_speed)

        initial_position = vehicle._chassis.getTransform().getPos()
        initial_front, initial_rear = _contact_loads(vehicle.snapshot())
        rows = []
        all_front = []
        all_rear = []
        decelerations = []
        locked_wheel_ticks = 0
        supported_wheel_ticks = 0
        previous_speed = vehicle.signed_speed()
        stopped_at_tick = None
        for tick in range(1, max_ticks + 1):
            if scenario == "full_throttle":
                command = VehicleCommand(throttle=1.0, direction=1)
            elif scenario == "brake_045":
                command = VehicleCommand(brake=0.45, direction=1)
            else:
                command = VehicleCommand(brake=1.0, direction=1)
            _step(world, vehicle, command)
            snapshot = vehicle.snapshot()
            speed = vehicle.signed_speed()
            decelerations.append((previous_speed - speed) / FIXED_DT)
            previous_speed = speed
            front, rear = _contact_loads(snapshot)
            all_front.append(front)
            all_rear.append(rear)
            for wheel in snapshot.wheel_dynamics:
                if wheel.road_support:
                    supported_wheel_ticks += 1
                    if abs(wheel.omega * config.wheel_radius) < 0.2 and abs(
                        wheel.longitudinal_speed
                    ) > 1.0:
                        locked_wheel_ticks += 1
            if tick % sample_stride == 0 or tick == 1:
                row = {"tick": tick, "time_s": tick * FIXED_DT}
                _flatten("command", asdict(command), row)
                _flatten("state", asdict(snapshot), row)
                row["measured_signed_speed_mps"] = speed
                row["front_normal_load_n"] = front
                row["rear_normal_load_n"] = rear
                rows.append(row)
            if scenario == "full_brake_until_stop" and math.hypot(*snapshot.velocity[:2]) < 0.1:
                stopped_at_tick = tick
                break

        elapsed = tick * FIXED_DT
        final_speed = vehicle.signed_speed()
        final_position = vehicle._chassis.getTransform().getPos()
        tail_front = statistics.fmean(all_front[-60:])
        tail_total = tail_front + statistics.fmean(all_rear[-60:])
        summary = {
            "case": case,
            "scenario": scenario,
            "ticks": tick,
            "elapsed_s": elapsed,
            "initial_speed_mps": initial_speed,
            "final_speed_mps": final_speed,
            "maximum_speed_mps": max(
                [initial_speed] + [row["measured_signed_speed_mps"] for row in rows]
            ),
            "longitudinal_displacement_m": float(final_position.y - initial_position.y),
            "mean_longitudinal_deceleration_mps2": statistics.fmean(decelerations),
            "mean_front_normal_load_n": statistics.fmean(all_front),
            "mean_rear_normal_load_n": statistics.fmean(all_rear),
            "static_front_normal_load_n": static_front_load,
            "static_rear_normal_load_n": static_rear_load,
            "settled_snapshot": asdict(static_snapshot),
            "initial_front_normal_load_n": initial_front,
            "initial_rear_normal_load_n": initial_rear,
            "late_front_normal_load_n": tail_front,
            "late_front_load_delta_from_static_n": tail_front - static_front_load,
            "late_front_load_fraction": tail_front / tail_total,
            "stopped": stopped_at_tick is not None,
            "time_to_stop_s": stopped_at_tick * FIXED_DT if stopped_at_tick else None,
            "locked_wheel_tick_fraction": (
                locked_wheel_ticks / supported_wheel_ticks if supported_wheel_ticks else 0.0
            ),
            "supported_wheel_ticks": supported_wheel_ticks,
            "config": asdict(config),
        }
        return summary, rows
    finally:
        vehicle.close()


def _source_hashes():
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"):
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "src").rglob("*.py"))
    }


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_matrix(output):
    if output.exists():
        raise FileExistsError(f"output must be a new directory: {output}")
    output.mkdir(parents=True)
    variants = {
        "B1-wheel-inertia": replace(REFERENCE_CAR, wheel_inertia=3.6),
        "B2-cg-height": replace(REFERENCE_CAR, center_of_mass_height=0.62),
        "B3-asphalt-mu": replace(REFERENCE_CAR, road_friction=0.6),
    }
    expectations = {
        "B1-wheel-inertia": "higher wheel inertia should reduce acceleration and final speed",
        "B2-cg-height": "higher CG should increase measured braking load transfer; record deceleration",
        "B3-asphalt-mu": "lower asphalt mu should reduce braking deceleration and increase stopping distance",
    }
    results = []
    for case, candidate_config in variants.items():
        baseline, baseline_rows = run_trial(case, REFERENCE_CAR)
        candidate, candidate_rows = run_trial(case, candidate_config)
        suffix = case.removeprefix("B1-").removeprefix("B2-").removeprefix("B3-")
        baseline_file = f"{case}-A-reference-{suffix}.csv"
        candidate_file = f"{case}-B-candidate-{suffix}.csv"
        _write_csv(output / baseline_file, baseline_rows)
        _write_csv(output / candidate_file, candidate_rows)
        results.append({
            "case": case,
            "before_A": baseline,
            "after_B": candidate,
            "expected_direction": expectations[case],
            "samples_A": baseline_file,
            "samples_B": candidate_file,
        })
    rotational_mass = 4 * REFERENCE_CAR.wheel_inertia / REFERENCE_CAR.wheel_radius**2
    report = {
        "source_git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_sha256": _source_hashes(),
        "protocol": {
            "world": "independent BulletWorld; z gravity -9.81; infinite horizontal BulletPlaneShape",
            "step_s": FIXED_DT,
            "bullet_max_substeps": 0,
            "settle_ticks": SETTLE_TICKS,
            "sample_every_ticks": SAMPLE_STRIDE,
            "input": "fixed direct VehicleCommand; no DriverAssist mapping",
            "initial_speed": "set once after settle for braking trials; initialize tire rolling once",
            "initial_cg_pose": "vertical spawn offset preserves identical wheel/body world geometry as CG height changes",
        },
        "baseline_config_A": asdict(REFERENCE_CAR),
        "wheel_rotational_equivalent_mass_kg": rotational_mass,
        "variants_B": {case: asdict(config) for case, config in variants.items()},
        "cases": results,
    }
    report_path = output / "summary.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    report = run_matrix(output)
    for result in report["cases"]:
        old = result["before_A"]
        new = result["after_B"]
        print(json.dumps({
            "case": result["case"],
            "expected": result["expected_direction"],
            "A_final_speed_mps": old["final_speed_mps"],
            "B_final_speed_mps": new["final_speed_mps"],
            "A_deceleration_mps2": old["mean_longitudinal_deceleration_mps2"],
            "B_deceleration_mps2": new["mean_longitudinal_deceleration_mps2"],
            "A_late_front_load_delta_n": old["late_front_load_delta_from_static_n"],
            "B_late_front_load_delta_n": new["late_front_load_delta_from_static_n"],
            "A_distance_m": old["longitudinal_displacement_m"],
            "B_distance_m": new["longitudinal_displacement_m"],
            "A_stopped": old["stopped"],
            "B_stopped": new["stopped"],
        }, ensure_ascii=False))
    print(f"saved {output / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
