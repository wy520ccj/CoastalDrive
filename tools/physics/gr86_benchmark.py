"""GR86同版本公开实测协议；直线动力／制动与真实定圆驾驶分别记录。"""

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.core import Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from physics.esc_probe import write_csv
from physics.reference_ab import _create_vehicle, _flatten, _step

from vehicle_designs import GR86_DESIGN, GR86_PROFILE_PATH
from vehicle_parameters import load_vehicle_config
from vehicle_state import FIXED_DT, VehicleCommand


def settled(config, speed=0.):
    world, car = _create_vehicle(config)
    for _ in range(240):
        _step(world, car, VehicleCommand())
    initial = asdict(car.snapshot())
    car._chassis.setLinearVelocity(Vec3(0, speed, 0))
    car.tires.initialize_rolling(speed)
    car.powertrain.initialize_rolling(speed)
    return world, car, initial


def sample(car, command, tick):
    row = {"tick": tick, "time_s": tick * FIXED_DT}
    _flatten("command", asdict(command), row)
    _flatten("state", asdict(car.snapshot()), row)
    return row


def launch(config, launch_rpm, shift_rpm):
    world, car, initial = settled(config)
    rows, events = [], {}
    origin = car.snapshot().position
    gear = 1
    try:
        preload = []
        if launch_rpm:
            for preload_tick in range(1, 601):
                command = VehicleCommand(throttle=1., clutch=0., direction=1, gear=1)
                _step(world, car, command)
                row = sample(car, command, preload_tick)
                row["phase"] = "prelaunch"
                preload.append(row)
                if car.powertrain.rpm >= launch_rpm:
                    break
            else:
                raise ArithmeticError("试验驾驶员未达到声明的起步RPM")
            for row in preload:
                row["tick"] -= preload_tick
                row["time_s"] = row["tick"] * FIXED_DT
            rows.extend(preload)
        origin = car.snapshot().position
        rpm_at_release = car.powertrain.rpm
        for tick in range(1, 2401):
            # 明确的试验驾驶员挡位请求；六速手动硬件仍走实际离合／有限同步。
            if car.powertrain.shift_phase == "engaged" and car.powertrain.rpm >= shift_rpm and gear < len(config.gear_ratios):
                gear += 1
            command = VehicleCommand(throttle=1., direction=1, gear=gear, clutch=1. if launch_rpm else None)
            _step(world, car, command)
            state = car.snapshot()
            row = sample(car, command, tick)
            row["phase"] = "launch"
            rows.append(row)
            distance = state.position[1] - origin[1]
            for label, reached in (("one_foot", distance >= .3048), ("60mph", state.speed >= 26.8224),
                                   ("100kmh", state.speed >= 100 / 3.6), ("quarter_mile", distance >= 402.336)):
                if label not in events and reached:
                    events[label] = {"time_s": tick * FIXED_DT, "speed_m_s": state.speed, "distance_m": distance}
            if "quarter_mile" in events:
                break
        elapsed = events["60mph"]["time_s"] - events["one_foot"]["time_s"] if "60mph" in events and "one_foot" in events else None
        quarter = events["quarter_mile"]["time_s"] - events["one_foot"]["time_s"] if "quarter_mile" in events and "one_foot" in events else None
        return {"case": "launch", "settled_snapshot": initial, "events": events,
                "0_60mph_with_one_foot_rollout_s": elapsed,
                "quarter_mile_with_one_foot_rollout_s": quarter,
                "timing_definition": "completed 120Hz tick threshold; full standstill and 0.3048m rollout separately recorded",
                "shift_request_rpm": shift_rpm, "prelaunch_target_rpm": launch_rpm,
                "rpm_at_clutch_release": rpm_at_release, "driver_equipment_payload_kg": 0.}, rows
    finally:
        car.close()


def brake(config, mph):
    world, car, initial = settled(config, mph * .44704)
    origin, rows = car.snapshot().position, []
    try:
        for tick in range(1, 1801):
            command = VehicleCommand(brake=1., direction=1, clutch=0., gear=1)
            _step(world, car, command)
            rows.append(sample(car, command, tick))
            state = car.snapshot()
            if math.hypot(*state.velocity[:2]) < .1:
                break
        return {"case": f"brake-{mph}mph", "settled_snapshot": initial,
                "initial_speed_m_s": mph * .44704, "stopped": math.hypot(*state.velocity[:2]) < .1,
                "stopping_time_s": tick * FIXED_DT, "stopping_distance_m": state.position[1] - origin[1],
                "stop_speed_threshold_m_s": .1, "driver_equipment_payload_kg": 0.}, rows
    finally:
        car.close()


