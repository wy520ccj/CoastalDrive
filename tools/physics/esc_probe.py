"""独立平面ESC逐tick A/B；仅初始化运动状态，介入通过真实执行器。"""

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from panda3d.core import Quat, TransformState, Vec3
from physics.reference_ab import SETTLE_TICKS, _create_vehicle, _flatten, _source_hashes, _step

from driving_modes import DrivingMode
from vehicle_contacts import road_support
from vehicle_state import FIXED_DT, VehicleCommand

CASES = ("asphalt-brake", "low-mu-brake", "split-mu-brake", "corner-brake",
         "steering-step", "steering-saturation", "reverse", "airborne-recontact", "coast-disturbance")
MODES = ("game", "simulation")


def trial_config(case, enabled, mode="simulation"):
    config = DrivingMode(mode).vehicle_config
    config = replace(config, braking=replace(config.braking, abs_enabled=True),
                     traction=replace(config.traction, tcs_enabled=True),
                     stability=replace(config.stability, esc_enabled=enabled))
    if case == "low-mu-brake":
        config = replace(config, road_friction=.6)
    elif case == "split-mu-brake":
        config = replace(config, road_friction=1.1, grass_friction=.45)
    return config


def command_at(case, time_s):
    if case == "corner-brake":
        return ("corner-entry", VehicleCommand(steering=2, throttle=.15, direction=1)) if time_s < 1.5 else (
            "corner-brake", VehicleCommand(steering=2, brake=.7, direction=1))
    if case in ("steering-step", "steering-saturation"):
        angle = 3 if case == "steering-step" else 12
        return case, VehicleCommand(steering=0 if time_s < .5 else angle, throttle=.3, direction=1)
    if case == "coast-disturbance":
        return "coast", VehicleCommand()
    return "brake", VehicleCommand(brake=1, direction=-1 if case == "reverse" else 1)


def initial_speed(case):
    return (-30 if case == "reverse" else 40 if case == "corner-brake" else
            80 if case in ("steering-step", "steering-saturation", "coast-disturbance") else 100) / 3.6


def tire_contact_moments(pose, contacts, contact_tick, wheels):
    """沿Tires施力前固定坐标还原接点力矩；不包含轮轴反力与其它车身力矩。"""
    orientation = pose.getQuat()
    origin = pose.getPos()
    up = orientation.getUp()
    moments = []
    for index, wheel in enumerate(wheels):
        if wheel.force_contact_tick != contact_tick:
            raise ValueError("轮胎施力tick与缓存接点tick不一致")
        values = {"last_substep_fx_contact_yaw_nm": 0.0,
                  "last_substep_fy_contact_yaw_nm": 0.0,
                  "last_substep_total_contact_yaw_nm": 0.0,
                  "mean_fx_contact_yaw_nm": 0.0, "mean_fy_contact_yaw_nm": 0.0,
                  "mean_total_contact_yaw_nm": 0.0, "force_contact_tick": contact_tick}
        contact = contacts[index] if contacts else None
        if contact is not None and contact.in_contact and road_support(contact.contact_normal):
            steering = Quat()
            steering.setHpr(Vec3(-wheel.steering, 0, 0))
            heading = orientation.xform(steering.xform(Vec3(0, 1, 0)))
            normal = Vec3(*contact.contact_normal)
            tangent = (heading-normal*heading.dot(normal)).normalized()
            lateral = tangent.cross(normal)
            point = Vec3(*contact.contact_point)-origin
            longitudinal_arm = float(point.cross(tangent).dot(up))
            lateral_arm = float(point.cross(lateral).dot(up))
            values["last_substep_fx_contact_yaw_nm"] = longitudinal_arm*wheel.fx
            values["last_substep_fy_contact_yaw_nm"] = lateral_arm*wheel.fy
            values["mean_fx_contact_yaw_nm"] = longitudinal_arm*wheel.longitudinal_impulse/FIXED_DT
            values["mean_fy_contact_yaw_nm"] = lateral_arm*wheel.lateral_impulse/FIXED_DT
            for prefix in ("last_substep", "mean"):
                values[f"{prefix}_total_contact_yaw_nm"] = (
                    values[f"{prefix}_fx_contact_yaw_nm"]+values[f"{prefix}_fy_contact_yaw_nm"])
        moments.append(values)
    return moments


