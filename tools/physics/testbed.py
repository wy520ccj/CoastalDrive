"""可重复的单车 Bullet 标准物理试验与结果对照。"""

import argparse
import csv
import hashlib
import importlib
import json
import math
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, Plane, Vec3

MASK = BitMask32.bit(0) | BitMask32.bit(1)
CASES = (
    "flat_acceleration",
    "steering_step",
    "corner_braking",
    "split_mu_braking",
    "circle_20m",
    "circle_40m",
    "circle_60m",
)
CAR = None
Control = None
FIXED_DT = None
Vehicle = None
forward = None
steering_limit = None
_loaded_source = None
_response_modules = ()
_tire_modules = ()


def _load_source(source_dir=None):
    global CAR, Control, FIXED_DT, Vehicle, forward, steering_limit
    global _loaded_source, _response_modules, _tire_modules
    if source_dir is None and _loaded_source is not None:
        return
    selected = Path(source_dir or Path(__file__).resolve().parents[2] / "src").resolve()
    if _loaded_source == selected:
        return
    if _loaded_source is not None:
        raise RuntimeError("不同 --source-dir 请在独立进程中运行，避免复用已导入的车辆模块")
    sys.path.insert(0, str(selected))
    vehicle_config = importlib.import_module("vehicle_config")
    vehicle_state = importlib.import_module("vehicle_state")
    vehicle = importlib.import_module("vehicle")
    # 历史源码边界：ARCH-01前后的模块布局明确不同，分别在独立进程中加载。
    if (selected / "driver_assist.py").is_file():
        _response_modules = ("driver_assist", "powertrain", "vehicle_steering")
    else:
        _response_modules = ("vehicle_response",)
    _tire_modules = (
        ("tire_forces", "wheel_dynamics", "vehicle_tires")
        if (selected / "vehicle_tires.py").is_file()
        else ()
    )
    if (selected / "tire_properties.py").is_file():
        _tire_modules = ("tire_properties", *_tire_modules)
    if (selected / "tire_compliance.py").is_file():
        _tire_modules = ("tire_compliance", *_tire_modules)
    if (selected / "tire_coupling.py").is_file():
        _tire_modules = ("tire_coupling", *_tire_modules)
    response_modules = [importlib.import_module(name) for name in _response_modules]
    CAR = vehicle_config.CAR
    Control = vehicle_state.Control
    FIXED_DT = vehicle_state.FIXED_DT
    forward = vehicle_state.forward
    Vehicle = vehicle.Vehicle
    steering_limit = response_modules[0].steering_limit
    _loaded_source = selected


def _world():
    _load_source()
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("testbed-ground")
    ground.addShape(BulletPlaneShape(Plane(Vec3(0, 0, 1), 0)))
    ground.setIntoCollideMask(MASK)
    world.attachRigidBody(ground)
    return world


def _command(case, tick, speed, config=None, input_config=None):
    seconds = tick * FIXED_DT
    if case == "flat_acceleration":
        return Control(throttle=1.0 if seconds < 12 else 0.0)
    if case == "steering_step":
        return Control(steering=0.18, throttle=0.15) if seconds >= 0.5 else Control()
    if case == "corner_braking":
        return Control(steering=0.18, throttle=0.15) if seconds < 1.5 else Control(steering=0.18, brake=0.7)
    if case.startswith("circle_"):
        radius = float(case.removeprefix("circle_").removesuffix("m"))
        speed_error = 20 / 3.6 - abs(speed)
        throttle = max(0.0, min(1.0, 0.12 + speed_error * 0.6))
        brake = max(0.0, min(1.0, (-speed_error - 0.2) * 0.8))
        selected = CAR if config is None else config
        wheel_angle = math.degrees(math.atan(selected.wheelbase / radius))
        limit = (steering_limit(abs(speed)) if input_config is None
                 else steering_limit(abs(speed), selected, input_config))
        return Control(steering=wheel_angle / limit, throttle=throttle, brake=brake)
    return Control(brake=1.0)


def _surface(case, x, _y):
    return case != "split_mu_braking" or x < 0


