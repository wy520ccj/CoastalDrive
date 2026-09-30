"""研究独立轮速轮胎模型的Bullet整车响应，不作为玩家性能验收。"""

import argparse
import csv
import hashlib
import importlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.core import TransformState, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from physics import testbed

CONFIGS = tuple(
    {"tire_substeps": substeps, "rear_lateral_stiffness": stiffness}
    for substeps in (2, 8)
    for stiffness in (50000.0, 60000.0)
)
CASES = ("asphalt_disturbance", "asphalt_traction", "grass_traction", "asphalt_braking", "grade_braking")
DT = 1 / 120
VehicleCommand = None


def _plane_world(pitch_degrees=0.0):
    world = testbed._world()
    if pitch_degrees:
        ground = world.getRigidBodies()[0]
        world.removeRigidBody(ground)
        ground.setTransform(TransformState.makeHpr(Vec3(0, pitch_degrees, 0)))
        world.attachRigidBody(ground)
    return world


def _case_setup(case):
    if case == "asphalt_disturbance":
        return {"surface": True, "duration_s": 8.0, "speed_mps": 150 / 3.6,
                "lateral_mps": 0.02, "yaw_rate_rad_s": 0.001, "pitch_deg": 0.0}
    if case in ("asphalt_traction", "grass_traction"):
        return {"surface": case == "asphalt_traction", "duration_s": 4.0, "speed_mps": 0.0,
                "lateral_mps": 0.0, "yaw_rate_rad_s": 0.0, "pitch_deg": 0.0}
    if case == "asphalt_braking":
        return {"surface": True, "duration_s": 6.0, "speed_mps": 100 / 3.6,
                "lateral_mps": 0.0, "yaw_rate_rad_s": 0.0, "pitch_deg": 0.0}
    return {"surface": True, "duration_s": 10.0, "speed_mps": 0.0,
            "lateral_mps": 0.0, "yaw_rate_rad_s": 0.0, "pitch_deg": 5.0}


def _command(case, time_s):
    if case == "asphalt_disturbance":
        return VehicleCommand(steering=0.0, throttle=0.15, brake=0.0, direction=1), "held_throttle"
    if case in ("asphalt_traction", "grass_traction"):
        if time_s < 3.0:
            return VehicleCommand(steering=0.0, throttle=1.0, brake=0.0, direction=1), "full_throttle"
        return VehicleCommand(steering=0.0, throttle=0.0, brake=0.0, direction=1), "coast"
    if case == "asphalt_braking":
        return VehicleCommand(steering=0.0, throttle=0.0, brake=1.0, direction=0), "full_brake"
    return VehicleCommand(steering=0.0, throttle=0.0, brake=1.0, direction=0), "grade_brake"


def _source_sha256():
    source = testbed._loaded_source
    modules = (
        "vehicle",
        "vehicle_config",
        "vehicle_state",
        "vehicle_dynamics",
        "vehicle_contacts",
        *testbed._response_modules,
        *testbed._tire_modules,
    )
    return {
        name: hashlib.sha256((source / f"{name}.py").read_bytes()).hexdigest()
        for name in modules
        if (source / f"{name}.py").is_file()
    }


def _config_label(config_values):
    return f"substeps{config_values['tire_substeps']}_rear{int(config_values['rear_lateral_stiffness'] / 1000)}k"


