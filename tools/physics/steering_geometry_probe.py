"""前轮转向几何定半径试验；轮胎侧向速度仅作刚体运动学诊断。"""

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

from panda3d.core import Quat, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from physics import testbed

INITIAL_SPEED_MPS = 2.77778
TARGET_SPEED_MPS = 10 / 3.6
TEST_WHEELBASE_M = 2.2
RADII_M = (6.0, 20.0)
SAMPLE_EVERY_TICKS = 6
TOTAL_TICKS = 12 * 120
WINDOW_START_S = 8.0
WINDOW_END_S = 12.0


def _cases():
    return tuple(
        (f"radius_{int(radius)}m_{side}", radius, sign)
        for radius in RADII_M
        for side, sign in (("positive", 1), ("negative", -1))
    )


def _control(center_angle_deg, speed):
    speed_error = TARGET_SPEED_MPS - abs(speed)
    throttle = max(0.0, min(1.0, 0.12 + speed_error * 0.6))
    brake = max(0.0, min(1.0, (-speed_error - 0.2) * 0.8))
    return testbed.Control(
        steering=center_angle_deg / testbed.steering_limit(abs(speed)),
        throttle=throttle,
        brake=brake,
    )


def _wheel_lateral_velocity(vehicle, index, actual_angle_deg, point):
    chassis = vehicle._chassis
    chassis_pose = chassis.getTransform()
    angular = chassis.getAngularVelocity()
    origin = chassis_pose.getPos()
    point_velocity = chassis.getLinearVelocity() + angular.cross(Vec3(*point) - origin)

    wheel_heading = -actual_angle_deg if index < 2 else 0.0
    wheel_rotation = Quat()
    wheel_rotation.setHpr(Vec3(wheel_heading, 0, 0))
    wheel_right_local = wheel_rotation.xform(Vec3(1, 0, 0))
    wheel_right_world = chassis_pose.getQuat().xform(wheel_right_local)
    return point_velocity.dot(wheel_right_world)


def _sample(vehicle, state):
    actual_angles = tuple(-vehicle._vehicle.getSteeringValue(index) for index in (0, 1))
    lateral_velocities = []
    contact_points = []
    for index, contact in enumerate(state.wheel_contacts):
        if contact.contact_point is None:
            contact_points.append((None, None, None))
            lateral_velocities.append(None)
        else:
            contact_points.append(contact.contact_point)
            angle = actual_angles[index] if index < 2 else 0.0
            lateral_velocities.append(_wheel_lateral_velocity(vehicle, index, angle, contact.contact_point))
    return actual_angles, tuple(contact_points), tuple(lateral_velocities)