def run_trial(case, enabled, duration=6.0, mode="simulation"):
    if case not in CASES:
        raise ValueError(f"未知ESC工况：{case}")
    if not math.isfinite(duration) or duration < FIXED_DT:
        raise ValueError("试验时长须至少一个有限固定步")
    config = trial_config(case, enabled, mode)
    world, vehicle = _create_vehicle(config)
    if case == "split-mu-brake":
        vehicle.on_asphalt = lambda x, _y: x < 0
    try:
        if case == "airborne-recontact":
            pose = vehicle._chassis.getTransform()
            vehicle._chassis.setTransform(TransformState.makePosQuatScale(
                pose.getPos() + Vec3(0, 0, 2), pose.getQuat(), Vec3(1)))
        else:
            for _ in range(SETTLE_TICKS):
                _step(world, vehicle, VehicleCommand())
        speed = initial_speed(case)
        vehicle._chassis.setLinearVelocity(Vec3(0, speed, 0))
        vehicle.tires.initialize_rolling(speed)
        if case == "coast-disturbance":
            vehicle._chassis.setAngularVelocity(Vec3(0, 0, .5))
        state = vehicle.snapshot()
        start = previous_position = state.position
        previous_heading = state.heading
        heading = peak_heading = distance = peak_yaw = slip_integral = yaw_integral = 0.0
        active_ticks = abs_ticks = saturated_ticks = 0
        peak_residual_moment = 0.0
        airborne = [0] * 4
        recontacts = [0] * 4
        supported = [wheel.sample_support for wheel in state.wheel_dynamics]
        stopped_tick = stopped_distance = None
        rows = []

        def record(tick, phase, command, force_pose=None, force_contacts=(), force_tick=0):
            # dynamics来自施力前；完成步的角速度和侧偏另列，不能冒充同一时刻。
            yaw = float(vehicle._chassis.getAngularVelocity().z)
            velocity = vehicle._chassis.getTransform().getQuat().conjugate().xform(
                vehicle._chassis.getLinearVelocity())
            sideslip = math.atan2(float(velocity.x), abs(float(velocity.y))) if velocity.length() > .1 else 0.0
            reference = state.stability_state.reference_yaw_rate
            row = {"tick": tick, "time_s": tick * FIXED_DT, "phase": phase,
                   "completed_yaw_rate_radps": yaw, "completed_sideslip_rad": sideslip,
                   "completed_yaw_error_radps": reference-yaw,
                   "actual_powertrain_drive_torque_nm": vehicle.powertrain.drive_torque,
                   "horizontal_speed_mps": math.hypot(*state.velocity[:2]),
                   "path_distance_m": distance, "unwrapped_heading_change_deg": heading}
            _flatten("command", asdict(command), row)
            _flatten("state", asdict(state), row)
            moments = (tire_contact_moments(force_pose, force_contacts, force_tick, state.wheel_dynamics)
                       if force_pose is not None else [])
            for index in range(4):
                values = moments[index] if moments else {
                    "last_substep_fx_contact_yaw_nm": 0.0, "last_substep_fy_contact_yaw_nm": 0.0,
                    "last_substep_total_contact_yaw_nm": 0.0, "mean_fx_contact_yaw_nm": 0.0,
                    "mean_fy_contact_yaw_nm": 0.0, "mean_total_contact_yaw_nm": 0.0,
                    "force_contact_tick": 0}
                _flatten(f"tire_moment.{index}", values, row)
            row["mean_tire_contact_yaw_moment_nm"] = sum(
                value["mean_total_contact_yaw_nm"] for value in moments)
            row["last_substep_tire_contact_yaw_moment_nm"] = sum(
                value["last_substep_total_contact_yaw_nm"] for value in moments)
            rows.append(row)
            return yaw, sideslip, reference-yaw

        record(0, "initial", command_at(case, 0)[1])
        for tick in range(1, round(duration / FIXED_DT)+1):
            phase, command = command_at(case, (tick-1)*FIXED_DT)
            force_pose = vehicle._chassis.getTransform()
            force_contacts = vehicle._wheel_contacts
            force_tick = vehicle._contact_tick
            _step(world, vehicle, command)
            state = vehicle.snapshot()
            distance += math.hypot(state.position[0]-previous_position[0], state.position[1]-previous_position[1])
            previous_position = state.position
            heading += (state.heading-previous_heading+180) % 360-180
            previous_heading = state.heading
            peak_heading = max(peak_heading, abs(heading))
            yaw, sideslip, yaw_error = record(tick, phase, command, force_pose, force_contacts, force_tick)
            peak_yaw = max(peak_yaw, abs(yaw))
            slip_integral += abs(sideslip)*FIXED_DT
            yaw_integral += abs(yaw_error)*FIXED_DT
            active_ticks += int(state.stability_state.active)
            abs_ticks += int(any(brake.abs_active for brake in state.brake_states))
            residual = abs(state.stability_state.residual_moment)
            peak_residual_moment = max(peak_residual_moment, residual)
            saturated_ticks += int(state.stability_state.active and residual > 1.0)
            for index, wheel in enumerate(state.wheel_dynamics):
                airborne[index] += int(not wheel.sample_support)
                recontacts[index] += int(wheel.sample_support and not supported[index])
                supported[index] = wheel.sample_support
            if stopped_tick is None and rows[-1]["horizontal_speed_mps"] < .1:
                stopped_tick, stopped_distance = tick, distance
        return {"case": case, "mode": mode, "esc_enabled": enabled, "config": asdict(config),
                "ticks": tick, "elapsed_s": tick*FIXED_DT, "initial_speed_mps": speed,
                "final_horizontal_speed_mps": rows[-1]["horizontal_speed_mps"],
                "path_distance_m": distance, "stopped": stopped_tick is not None,
                "time_to_stop_s": stopped_tick*FIXED_DT if stopped_tick else None,
                "stopping_path_distance_m": stopped_distance,
                "longitudinal_displacement_m": state.position[1]-start[1],
                "lateral_displacement_m": state.position[0]-start[0],
                "heading_change_deg": heading, "peak_abs_unwrapped_heading_deg": peak_heading,
                "peak_abs_yaw_rate_radps": peak_yaw, "abs_sideslip_integral_rad_s": slip_integral,
                "abs_yaw_error_integral_rad": yaw_integral, "esc_active_seconds": active_ticks*FIXED_DT,
                "abs_active_seconds": abs_ticks*FIXED_DT,
                "allocation_residual_over_1nm_seconds": saturated_ticks*FIXED_DT,
                "peak_abs_allocation_residual_nm": peak_residual_moment,
                "airborne_wheel_seconds": [n*FIXED_DT for n in airborne],
                "recontact_counts": recontacts}, rows
    finally:
        vehicle.close()