def _run_trial(case, config_values, output):
    settings = _case_setup(case)
    trial_config = replace(testbed.CAR, **config_values)
    world = _plane_world(settings["pitch_deg"])
    vehicle = testbed.Vehicle(
        world,
        lambda _x, _y: settings["surface"],
        (0, 0, 0.55),
        pitch=settings["pitch_deg"],
        reverse_enabled=False,
    )
    tire_module = importlib.import_module("vehicle_tires")
    vehicle_command = importlib.import_module("vehicle_state").VehicleCommand
    settle_command = (
        vehicle_command(brake=1.0, direction=0)
        if case == "grade_braking"
        else vehicle_command()
    )
    try:
        for _ in range(240):
            previous = vehicle._chassis.getLinearVelocity()
            vehicle.apply_command(settle_command)
            world.doPhysics(DT, 0, DT)
            vehicle.after_step(previous)

        vehicle.tires = tire_module.Tires(trial_config)
        start_position = vehicle._chassis.getTransform().getPos()
        start_quaternion = vehicle._chassis.getTransform().getQuat()
        forward_world = start_quaternion.xform(Vec3(0, 1, 0))
        right_world = start_quaternion.xform(Vec3(1, 0, 0))
        velocity = forward_world * settings["speed_mps"] + right_world * settings["lateral_mps"]
        vehicle._chassis.setLinearVelocity(velocity)
        vehicle._chassis.setAngularVelocity(Vec3(0, 0, settings["yaw_rate_rad_s"]))
        vehicle.tires.initialize_rolling(settings["speed_mps"])

        total_ticks = round(settings["duration_s"] / DT)
        stop_tick = None
        peak_speed = 0.0
        peak_abs_yaw = 0.0
        peak_abs_kappa = 0.0
        peak_wheel_omega = 0.0
        peak_abs_force = 0.0
        peak_solver_residual = 0.0
        supported_wheel_ticks = 0
        grass_spin_ticks = 0
        locked_slip_ticks = 0
        accumulated_slip_ratio = 0.0
        initial_lateral_speed = settings["lateral_mps"]
        final_lateral_speed = initial_lateral_speed
        initial_position = tuple(start_position)
        final_position = initial_position
        csv_path = output / f"{_config_label(config_values)}_{case}.csv"

        initial_schema = asdict(vehicle.snapshot())
        initial_schema.pop("wheels")
        flattened_state = testbed._flatten(initial_schema, "state")
        fieldnames = ["time_s", "tick", "phase", "command.steering_deg", "command.throttle",
                      "command.brake", "command.direction", *flattened_state]
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for tick in range(total_ticks):
                time_s = tick * DT
                command, phase = _command(case, time_s)
                previous = vehicle._chassis.getLinearVelocity()
                vehicle.apply_command(command)
                world.doPhysics(DT, 0, DT)
                vehicle.after_step(previous)
                state = vehicle.snapshot()
                state_data = asdict(state)
                state_data.pop("wheels")
                testbed._finite(state_data)

                velocity_world = vehicle._chassis.getLinearVelocity()
                transform = vehicle._chassis.getTransform()
                velocity_local = transform.getQuat().conjugate().xform(velocity_world)
                final_lateral_speed = float(velocity_local.x)
                final_position = tuple(transform.getPos())
                horizontal_speed = math.hypot(velocity_world.x, velocity_world.y)
                peak_speed = max(peak_speed, horizontal_speed)
                peak_abs_yaw = max(peak_abs_yaw, abs(state.dynamics.yaw_rate))
                wheel_states = vehicle.tires.states
                for wheel_state in wheel_states:
                    if wheel_state.road_support:
                        supported_wheel_ticks += 1
                        if wheel_state.kappa is not None:
                            peak_abs_kappa = max(peak_abs_kappa, abs(wheel_state.kappa))
                            accumulated_slip_ratio += abs(wheel_state.kappa)
                            if case in ("asphalt_traction", "grass_traction") and wheel_state.drive_torque:
                                grass_spin_ticks += abs(wheel_state.kappa) >= 0.2
                            if case == "asphalt_braking" and wheel_state.kappa <= -0.95:
                                locked_slip_ticks += 1
                    peak_wheel_omega = max(peak_wheel_omega, abs(wheel_state.omega))
                    peak_abs_force = max(peak_abs_force, math.hypot(wheel_state.fx, wheel_state.fy))
                    peak_solver_residual = max(peak_solver_residual, abs(wheel_state.force_residual))

                if case == "asphalt_braking" and stop_tick is None and horizontal_speed < 0.1:
                    stop_tick = tick + 1
                if (tick + 1) % 6 == 0 or tick == total_ticks - 1 or stop_tick == tick + 1:
                    row = {
                        "time_s": f"{(tick + 1) * DT:.12f}",
                        "tick": tick + 1,
                        "phase": phase,
                        "command.steering_deg": command.steering,
                        "command.throttle": command.throttle,
                        "command.brake": command.brake,
                        "command.direction": command.direction,
                    }
                    row.update(testbed._flatten(state_data, "state"))
                    testbed._finite(row)
                    writer.writerow(row)
                if case == "asphalt_braking" and stop_tick is not None:
                    break

        grade_displacement = None
        if case == "grade_braking":
            slope_tangent = Vec3(0, math.cos(math.radians(5)), math.sin(math.radians(5)))
            grade_displacement = (Vec3(*final_position) - Vec3(*initial_position)).dot(slope_tangent)
        result = {
            "status": "completed",
            "case": case,
            "config_label": _config_label(config_values),
            "tire_substeps": config_values["tire_substeps"],
            "rear_lateral_stiffness": config_values["rear_lateral_stiffness"],
            "substep_dt_s": DT / config_values["tire_substeps"],
            "surface": "asphalt" if settings["surface"] else "grass",
            "duration_s": (tick + 1) * DT,
            "ticks": tick + 1,
            "stopped_at_s": stop_tick * DT if stop_tick is not None else None,
            "initial_speed_mps": settings["speed_mps"],
            "final_horizontal_speed_mps": horizontal_speed,
            "peak_horizontal_speed_mps": peak_speed,
            "initial_lateral_speed_mps": initial_lateral_speed,
            "final_lateral_speed_mps": final_lateral_speed,
            "initial_yaw_rate_rad_s": settings["yaw_rate_rad_s"],
            "final_yaw_rate_rad_s": state.dynamics.yaw_rate,
            "peak_abs_yaw_rate_rad_s": peak_abs_yaw,
            "initial_position": initial_position,
            "final_position": final_position,
            "grade_displacement_m": grade_displacement,
            "peak_abs_kappa": peak_abs_kappa,
            "mean_abs_supported_kappa": (
                accumulated_slip_ratio / supported_wheel_ticks if supported_wheel_ticks else None
            ),
            "peak_wheel_omega_rad_s": peak_wheel_omega,
            "peak_wheel_force_n": peak_abs_force,
            "peak_solver_residual_n": peak_solver_residual,
            "supported_wheel_ticks": supported_wheel_ticks,
            "drive_slip_wheel_ticks_kappa_ge_0_2": grass_spin_ticks,
            "brake_locked_slip_wheel_ticks_kappa_le_minus_0_95": locked_slip_ticks,
            "csv": csv_path.name,
        }
        testbed._finite(result)
        return result
    finally:
        vehicle.close()