def _run_case(case, radius, sign, output_dir):
    world = testbed._world()
    vehicle = testbed.Vehicle(world, lambda _x, _y: True, (0, 0, 0.55), reverse_enabled=False)
    center_angle = sign * math.degrees(math.atan(TEST_WHEELBASE_M / radius))
    try:
        for _ in range(240):
            previous = vehicle._chassis.getLinearVelocity()
            vehicle.apply_control(testbed.Control())
            world.doPhysics(testbed.FIXED_DT, 0, testbed.FIXED_DT)
            vehicle.after_step(previous)

        vehicle._chassis.setLinearVelocity(Vec3(*testbed.forward(0)) * INITIAL_SPEED_MPS)
        if testbed._tire_modules:
            vehicle.tires.initialize_rolling(INITIAL_SPEED_MPS)
        csv_path = output_dir / f"{case}.csv"
        fieldnames = [
            "time_s",
            "tick",
            "control.steering_fraction",
            "control.throttle",
            "control.brake",
            "speed_mps",
            "cg_horizontal_speed_mps",
            "yaw_rate_rad_s",
            "position_x_m",
            "position_y_m",
            "position_z_m",
            "roll_deg",
            "front_left_angle_deg",
            "front_right_angle_deg",
        ]
        for index in range(4):
            fieldnames.extend((
                f"wheel{index}_contact_x_m",
                f"wheel{index}_contact_y_m",
                f"wheel{index}_contact_z_m",
                f"wheel{index}_lateral_velocity_mps",
            ))

        count = 0
        speed_sum = 0.0
        longitudinal_speed_sum = 0.0
        yaw_sum = 0.0
        abs_yaw_sum = 0.0
        front_lateral_abs_sum = 0.0
        front_lateral_count = 0
        left_angle_sum = 0.0
        right_angle_sum = 0.0
        radius_sum = 0.0
        radius_count = 0
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for tick in range(TOTAL_TICKS):
                before = vehicle.snapshot(include_wheels=False)
                control = _control(center_angle, before.speed)
                previous = vehicle._chassis.getLinearVelocity()
                vehicle.apply_control(control)
                world.doPhysics(testbed.FIXED_DT, 0, testbed.FIXED_DT)
                vehicle.after_step(previous)
                state = vehicle.snapshot()
                actual_angles, contact_points, lateral_velocities = _sample(vehicle, state)
                time_s = (tick + 1) * testbed.FIXED_DT
                yaw_rate = state.dynamics.yaw_rate
                speed = math.hypot(*state.velocity[:2])
                testbed._finite(asdict(state))
                testbed._finite(actual_angles)
                testbed._finite(lateral_velocities)

                if WINDOW_START_S <= time_s <= WINDOW_END_S:
                    count += 1
                    speed_sum += speed
                    longitudinal_speed_sum += abs(state.speed)
                    yaw_sum += yaw_rate
                    abs_yaw_sum += abs(yaw_rate)
                    left_angle_sum += actual_angles[0]
                    right_angle_sum += actual_angles[1]
                    if abs(yaw_rate) > 0:
                        radius_sum += speed / abs(yaw_rate)
                        radius_count += 1
                    for lateral_velocity in lateral_velocities[:2]:
                        if lateral_velocity is not None:
                            front_lateral_abs_sum += abs(lateral_velocity)
                            front_lateral_count += 1

                if (tick + 1) % SAMPLE_EVERY_TICKS == 0:
                    row = {
                        "time_s": f"{time_s:.12f}",
                        "tick": tick + 1,
                        "control.steering_fraction": control.steering,
                        "control.throttle": control.throttle,
                        "control.brake": control.brake,
                        "speed_mps": state.speed,
                        "cg_horizontal_speed_mps": speed,
                        "yaw_rate_rad_s": yaw_rate,
                        "position_x_m": state.position[0],
                        "position_y_m": state.position[1],
                        "position_z_m": state.position[2],
                        "roll_deg": state.roll,
                        "front_left_angle_deg": actual_angles[0],
                        "front_right_angle_deg": actual_angles[1],
                    }
                    for index, (point, lateral_velocity) in enumerate(zip(contact_points, lateral_velocities)):
                        row[f"wheel{index}_contact_x_m"] = point[0]
                        row[f"wheel{index}_contact_y_m"] = point[1]
                        row[f"wheel{index}_contact_z_m"] = point[2]
                        row[f"wheel{index}_lateral_velocity_mps"] = lateral_velocity
                    testbed._finite(row)
                    writer.writerow(row)

        mean_speed = speed_sum / count
        mean_yaw = yaw_sum / count
        mean_abs_yaw = abs_yaw_sum / count
        rear_radius = TEST_WHEELBASE_M / math.tan(abs(math.radians(center_angle)))
        summary = {
            "case": case,
            "target_radius_rear_axle_m": radius,
            "turn_sign": sign,
            "target_speed_mps": TARGET_SPEED_MPS,
            "initial_speed_mps": INITIAL_SPEED_MPS,
            "center_angle_deg": center_angle,
            "window_s": [WINDOW_START_S, WINDOW_END_S],
            "window_ticks": count,
            "mean_speed_mps": mean_speed,
            "mean_longitudinal_speed_mps": longitudinal_speed_sum / count,
            "mean_yaw_rate_rad_s": mean_yaw,
            "mean_abs_yaw_rate_rad_s": mean_abs_yaw,
            "effective_cg_radius_m": mean_speed / mean_abs_yaw if mean_abs_yaw > 0 else None,
            "mean_instantaneous_cg_radius_m": radius_sum / radius_count if radius_count else None,
            "expected_cg_radius_m": math.sqrt(rear_radius**2 + (TEST_WHEELBASE_M / 2) ** 2),
            "mean_front_lateral_velocity_abs_mps": (
                front_lateral_abs_sum / front_lateral_count if front_lateral_count else None
            ),
            "front_lateral_velocity_samples": front_lateral_count,
            "mean_front_left_angle_deg": left_angle_sum / count,
            "mean_front_right_angle_deg": right_angle_sum / count,
        }
        testbed._finite(summary)
        return summary
    finally:
        vehicle.close()


