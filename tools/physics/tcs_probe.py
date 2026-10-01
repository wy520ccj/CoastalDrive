"""独立平面TCS A/B机制对照；逐步真值反馈不代表真实传感器或高保真验收。"""

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from panda3d.core import TransformState, Vec3
from physics.reference_ab import SETTLE_TICKS, _create_vehicle, _flatten, _source_hashes, _step

from driving_modes import REFERENCE_CAR
from vehicle_state import FIXED_DT, VehicleCommand

CASES = ("asphalt", "low-mu", "split-mu", "reverse", "airborne-recontact", "lift-off", "driver-brake")
SLIP_LIMIT = .2
PHASE_CHANGE_S = 2.0


def trial_config(case, enabled):
    config = replace(REFERENCE_CAR, traction=replace(REFERENCE_CAR.traction, tcs_enabled=enabled))
    if case in ("low-mu", "lift-off", "driver-brake"):
        config = replace(config, road_friction=.3)
    elif case == "split-mu":
        config = replace(config, grass_friction=.2)
    return config


def command_at(case, time_s):
    direction = -1 if case == "reverse" else 1
    if case == "lift-off" and time_s >= PHASE_CHANGE_S:
        return "lift-off", VehicleCommand(direction=direction)
    if case == "driver-brake" and time_s >= PHASE_CHANGE_S:
        return "driver-brake", VehicleCommand(throttle=1, brake=1, direction=direction)
    return "acceleration", VehicleCommand(throttle=1, direction=direction)


def run_trial(case, enabled, duration=6.0):
    if case not in CASES:
        raise ValueError(f"未知TCS工况：{case}")
    if not math.isfinite(duration) or duration < FIXED_DT:
        raise ValueError("试验时长须至少一个有限固定步")
    config = trial_config(case, enabled)
    world, vehicle = _create_vehicle(config)
    if case == "split-mu":
        vehicle.on_asphalt = lambda x, _y: x < 0
    try:
        if case == "airborne-recontact":
            # 只在首步前指定离地初值；随后由重力与真实接触落回平面。
            pose = vehicle._chassis.getTransform()
            position = pose.getPos() + Vec3(0, 0, 2)
            vehicle._chassis.setTransform(TransformState.makePosQuatScale(position, pose.getQuat(), Vec3(1)))
        else:
            for _ in range(SETTLE_TICKS):
                _step(world, vehicle, VehicleCommand())
        state = vehicle.snapshot()
        start = previous_position = state.position
        previous_heading = state.heading
        heading = peak_heading = peak_yaw_rate = distance = 0.0
        slips = [0.0] * 4
        excess = [0.0] * 4
        overlimit = [0] * 4
        airborne = [0] * 4
        recontacts = [0] * 4
        previous_support = [wheel.sample_support for wheel in state.wheel_dynamics]
        extrema = [{} for _ in range(4)]
        active_ticks = 0
        phase_ticks = {}
        rows = []

        def record(tick, phase, command):
            row = {"tick": tick, "time_s": tick * FIXED_DT, "phase": phase}
            _flatten("command", asdict(command), row)
            _flatten("state", asdict(state), row)
            row["horizontal_speed_mps"] = math.hypot(*state.velocity[:2])
            row["path_distance_m"] = distance
            row["unwrapped_heading_change_deg"] = heading
            rows.append(row)

        phase, command = command_at(case, 0)
        record(0, "initial", command)
        for tick in range(1, round(duration / FIXED_DT) + 1):
            # command覆盖[tick-1, tick]，2秒边界后的第一步切换踏板。
            phase, command = command_at(case, (tick - 1) * FIXED_DT)
            _step(world, vehicle, command)
            state = vehicle.snapshot()
            distance += math.hypot(state.position[0] - previous_position[0], state.position[1] - previous_position[1])
            previous_position = state.position
            heading += (state.heading - previous_heading + 180) % 360 - 180
            previous_heading = state.heading
            peak_heading = max(peak_heading, abs(heading))
            peak_yaw_rate = max(peak_yaw_rate, abs(state.dynamics.yaw_rate))
            active_ticks += int(state.traction_state.active)
            phase_ticks[phase] = phase_ticks.get(phase, 0) + 1
            for index, wheel in enumerate(state.wheel_dynamics):
                supported = wheel.sample_support
                airborne[index] += int(not supported)
                recontacts[index] += int(supported and not previous_support[index])
                previous_support[index] = supported
                if supported and wheel.kappa is not None:
                    slip = abs(wheel.kappa)
                    slips[index] += slip * FIXED_DT
                    excess[index] += max(0, slip - SLIP_LIMIT) * FIXED_DT
                    overlimit[index] += int(slip > SLIP_LIMIT)
                brake = state.brake_states[index]
                values = {"omega": wheel.omega, "kappa": wheel.kappa, "normal_load": wheel.normal_load,
                          "fx": wheel.fx, "fy": wheel.fy, "drive_torque": wheel.drive_torque,
                          "brake_torque": wheel.brake_torque, "pressure": brake.pressure}
                for name, value in values.items():
                    if value is not None:
                        limits = extrema[index].setdefault(name, [value, value])
                        limits[0], limits[1] = min(limits[0], value), max(limits[1], value)
            record(tick, phase, command)
        summary = {
            "case": case, "tcs_enabled": enabled, "config": asdict(config), "ticks": tick,
            "elapsed_s": tick * FIXED_DT, "phase_ticks": phase_ticks,
            "final_horizontal_speed_mps": math.hypot(*state.velocity[:2]),
            "final_signed_speed_mps": vehicle.signed_speed(), "path_distance_m": distance,
            "longitudinal_displacement_m": state.position[1] - start[1],
            "lateral_displacement_m": state.position[0] - start[0],
            "heading_change_deg": heading, "peak_abs_unwrapped_heading_deg": peak_heading,
            "peak_abs_yaw_rate_radps": peak_yaw_rate, "tcs_active_seconds": active_ticks * FIXED_DT,
            "supported_abs_slip_integral_s": slips, "supported_excess_slip_integral_s": excess,
            "supported_overlimit_wheel_seconds": [n * FIXED_DT for n in overlimit],
            "airborne_wheel_seconds": [n * FIXED_DT for n in airborne],
            "recontact_counts": recontacts, "wheel_extrema_each_tick": extrema,
        }
        return summary, rows
    finally:
        vehicle.close()


