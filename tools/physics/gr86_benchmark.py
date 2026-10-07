"""GR86同版本公开实测协议；直线动力／制动与真实定圆驾驶分别记录。"""

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
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
            throttle, clutch = 1., None
            if launch_rpm:
                before = car.snapshot()
                speed = math.hypot(*before.velocity[:2])
                wheel_speed = config.wheel_radius * sum(w.relative_omega for w in before.wheel_dynamics[2:]) / 2
                slip = (wheel_speed - speed) / max(5., speed)
                launch_speed = launch_rpm * math.tau / 60 * config.wheel_radius / (config.gear_ratios[0] * config.final_drive)
                if gear == 1 and speed < .9 * launch_speed:
                    throttle = max(0., min(1., .7 + .0004 * (launch_rpm - before.rpm)))
                    clutch = max(.1, .58 - .4 * max(0., slip - .08))
                else:
                    clutch = 1.
                throttle = max(0., throttle - 2 * max(0., slip - .08))
            command = VehicleCommand(throttle=throttle, direction=1, gear=gear, clutch=clutch)
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
                "driver": "finite clutch feathering below launch-speed match; tachometer/velocity slip-based throttle feathering above .08; real gear synchronization",
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


def fitted_circle(points):
    values = np.asarray(points)
    origin = values.mean(axis=0)
    local = values - origin
    squared = np.sum(local**2, axis=1)
    solution, _residual, rank, _singular = np.linalg.lstsq(np.column_stack((2 * local, np.ones(len(local)))), squared, rcond=None)
    if rank < 3:
        return {"status": "insufficient_curvature", "radius_m": None, "radial_rms_m": None}
    radius = math.sqrt(solution[2] + sum(solution[:2]**2))
    radii = np.linalg.norm(local - solution[:2], axis=1)
    return {"status": "fitted", "radius_m": radius,
            "radial_rms_m": float(np.sqrt(np.mean((radii - radius)**2))),
            "center_m": tuple(origin + solution[:2])}


def skidpad(config, speeds=(8., 12., 16., 18., 20., 21., 22.), stage_seconds=10.):
    radius = 45.72
    world, car, initial = settled(config, speeds[0])
    rows, stages = [], []
    try:
        stage_ticks = round(stage_seconds / FIXED_DT)
        rack = math.degrees(math.atan(config.wheelbase / radius))
        speed_integral, measured_curvature_rate = 0., 0.
        previous_velocity = car.snapshot().velocity
        for stage, target_speed in enumerate(speeds):
            tail = []
            previous_target = speeds[max(stage - 1, 0)]
            for local_tick in range(stage_ticks):
                state = car.snapshot()
                speed = math.hypot(*state.velocity[:2])
                vx0, vy0 = previous_velocity[:2]
                vx1, vy1 = state.velocity[:2]
                right_rate = math.atan2(vy0 * vx1 - vx0 * vy1, vx0 * vx1 + vy0 * vy1) / FIXED_DT
                measured_curvature_rate += (right_rate - measured_curvature_rate) * (1 - math.exp(-FIXED_DT / .15))
                if stage * stage_ticks + local_tick >= 120:
                    rack = max(-10., min(10., rack + 4 * (speed / radius - measured_curvature_rate) * FIXED_DT))
                target = previous_target + (target_speed - previous_target) * min(1., local_tick * FIXED_DT / 2)
                error = target - speed
                speed_integral = max(-.12, min(.35, speed_integral + .06 * error * FIXED_DT))
                wheel_speed = config.wheel_radius * sum(w.relative_omega for w in state.wheel_dynamics[2:]) / 2
                slip = (wheel_speed - speed) / max(5., speed)
                throttle = max(0., min(.65, .12 + .3 * error + speed_integral) - 1.5 * max(0., slip - .08))
                if abs(state.dynamics.sideslip) > 5.:
                    throttle = min(throttle, .15)
                command = VehicleCommand(throttle=throttle, brake=max(0., min(1., .8 * (-error - .2))),
                                         steering=rack, direction=1, gear=2)
                previous_velocity = state.velocity
                _step(world, car, command)
                tick = stage * stage_ticks + local_tick + 1
                state = car.snapshot()
                rows.append(sample(car, command, tick))
                if local_tick >= stage_ticks - 360:
                    tail.append(state)
            fit = fitted_circle([state.position[:2] for state in tail])
            valid_geometry = fit["status"] == "fitted" and abs(fit["radius_m"] - radius) <= .02 * radius and fit["radial_rms_m"] <= .005 * radius
            accepted = [state for state in tail if valid_geometry and abs(state.speed - target_speed) < .3]
            stages.append({"target_speed_m_s": target_speed, "accepted_ticks": len(accepted),
                           "mean_lateral_g": float(np.mean([math.hypot(*state.velocity[:2])**2 / (fit["radius_m"] * 9.81) for state in accepted])) if accepted else None,
                           "last_speed_m_s": state.speed, "actual_circle": fit})
        return {"case": "300ft-skidpad", "settled_snapshot": initial, "radius_m": radius, "stages": stages,
                "stage_seconds": stage_seconds,
                "measurement": "last 3s actual trajectory circle fit; radius within 2%, radial RMS within .5%, speed within .3m/s; lateral g=actual speed squared/fitted radius/g",
                "driver": "2s progressive target ramp; slowly integrated measured velocity-curvature error; bounded speed PI; tachometer/sideslip throttle feathering; finite real actuators"}, rows
    finally:
        car.close()


def run(output, config_path, cases, launch_rpm, shift_rpm, raw_electronics, skidpad_speeds, stage_seconds):
    output.mkdir(parents=True, exist_ok=False)
    config = load_vehicle_config(config_path, GR86_DESIGN)
    if raw_electronics:
        config = replace(config, traction=replace(config.traction, tcs_enabled=False),
                         stability=replace(config.stability, esc_enabled=False))
    paths = tuple(p for folder in ("src", "tools/physics") for p in (ROOT / folder).rglob("*.py"))
    hashes = lambda: {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    report = {"status": "running", "config": asdict(config), "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
              "source_before": hashes(), "results": [], "protocol": {"physics_hz": 120, "trace_hz": 120,
              "curb_mass_only": True, "known_public_driver_equipment_payload": False, "raw_electronics": raw_electronics,
              "environment": "same gravity, air, zero wind and plane; tyre hardware and real actuators unchanged"}}

    def save():
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    save()
    try:
        for case in cases:
            result, rows = (launch(config, launch_rpm, shift_rpm) if case == "launch" else
                            skidpad(config, skidpad_speeds, stage_seconds) if case == "skidpad" else
                            brake(config, int(case.split("-")[1])))
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
    parser.add_argument("--skidpad-speeds", type=float, nargs="+", default=(8., 12., 16., 18., 20., 21., 22.))
    parser.add_argument("--stage-seconds", type=float, default=10.)
    parser.add_argument("--cases", nargs="+", choices=("launch", "brake-70", "brake-100", "skidpad"), default=("launch", "brake-70", "brake-100", "skidpad"))
    args = parser.parse_args()
    if args.stage_seconds < 3 or any(speed <= 0. for speed in args.skidpad_speeds):
        parser.error("定圆阶段须至少3秒、目标速度须为正值")
    run(args.output, args.config, args.cases, args.launch_rpm, args.shift_rpm, args.raw_electronics,
        args.skidpad_speeds, args.stage_seconds)