def _source_sha256():
    source_dir = testbed._loaded_source
    names = (
        "vehicle",
        "vehicle_config",
        "vehicle_state",
        "vehicle_dynamics",
        "vehicle_contacts",
        *testbed._response_modules,
        *testbed._tire_modules,
    )
    return {
        name: hashlib.sha256((source_dir / f"{name}.py").read_bytes()).hexdigest()
        for name in names
        if (source_dir / f"{name}.py").is_file()
    }


def run(output, source_dir=None, label=None):
    testbed._load_source(source_dir)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    summaries = [_run_case(case, radius, sign, output) for case, radius, sign in _cases()]
    metadata = {
        "label": label or ("current-src" if source_dir is None else str(source_dir)),
        "git_sha": testbed._git_sha(),
        "source_sha256": _source_sha256(),
        "config": asdict(testbed.CAR),
        "physics_hz": 1 / testbed.FIXED_DT,
        "fixed_dt_s": testbed.FIXED_DT,
        "environment": {
            "world": "independent BulletWorld",
            "ground": "infinite horizontal plane",
            "gravity_mps2": [0, 0, -9.81],
            "collision_mask_bits": [0, 1],
        },
        "inputs": {
            "wheelbase_m": TEST_WHEELBASE_M,
            "radii_at_rear_axle_m": list(RADII_M),
            "turn_signs": {"positive": 1, "negative": -1},
            "initial_speed_mps": INITIAL_SPEED_MPS,
            "target_speed_mps": TARGET_SPEED_MPS,
            "settle_ticks": 240,
            "duration_s": TOTAL_TICKS * testbed.FIXED_DT,
            "sample_every_ticks": SAMPLE_EVERY_TICKS,
            "proportional_speed_control": {
                "throttle_bias": 0.12, "throttle_gain": 0.6,
                "brake_deadband_mps": 0.2, "brake_gain": 0.8,
            },
            "steering": "center_angle / steering_limit(abs(speed)); no path correction",
            "summary_window_s": [WINDOW_START_S, WINDOW_END_S],
        },
        "rolling_initialization": (
            "after setting chassis initial velocity, call vehicle.tires.initialize_rolling(speed) once; no runtime realignment"
            if testbed._tire_modules
            else "legacy layout has no separate wheel spin state; no explicit rolling initialization"
        ),
        "sampling": {
            "physics_hz": 1 / testbed.FIXED_DT,
            "csv_every_completed_ticks": SAMPLE_EVERY_TICKS,
            "csv_hz": 1 / (SAMPLE_EVERY_TICKS * testbed.FIXED_DT),
            "summary_window_accumulation": "every physics tick with timestamp in [8, 12] seconds",
        },
        "wheel_lateral_velocity_definition": (
            "rigid-body contact-point velocity projected onto each wheel-plane lateral axis; "
            "kinematic lateral velocity only, not tire alpha or wheel speed"
        ),
        "summaries": summaries,
    }
    testbed._finite(metadata)
    (output / "summary.json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description="前轮转向几何定半径试验")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--label")
    args = parser.parse_args()
    source_dir = args.source_dir.resolve() if args.source_dir else None
    result = run(args.output, source_dir, args.label)
    print(json.dumps(result["summaries"], indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