def source_hashes():
    hashes = _source_hashes()
    for path in (Path(__file__), ROOT / "tools/physics/reference_ab.py"):
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def write_csv(path, rows):
    # 初始空接触与后续接触元组字段不同，完整保留所有步的诊断列。
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_matrix(output, duration=6.0, cases=CASES):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source = source_hashes()
    results = []
    pending = [(case, label) for case in cases for label in ("A", "B")]
    try:
        for case in cases:
            pair = {"case": case}
            results.append(pair)
            for label, enabled in (("A", False), ("B", True)):
                summary, rows = run_trial(case, enabled, duration)
                filename = f"{case}-{label}.csv"
                write_csv(output / filename, rows)
                pair[label] = {**summary, "csv": filename}
                pending.remove((case, label))
    except Exception as error:
        # 文件/执行边界留下明确失败账目，异常继续上抛，不能冒充完成。
        failure = {
            "status": "failed", "failed_trial": pending[0],
            "error": f"{type(error).__name__}: {error}", "not_run": pending[1:],
            "source_sha256_before": source, "source_sha256_after": source_hashes(),
            "cases": results,
        }
        (output / "summary.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise
    report = {
        "status": "completed",
        "source_sha256_before": source, "source_sha256_after": source_hashes(),
        "protocol": {
            "observer": "simulation truth; previous completed wheel feedback; no sensor estimator",
            "world": "independent horizontal Bullet plane; gravity -9.81; no window",
            "step_s": FIXED_DT, "sample_stride": 1, "settle_ticks": SETTLE_TICKS,
            "airborne_settle_ticks": 0, "airborne_initial_height_offset_m": 2,
            "initialization": "zero speed; airborne pose assigned once before first step; no runtime reset",
            "phase_change_s": PHASE_CHANGE_S,
            "lift_off": "full throttle [0,2s), zero throttle thereafter",
            "driver_brake": "full throttle throughout; full brake from 2s (priority conflict)",
            "slip_metric": "supported wheels only; absolute kappa; diagnostic threshold 0.2",
            "slip_limit": SLIP_LIMIT,
            "comparison": "same car, initial conditions and commands; only tcs_enabled differs within each pair",
            "scope": "mechanism evidence only; acceleration/distance/yaw improvement not mandatory; no high-fidelity completion claim",
        }, "cases": results,
    }
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    run_matrix(output, args.duration, args.cases)
    print(f"saved {output / 'summary.json'}")


if __name__ == "__main__":
    main()