def skidpad(config):
    radius = 45.72
    world, car, initial = settled(config, 18.)
    origin = car.snapshot().position
    center = origin[0] + radius, origin[1]
    rows, stages = [], []
    try:
        for stage, target_speed in enumerate((18., 20., 21., 22.)):
            accepted = []
            for local_tick in range(1200):
                state = car.snapshot()
                speed = math.hypot(*state.velocity[:2])
                phase = math.atan2(state.position[1] - center[1], state.position[0] - center[0])
                preview = max(14., 1.2 * speed)
                target = center[0] + radius * math.cos(phase - preview / radius), center[1] + radius * math.sin(phase - preview / radius)
                dx, dy = target[0] - state.position[0], target[1] - state.position[1]
                bearing_error = math.atan2(dx, dy) + math.radians(state.heading)
                rack = math.degrees(math.atan2(2 * config.wheelbase * math.sin(bearing_error), math.hypot(dx, dy)))
                error = target_speed - speed
                command = VehicleCommand(throttle=max(0., min(1., .12 + .6 * error)),
                                         brake=max(0., min(1., .8 * (-error - .2))), steering=rack, direction=1, gear=2)
                _step(world, car, command)
                tick = stage * 1200 + local_tick + 1
                rows.append(sample(car, command, tick))
                state = car.snapshot()
                actual_radius = math.hypot(state.position[0] - center[0], state.position[1] - center[1])
                if local_tick >= 840 and abs(actual_radius - radius) <= .02 * radius and abs(state.speed - target_speed) < .3:
                    accepted.append(abs(state.lateral_acceleration) / 9.81)
            stages.append({"target_speed_m_s": target_speed, "accepted_ticks": len(accepted),
                           "mean_lateral_g": sum(accepted) / len(accepted) if accepted else None,
                           "last_radius_m": actual_radius, "last_speed_m_s": state.speed})
        return {"case": "300ft-skidpad", "settled_snapshot": initial, "radius_m": radius, "stages": stages,
                "measurement": "last 3s of each 10s speed stage; radius within 2%, speed within .3m/s; actual acceleration",
                "driver": "pure-pursuit circular path, finite rack and actual throttle/brake; no state correction"}, rows
    finally:
        car.close()


def run(output, config_path, cases, launch_rpm, shift_rpm, raw_electronics):
    output.mkdir(parents=True, exist_ok=False)
    config = load_vehicle_config(config_path, GR86_DESIGN)
    if raw_electronics:
        config = replace(config, traction=replace(config.traction, tcs_enabled=False),
                         stability=replace(config.stability, esc_enabled=False))
    hashes = lambda: {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for folder in ("src", "tools/physics") for p in (ROOT / folder).rglob("*.py")}
    report = {"status": "running", "config": asdict(config), "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
              "source_before": hashes(), "results": [], "protocol": {"physics_hz": 120, "trace_hz": 120,
              "curb_mass_only": True, "known_public_driver_equipment_payload": False, "raw_electronics": raw_electronics,
              "environment": "same gravity, air, zero wind and plane; tyre hardware and real actuators unchanged"}}

    def save():
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    save()
    try:
        for case in cases:
            result, rows = launch(config, launch_rpm, shift_rpm) if case == "launch" else skidpad(config) if case == "skidpad" else brake(config, int(case.split("-")[1]))
            path = output / (case + ".csv.gz")
            write_csv(path, rows)
            result.update(trace=path.name, trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            report["results"].append(result)
            save()
            print(json.dumps({k: v for k, v in result.items() if k != "settled_snapshot"}, ensure_ascii=False), flush=True)
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", failed_case=case, error=str(error),
                      not_run=cases[cases.index(case) + 1:])
        raise
    else:
        report["status"] = "completed"
    finally:
        report["source_after"] = hashes()
        report["source_stable"] = report["source_after"] == report["source_before"]
        save()
    assert report["source_stable"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=GR86_PROFILE_PATH)
    parser.add_argument("--launch-rpm", type=float, default=4500., help="明确试验驾驶员预升转速；0沿用低速自动离合起步")
    parser.add_argument("--shift-rpm", type=float, default=7400.)
    parser.add_argument("--raw-electronics", action="store_true", help="硬件标定暂关闭TCS/ESC；ABS保持车型配置")
    parser.add_argument("--cases", nargs="+", choices=("launch", "brake-70", "brake-100", "skidpad"), default=("launch", "brake-70", "brake-100", "skidpad"))
    args = parser.parse_args()
    run(args.output, args.config, args.cases, args.launch_rpm, args.shift_rpm, args.raw_electronics)