def _run_matrix(output, quick=False):
    configs = CONFIGS[:1] if quick else CONFIGS
    cases = CASES[:1] if quick else CASES
    results = []
    for settings in configs:
        for case in cases:
            try:
                results.append(_run_trial(case, settings, output))
            except (ArithmeticError, ValueError, OverflowError) as error:
                results.append({
                    "status": "error",
                    "case": case,
                    "config_label": _config_label(settings),
                    "error_type": type(error).__name__,
                    "error": str(error),
                })
    return results


def _comparisons(results):
    by_condition = {(row.get("case"), row.get("rear_lateral_stiffness"), row.get("tire_substeps")): row
                    for row in results if row["status"] == "completed"}
    pairs = []
    for case in CASES:
        for stiffness in (50000.0, 60000.0):
            coarse = by_condition.get((case, stiffness, 2))
            fine = by_condition.get((case, stiffness, 8))
            if coarse and fine:
                pairs.append({
                    "case": case,
                    "rear_lateral_stiffness": stiffness,
                    "coarse_tire_substeps": 2,
                    "fine_tire_substeps": 8,
                    "fine_minus_coarse": {
                        key: fine[key] - coarse[key]
                        for key in ("final_horizontal_speed_mps", "peak_abs_yaw_rate_rad_s",
                                    "peak_abs_kappa", "peak_solver_residual_n")
                    },
                })
    return pairs


def run(output, source_dir=None, label=None, quick=False):
    testbed._load_source(source_dir)
    global VehicleCommand
    VehicleCommand = importlib.import_module("vehicle_state").VehicleCommand
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    results = _run_matrix(output, quick)
    metadata = {
        "label": label or ("current-src" if source_dir is None else str(source_dir)),
        "git_sha": testbed._git_sha(),
        "source_sha256": _source_sha256(),
        "global_config": asdict(testbed.CAR),
        "trial_config_variants": CONFIGS[:1] if quick else CONFIGS,
        "physics_hz": 1 / DT,
        "environment": {
            "ground": "infinite Bullet plane",
            "gravity_mps2": [0, 0, -9.81],
            "bullet_stepping": "world.doPhysics(DT, max_substeps=0, fixed_timestep=DT); exactly one supplied 1/120 s step per outer tick",
            "slope_plane_normal_for_grade_case": [0, -math.sin(math.radians(5)), math.cos(math.radians(5))],
            "all_other_conditions": "horizontal infinite plane",
        },
        "initialization": {
            "static_settle_ticks": 240,
            "trial_tires_replaced_only_after_settling": True,
            "rolling_speed_initialized_once_from_trial_initial_speed": True,
            "running_wheel_speed_alignment": False,
        },
        "sampling": {
            "csv_every_completed_ticks": 6,
            "csv_hz": 20,
            "state_data": "snapshot asdict recursively flattened, including per-wheel force/slip/spin fields",
            "finite_check": "every physics tick and emitted row",
        },
        "cases": {
            "asphalt_disturbance": "150 km/h, lateral 0.02 m/s, yaw 0.001 rad/s, rolling wheel speeds, throttle 0.15 for 8 s",
            "asphalt_traction": "asphalt full throttle from rest 3 s, then coast 1 s",
            "grass_traction": "grass full throttle from rest 3 s, then coast 1 s",
            "asphalt_braking": "asphalt 100 km/h, full brake until horizontal speed <0.1 m/s or 6 s",
            "grade_braking": "5 degree slope, static initial condition, full brake for 10 s",
        },
        "observations": results,
        "substep_comparisons": _comparisons(results),
        "interpretation": "研究观察值，无玩家性能通过阈值；轮胎积分残差仅作数值误差记录。",
    }
    testbed._finite(metadata)
    (output / "summary.json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description="独立轮速轮胎模型的Bullet整车研究探针")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--label")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    source_dir = args.source_dir.resolve() if args.source_dir else None
    result = run(args.output, source_dir, args.label, args.quick)
    print(json.dumps(result["observations"], indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