def source_hashes():
    hashes = _source_hashes()
    for path in (Path(__file__), ROOT / "tools/physics/reference_ab.py"):
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with gzip.open(path, "wt", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_matrix(output, duration=6.0, cases=CASES, modes=MODES):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source = source_hashes()
    results = []
    pending = [(mode, case, label) for mode in modes for case in cases for label in ("A", "B")]
    try:
        for mode in modes:
            for case in cases:
                pair = {"mode": mode, "case": case}
                results.append(pair)
                for label, enabled in (("A", False), ("B", True)):
                    summary, rows = run_trial(case, enabled, duration, mode)
                    filename = f"{mode}-{case}-{label}.csv.gz"
                    write_csv(output / filename, rows)
                    pair[label] = {**summary, "csv_gz": filename}
                    pending.remove((mode, case, label))
                metrics = ("peak_abs_unwrapped_heading_deg", "peak_abs_yaw_rate_radps", "abs_sideslip_integral_rad_s",
                           "abs_yaw_error_integral_rad", "path_distance_m")
                pair["B_minus_A"] = {key: pair["B"][key]-pair["A"][key] for key in metrics}
                pair["not_improved_metrics"] = [key for key in metrics if pair["B"][key] >= pair["A"][key]]
    except Exception as error:
        failure = {"status": "failed", "failed_trial": pending[0], "not_run": pending[1:],
                   "error": f"{type(error).__name__}: {error}", "cases": results,
                   "source_sha256_before": source, "source_sha256_after": source_hashes()}
        (output / "summary.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        raise
    report = {"status": "completed", "source_sha256_before": source,
              "source_sha256_after": source_hashes(), "cases": results,
              "protocol": {
                  "observer": "simulation truth; no sensor estimator or real-car validation",
                  "world": "independent horizontal Bullet plane; gravity -9.81; no window",
                  "step_s": FIXED_DT, "sample_stride": 1, "settle_ticks": SETTLE_TICKS,
                  "airborne_settle_ticks": 0, "airborne_initial_height_offset_m": 2,
                  "initialization": "speed and pure rolling assigned once; initial coast yaw +0.5 rad/s; no runtime state edits",
                  "comparison": "same mode core car, initial conditions and commands; only esc_enabled differs; ABS/TCS on",
                  "completed_observation": "angular velocity read after Bullet step; heading unwrapped every tick; dynamics retained as pre-step diagnostics",
                  "yaw_error": "completed body yaw versus control reference from that step; control feedback tick retained",
                  "torque": "actual_powertrain_drive_torque_nm is delivered driveline torque, not inferred engine shaft torque; wheel torques retained",
                  "allocation_residual": "active allocation residual >1 Nm duration is diagnostic; full desired/baseline/allocated/residual moments retained every tick",
                  "tire_contact_moment": "pre-force pose and previous contacts; force_contact_tick verified; tangent/lateral match Tires.advance; projected on body up axis; last_substep from fx/fy, mean from cumulative impulses/dt at fixed sampled contact; excludes axle reaction, suspension, collision and other torques; not net body moment",
                  "scope": "mechanism evidence; all non-improvements retained; shorter stopping distance not required; not high fidelity acceptance",
                  "duration_s": duration, "stop": "first horizontal speed <0.1m/s recorded; all ticks continue"}}
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    args = parser.parse_args()
    run_matrix(args.output, args.duration, args.cases, args.modes)


if __name__ == "__main__":
    main()
