"""独立平面ABS对照；轮心速度与轮速均为仿真真值观测。"""

import argparse
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / 'tools'))

from panda3d.core import Vec3
from physics.reference_ab import (
    SETTLE_TICKS,
    _create_vehicle,
    _flatten,
    _source_hashes,
    _step,
    _write_csv,
)

from driving_modes import REFERENCE_CAR
from vehicle_state import FIXED_DT, VehicleCommand

CASES = ("asphalt", "low-mu", "split-mu", "steering", "reverse")


def run_trial(case, enabled, duration=6.0, wheel_brakes=None, *, vehicle_config=None):
    base = REFERENCE_CAR if vehicle_config is None else vehicle_config
    config = replace(base, braking=replace(base.braking, abs_enabled=enabled))
    if case == "low-mu":
        config = replace(config, road_friction=.6)
    world, vehicle = _create_vehicle(config)
    if case == "split-mu":
        vehicle.on_asphalt = lambda x, _y: x < 0
    try:
        for _ in range(SETTLE_TICKS):
            _step(world, vehicle, VehicleCommand())
        initial_speed = -30 / 3.6 if case == "reverse" else 100 / 3.6
        vehicle._chassis.setLinearVelocity(Vec3(0, initial_speed, 0))
        vehicle.tires.initialize_rolling(initial_speed)
        vehicle.powertrain.initialize_rolling(initial_speed)
        start = vehicle.snapshot().position
        command = VehicleCommand(
            steering=2 if case == "steering" else 0, brake=1,
            direction=-1 if case == "reverse" else 1, wheel_brakes=wheel_brakes,
        )
        rows, locked, longest, current = [], [0]*4, [0]*4, [0]*4
        peak_yaw, distance = 0.0, 0.0
        previous_heading = vehicle.snapshot().heading
        accumulated_heading = peak_unwrapped_heading = peak_yaw_rate = 0.0
        wheel_extrema = [{} for _ in range(4)]
        phase_ticks = [{} for _ in range(4)]
        previous = start
        stopped = False

        def record(tick, state):
            row = {"tick": tick, "time_s": tick * FIXED_DT}
            _flatten("command", asdict(command), row)
            _flatten("state", asdict(state), row)
            row["horizontal_speed_mps"] = math.hypot(*state.velocity[:2])
            row["path_distance_m"] = distance
            rows.append(row)

        record(0, vehicle.snapshot())
        for tick in range(1, round(duration / FIXED_DT) + 1):
            _step(world, vehicle, command)
            state = vehicle.snapshot()
            distance += math.hypot(state.position[0]-previous[0], state.position[1]-previous[1])
            previous = state.position
            peak_yaw = max(peak_yaw, abs(state.heading))
            accumulated_heading += (state.heading - previous_heading + 180) % 360 - 180
            previous_heading = state.heading
            peak_unwrapped_heading = max(peak_unwrapped_heading, abs(accumulated_heading))
            peak_yaw_rate = max(peak_yaw_rate, abs(state.dynamics.yaw_rate))
            for index, wheel in enumerate(state.wheel_dynamics):
                brake = state.brake_states[index]
                values = {
                    "longitudinal_speed": wheel.longitudinal_speed, "omega": wheel.omega,
                    "kappa": wheel.kappa, "normal_load": wheel.normal_load,
                    "fx": wheel.fx, "fy": wheel.fy, "pressure": brake.pressure,
                    "brake_torque": wheel.brake_torque,
                }
                for name, value in values.items():
                    if value is not None:
                        limits = wheel_extrema[index].setdefault(name, [value, value])
                        limits[0], limits[1] = min(limits[0], value), max(limits[1], value)
                phases = phase_ticks[index]
                phases[brake.phase] = phases.get(brake.phase, 0) + 1
                is_locked = (wheel.sample_support and
                             abs(wheel.omega * config.wheel_radius) < .2 and
                             abs(wheel.longitudinal_speed) > 1)
                locked[index] += int(is_locked)
                current[index] = current[index]+1 if is_locked else 0
                longest[index] = max(longest[index], current[index])
            stopped = math.hypot(*state.velocity[:2]) < .1
            if tick % 6 == 0 or stopped:
                record(tick, state)
            if stopped:
                break
        if rows[-1]["tick"] != tick:
            record(tick, state)
        return {
            "case": case, "abs_enabled": enabled, "config": asdict(config),
            "ticks": tick, "stopped": stopped, "elapsed_s": tick * FIXED_DT,
            "initial_speed_mps": initial_speed,
            "final_horizontal_speed_mps": math.hypot(*state.velocity[:2]),
            "path_distance_m": distance,
            "longitudinal_displacement_m": state.position[1]-start[1],
            "lateral_displacement_m": state.position[0]-start[0],
            "peak_abs_heading_deg": peak_yaw,
            "heading_change_deg": accumulated_heading,
            "peak_abs_unwrapped_heading_deg": peak_unwrapped_heading,
            "peak_abs_yaw_rate_radps": peak_yaw_rate,
            "locked_wheel_seconds": [v * FIXED_DT for v in locked],
            "longest_lock_seconds": [v * FIXED_DT for v in longest],
            "wheel_extrema_each_tick": wheel_extrema, "brake_phase_ticks": phase_ticks,
        }, rows
    finally:
        vehicle.close()


def run_matrix(output, duration=6.0, cases=CASES):
    output.mkdir(parents=True, exist_ok=False)
    source = _source_hashes()
    results = []
    for case in cases:
        pair = {"case": case}
        for label, enabled in (("A", False), ("B", True)):
            summary, rows = run_trial(case, enabled, duration)
            _write_csv(output / f"{case}-{label}.csv", rows)
            pair[label] = summary
        results.append(pair)
        print(json.dumps(pair, ensure_ascii=False))
    report = {
        "source_sha256_before": source, "source_sha256_after": _source_hashes(),
        "protocol": {
            "observer": "simulation truth; no real sensor or vehicle speed estimator",
            "world": "independent horizontal Bullet plane, gravity -9.81",
            "settle_ticks": 240, "step_s": FIXED_DT, "sample_stride": 6,
            "initialization": "body speed and rolling omega assigned once after settling",
            "stop": "horizontal velocity norm < 0.1 m/s or duration limit",
            "feedback": "previous completed wheel sample; feedback_tick in CSV",
            "direction": "observe lock reduction, slip recovery, pressure modulation; distance and yaw unrestricted",
        }, "cases": results,
    }
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    args = parser.parse_args()
    run_matrix(args.output, args.duration, args.cases)


if __name__ == "__main__":
    main()