def _wheel_surface_types(vehicle):
    return tuple(
        "asphalt" if _surface("split_mu_braking", wheel.getRaycastInfo().getContactPointWs().x, 0) else "grass"
        for wheel in vehicle._vehicle.getWheels()
    )


def _initial_speed(case):
    if case.startswith("circle_"):
        return 20 / 3.6
    return 0.0 if case == "flat_acceleration" else 40 / 3.6 if case in ("steering_step", "corner_braking") else 100 / 3.6


def _duration(case):
    if case.startswith("circle_"):
        return 12
    return {"flat_acceleration": 12, "steering_step": 3.5, "corner_braking": 3.5, "split_mu_braking": 6}[case]


def _finite(value, path="root"):
    if isinstance(value, dict):
        for key, item in value.items():
            _finite(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _finite(item, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"非有限数值：{path}={value}")


def _flatten(value, prefix):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result.update(_flatten(item, f"{prefix}.{key}" if prefix else str(key)))
        return result
    if isinstance(value, (list, tuple)):
        result = {}
        for index, item in enumerate(value):
            result.update(_flatten(item, f"{prefix}.{index}" if prefix else str(index)))
        return result
    if value is None and prefix.endswith((".contact_point", ".contact_normal")):
        return {f"{prefix}.{index}": None for index in range(3)}
    return {prefix: value}


def _run_case(case, directory, stride=6, *, config=None, input_config=None, actuator_input=False):
    _load_source()
    if case not in CASES:
        raise ValueError(f"未知工况：{case}")
    world = _world()
    parameters = {} if config is None else {"config": config, "input_config": input_config}
    vehicle = Vehicle(world, lambda x, y: _surface(case, x, y), (0, 0, 0.55),
                      reverse_enabled=False, **parameters)
    try:
        for _ in range(240):
            previous = vehicle._chassis.getLinearVelocity()
            vehicle.apply_control(Control())
            world.doPhysics(FIXED_DT, 0, FIXED_DT)
            vehicle.after_step(previous)
        wheel_surfaces = _wheel_surface_types(vehicle) if case == "split_mu_braking" else ()
        velocity = Vec3(*forward(0)) * _initial_speed(case)
        vehicle._chassis.setLinearVelocity(velocity)
        if _tire_modules:
            vehicle.tires.initialize_rolling(_initial_speed(case))
            # 历史外部源码仍可能使用无实体轴的配置；其初值协议保持原版。
            if "input_shaft_enabled" in asdict(vehicle.config):
                vehicle.powertrain.initialize_rolling(_initial_speed(case))
        duration = _duration(case)
        total_ticks = round(duration / FIXED_DT)
        path_length = 0.0
        max_speed = 0.0
        max_lateral = 0.0
        max_abs_yaw_rate = 0.0
        max_abs_sideslip = 0.0
        max_braking = 0.0
        min_speed = float("inf")
        stopped_at = None
        yaw_change = 0.0
        previous_heading = vehicle.snapshot(include_wheels=False).heading
        rows = 0
        csv_path = directory / f"{case}.csv"
        state_schema = asdict(vehicle.snapshot())
        state_schema.pop("wheels")
        state_columns = _flatten(state_schema, "state")
        wheel_columns = {}
        for index, wheel in enumerate(vehicle.snapshot().wheels):
            wheel_columns.update(_flatten(asdict(wheel), f"wheel{index}"))
        fieldnames = ["time_s", "tick", "input.steering", "input.throttle", "input.brake",
                      *state_columns, *wheel_columns]
        command_type = importlib.import_module("vehicle_state").VehicleCommand if actuator_input else None
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for tick in range(total_ticks):
                state_before = vehicle.snapshot(include_wheels=False)
                control = _command(case, tick, state_before.speed, config, input_config)
                previous = vehicle._chassis.getLinearVelocity()
                if actuator_input:
                    angle = 0.0
                    if case.startswith("circle_"):
                        radius = float(case.removeprefix("circle_").removesuffix("m"))
                        angle = math.degrees(math.atan(config.wheelbase / radius))
                    elif control.steering:
                        angle = 2.0
                    control = command_type(angle, control.throttle, control.brake, 1)
                    vehicle.apply_command(control)
                else:
                    vehicle.apply_control(control)
                world.doPhysics(FIXED_DT, 0, FIXED_DT)
                vehicle.after_step(previous)
                state = vehicle.snapshot()
                state_data = asdict(state)
                wheel_data = [asdict(wheel) for wheel in state.wheels]
                _finite(state_data)
                _finite(wheel_data)
                # 大侧滑时车身前向速度可过零，但车仍在滑行；停车取水平速度模长。
                speed = math.hypot(*state.velocity[:2])
                path_length += math.dist(state_before.position[:2], state.position[:2])
                heading_delta = (state.heading - previous_heading + 180) % 360 - 180
                yaw_change += heading_delta
                previous_heading = state.heading
                max_speed = max(max_speed, speed)
                min_speed = min(min_speed, speed)
                max_lateral = max(max_lateral, abs(state.lateral_acceleration))
                max_abs_yaw_rate = max(max_abs_yaw_rate, abs(state.dynamics.yaw_rate))
                max_abs_sideslip = max(max_abs_sideslip, abs(state.dynamics.sideslip))
                max_braking = max(max_braking, abs(state.acceleration))
                if stopped_at is None and control.brake > 0 and speed < 0.1:
                    stopped_at = (tick + 1) * FIXED_DT
                stopping = case == "split_mu_braking" and tick > 12 and speed < 0.1
                if (tick + 1) % stride == 0 or tick == total_ticks - 1 or stopping:
                    row = {"time_s": f"{(tick + 1) * FIXED_DT:.12f}", "tick": tick + 1,
                           "input.steering": control.steering, "input.throttle": control.throttle,
                           "input.brake": control.brake}
                    state_data.pop("wheels")
                    row.update(_flatten(state_data, "state"))
                    for index, wheel in enumerate(wheel_data):
                        row.update(_flatten(wheel, f"wheel{index}"))
                    writer.writerow(row)
                    rows += 1
                if stopping:
                    break
        elapsed = (tick + 1) * FIXED_DT
        summary = {
            "case": case,
            "duration_s": elapsed,
            "ticks": tick + 1,
            "sample_stride_ticks": stride,
            "csv_rows": rows,
            "initial_speed_mps": _initial_speed(case),
            "target_radius_m": float(case.removeprefix("circle_").removesuffix("m")) if case.startswith("circle_") else None,
            "target_speed_mps": 20 / 3.6 if case.startswith("circle_") else None,
            "final_speed_mps": state.speed,
            "final_horizontal_speed_mps": math.hypot(*state.velocity[:2]),
            "max_speed_mps": max_speed,
            "min_speed_mps": min_speed,
            "path_length_m": path_length,
            "yaw_change_deg": yaw_change,
            "max_abs_yaw_rate_rad_s": max_abs_yaw_rate,
            "max_lateral_acceleration_mps2": max_lateral,
            "max_abs_sideslip_deg": max_abs_sideslip,
            "max_abs_acceleration_mps2": max_braking,
            "stopped_at_s": stopped_at,
            "wheel_surfaces": wheel_surfaces,
        }
        _finite(summary)
        return summary
    finally:
        vehicle.close()


def _git_sha():
    return subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def load_vehicle_config(path, selected):
    """JSON文件边界恢复不可变配置；嵌套电子配置继承选定车型。"""
    values = json.loads(Path(path).read_text(encoding="utf-8"))
    if "braking" in values:
        values["braking"] = replace(selected.braking, **values["braking"])
    if "stability" in values:
        values["stability"] = replace(selected.stability, **values["stability"])
    if "traction" in values:
        values["traction"] = replace(selected.traction, **values["traction"])
    if "torque_curve" in values:
        values["torque_curve"] = tuple(tuple(node) for node in values["torque_curve"])
    if "gear_ratios" in values:
        values["gear_ratios"] = tuple(values["gear_ratios"])
    for name in ("engine_axis", "input_shaft_axis"):
        if name in values:
            values[name] = tuple(values[name])
    for name in ("differential_damping", "differential_capacity", "downstream_inertias"):
        if name in values:
            values[name] = tuple(values[name])
    if "downstream_axes" in values:
        values["downstream_axes"] = tuple(tuple(axis) for axis in values["downstream_axes"])
    if "body_inertia" in values and values["body_inertia"] is not None:
        values["body_inertia"] = tuple(values["body_inertia"])
    return replace(selected, **values)


def run(output, cases=CASES, source_dir=None, label=None, *, driving_mode=None,
        vehicle_config=None, actuator_input=False):
    _load_source(source_dir)
    config = input_config = None
    if driving_mode is not None or vehicle_config is not None or actuator_input:
        if not (_loaded_source / "driving_modes.py").is_file():
            raise ValueError("选定的历史源码不提供模式/实例配置接口")
        selected = importlib.import_module("driving_modes").DrivingMode(driving_mode or "game")
        config, input_config = selected.vehicle_config, selected.input_config
        if vehicle_config is not None:
            config = load_vehicle_config(vehicle_config, config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    results = [_run_case(case, output, config=config, input_config=input_config,
                         actuator_input=actuator_input) for case in cases]
    metadata = {
        "config": asdict(CAR if config is None else config),
        "driving_mode": driving_mode or "game",
        "input_config": None if input_config is None else asdict(input_config),
        "input_path": "actuator" if actuator_input else "driver",
        "environment": {"gravity_mps2": [0, 0, -9.81], "plane": "infinite_horizontal", "split_mu_boundary_x_m": 0,
                        "collision_mask_bits": [0, 1], "surface_assignment": {"x<0": "asphalt", "x>=0": "grass"}},
        "physics_hz": 1 / FIXED_DT,
        "measurement": {
            "bullet_stepping": "exactly one supplied fixed 1/120 s step; max_substeps=0",
            "speed_extrema_and_stop": "horizontal velocity norm; stop <0.1 m/s",
            "final_speed_mps": "signed body longitudinal velocity",
        },
        "fixed_dt_s": FIXED_DT,
        "source_version": label or ("current-src" if source_dir is None else str(source_dir)),
        "git_sha": _git_sha(),
        "source_sha256": {
            name: hashlib.sha256((_loaded_source / f"{name}.py").read_bytes()).hexdigest()
            for name in ("vehicle", "vehicle_config", "vehicle_state", "vehicle_dynamics",
                         "vehicle_contacts", "vehicle_brakes", *_response_modules, *_tire_modules)
            if (_loaded_source / f"{name}.py").is_file()
        },
        "rolling_initialization": (
            "after setting chassis initial velocity, call vehicle.tires.initialize_rolling(speed) once; no runtime realignment"
            if _tire_modules
            else "legacy layout has no separate wheel spin state; no explicit rolling initialization"
        ),
        "sampling": {
            "physics_hz": 1 / FIXED_DT,
            "csv_every_completed_ticks": 6,
            "csv_hz": 1 / (6 * FIXED_DT),
            "state_fields": "asdict(snapshot), recursively flattened; wheel pose fields expanded separately",
            "finite_check": "every physics tick",
        },
        "commands": {
            "flat_acceleration": "throttle=1 for 12 s",
            "steering_step": "40 km/h initial; coast 0.5 s; steering=0.18, throttle=0.15 for 3 s",
            "corner_braking": "40 km/h initial; steering=0.18, throttle=0.15 for 1.5 s; steering=0.18, brake=0.7 for 2 s",
            "split_mu_braking": "100 km/h initial; brake=1 until stopped or 6 s; x<0 asphalt, x>=0 grass",
            "circle_20m": "20 km/h target; requested wheel angle=atan(wheelbase/20 m); 12 s",
            "circle_40m": "20 km/h target; requested wheel angle=atan(wheelbase/40 m); 12 s",
            "circle_60m": "20 km/h target; requested wheel angle=atan(wheelbase/60 m); 12 s",
        },
        "summaries": results,
    }
    if actuator_input:
        metadata["commands"].update(
            steering_step="40 km/h initial; coast 0.5 s; center rack request=2 deg, throttle=0.15 for 3 s",
            corner_braking="40 km/h initial; rack request=2 deg, throttle=0.15 for 1.5 s; rack=2 deg, brake=0.7 for 2 s",
        )
        metadata["measurement"]["input"] = "VehicleCommand, direct pedals and center rack degrees; direction=D"
        metadata["measurement"]["csv_input_steering_unit"] = "degrees"
    _finite(metadata)
    (output / "summary.json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    return metadata


def compare(baseline, candidate, output=None):
    base = json.loads(Path(baseline).read_text(encoding="utf-8"))
    cand = json.loads(Path(candidate).read_text(encoding="utf-8"))
    base_rows = {row["case"]: row for row in base["summaries"]}
    cand_rows = {row["case"]: row for row in cand["summaries"]}
    if base_rows.keys() != cand_rows.keys():
        raise ValueError("A/B工况集合不同，不能作有效对照")
    for key in ("environment", "physics_hz", "fixed_dt_s", "commands"):
        if base[key] != cand[key]:
            raise ValueError(f"A/B试验条件不同：{key}")
    if base.get("measurement") != cand.get("measurement"):
        raise ValueError("A/B测量定义不同：measurement")
    for case in base_rows:
        for key in ("initial_speed_mps", "target_radius_m", "target_speed_mps"):
            if base_rows[case][key] != cand_rows[case][key]:
                raise ValueError(f"A/B工况初始条件不同：{case}.{key}")
    fields = sorted(set.intersection(*(set(row) for row in base_rows.values()), *(set(row) for row in cand_rows.values())))
    base_config = _flatten(base["config"], "")
    cand_config = _flatten(cand["config"], "")
    config_delta = {key: cand_config[key] - base_config[key]
                    for key in base_config.keys() & cand_config.keys()
                    if isinstance(base_config[key], (int, float)) and isinstance(cand_config[key], (int, float))
                    and cand_config[key] != base_config[key]}
    result = {"baseline": str(baseline), "candidate": str(candidate),
              "baseline_source_version": base["source_version"], "candidate_source_version": cand["source_version"],
              "config_delta_candidate_minus_baseline": config_delta,
              "config_added_candidate": {key: cand_config[key] for key in cand_config.keys() - base_config.keys()},
              "config_removed_candidate": {key: base_config[key] for key in base_config.keys() - cand_config.keys()},
              "baseline_input_config": base.get("input_config"),
              "candidate_input_config": cand.get("input_config"),
              "baseline_input_path": base.get("input_path", "driver"),
              "candidate_input_path": cand.get("input_path", "driver"),
              "cases": {}}
    for case in sorted(base_rows.keys() & cand_rows.keys()):
        delta = {field: cand_rows[case][field] - base_rows[case][field]
                 for field in fields if isinstance(base_rows[case][field], (int, float)) and isinstance(cand_rows[case][field], (int, float))}
        result["cases"][case] = {"delta_candidate_minus_baseline": delta}
    _finite(result)
    serialized = json.dumps(result, indent=2, allow_nan=False)
    if output is not None:
        Path(output).write_text(serialized, encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description="确定性车辆 Bullet 标准试验")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--label")
    parser.add_argument("--driving-mode", choices=("game", "simulation"))
    parser.add_argument("--vehicle-config", type=Path, help="覆盖车辆设计值的JSON对象")
    parser.add_argument("--actuator-input", action="store_true", help="直接踏板和齿条角标准试验")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    if args.baseline is not None:
        if args.candidate is None:
            parser.error("compare 模式需要 --candidate")
        result = compare(args.baseline, args.candidate, args.output)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    if args.output is None:
        parser.error("运行试验必须指定 --output 新目录")
    source_dir = (args.source_dir or Path(__file__).resolve().parents[2] / "src").resolve()
    sys.path.insert(0, str(source_dir))
    result = run(args.output, args.cases, source_dir, args.label, driving_mode=args.driving_mode,
                 vehicle_config=args.vehicle_config, actuator_input=args.actuator_input)
    print(json.dumps(result["summaries"], indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
