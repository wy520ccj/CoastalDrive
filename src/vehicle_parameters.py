"""车辆工程文件边界：分组读写，物理核心继续直接使用VehicleConfig。"""

import json
from dataclasses import asdict, replace
from pathlib import Path

SCHEMA = "vehicle-engineering-v1"
PARAMETER_GROUPS = {
    "chassis": (
        "mass", "wheelbase", "track_width", "collision_half_width", "collision_half_length",
        "collision_half_height", "centered_collision_support", "body_center_height",
        "wheel_connection_height", "center_of_mass_height", "front_weight_share", "body_inertia",
        "angular_damping", "steering_degrees", "steering_rate", "steering_response", "steering_return",
        "air_density", "drag_coefficient", "frontal_area",
    ),
    "powertrain": (
        "torque_curve", "gear_ratios", "final_drive", "drivetrain_efficiency", "idle_rpm",
        "shift_time", "torque_response", "engine_braking", "finite_drivetrain", "front_drive_share",
        "differential_damping", "differential_capacity", "engine_inertia", "engine_axis",
        "input_shaft_enabled", "input_shaft_inertia", "input_shaft_axis", "synchronizer_capacity",
        "downstream_inertia_enabled", "downstream_inertias", "downstream_axes", "engine_idle_response",
        "engine_idle_torque_limit", "engine_redline_rpm", "clutch_capacity", "clutch_release_time",
        "clutch_engage_time", "clutch_launch_response", "max_speed", "reverse_speed", "reverse_force",
        "reverse_gear_ratio", "game_speed_limits",
    ),
    "tires": (
        "wheel_radius", "wheel_width", "wheel_shoulder_radius", "wheel_crown_height", "wheel_inertia",
        "longitudinal_stiffness", "lateral_stiffness", "rear_lateral_stiffness",
        "tire_peak_load_exponent", "longitudinal_load_exponent", "lateral_load_exponent",
        "tire_compliance", "wheel_rotor_transport", "tire_contact_stiffness", "tire_contact_damping",
        "tire_shape", "tire_curvature", "slip_speed", "static_contact_speed", "tire_substeps",
        "rolling_coefficient", "grass_rolling_coefficient", "wheel_rolling_resistance",
        "rolling_transition_speed", "road_friction", "grass_friction",
    ),
    "suspension": (
        "suspension_si_enabled", "suspension_coupled_enabled", "suspension_antiroll_rates",
        "suspension_stop_rates", "suspension_spring_rates", "suspension_compression_damping",
        "suspension_extension_damping", "suspension_stiffness", "suspension_compression",
        "suspension_relaxation", "suspension_travel", "suspension_force_limit",
    ),
    "electronics": ("brake_torque", "front_brake_share", "braking", "traction", "stability"),
}


def _parameters(document):
    """旧平面JSON保持原协议；工程文件按声明版本与分区恢复。"""
    if "schema" not in document:
        return document
    if document["schema"] != SCHEMA:
        raise ValueError(f"未知车辆工程格式：{document['schema']}")
    unknown = set(document) - {"schema", "parameters", "metadata"}
    if unknown:
        raise ValueError(f"未知车辆工程文件字段：{sorted(unknown)}")
    values = {}
    for group, parameters in document["parameters"].items():
        if group not in PARAMETER_GROUPS:
            raise ValueError(f"未知车辆参数分区：{group}")
        invalid = set(parameters) - set(PARAMETER_GROUPS[group])
        if invalid:
            raise ValueError(f"参数分区{group}包含不属于该分区的字段：{sorted(invalid)}")
        values.update(parameters)
    return values


def grouped_parameters(config):
    """导出完整硬件值；新增字段必须明确进入对应业务分区。"""
    values = asdict(config)
    names = tuple(name for group in PARAMETER_GROUPS.values() for name in group)
    if len(names) != len(set(names)) or set(names) != set(values):
        raise ValueError("工程分区必须唯一且完整覆盖车辆配置")
    return {group: {name: values[name] for name in names} for group, names in PARAMETER_GROUPS.items()}


def save_vehicle_config(path, config, *, metadata=None):
    """保存工程文件；metadata记录单位/定义/来源，加载时不参与机械状态。"""
    document = {"schema": SCHEMA, "parameters": grouped_parameters(config)}
    if metadata is not None:
        document["metadata"] = metadata
    Path(path).write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def load_vehicle_config(path, selected):
    """JSON文件边界恢复不可变配置；嵌套电子配置继承选定车型。"""
    values = _parameters(json.loads(Path(path).read_text(encoding="utf-8")))
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
    si_fields = ("suspension_spring_rates", "suspension_compression_damping", "suspension_extension_damping",
                 "suspension_antiroll_rates", "suspension_stop_rates")
    if "suspension_si_enabled" not in values:
        # 配置文件的单位版本边界：旧归一化字段仍选旧单位，显式硬件字段选SI。
        if any(name in values for name in si_fields):
            values["suspension_si_enabled"] = True
        elif any(name in values for name in ("suspension_stiffness", "suspension_compression", "suspension_relaxation")):
            values["suspension_si_enabled"] = False
    for name in si_fields:
        if name in values:
            values[name] = tuple(values[name])
    if "body_inertia" in values and values["body_inertia"] is not None:
        values["body_inertia"] = tuple(values["body_inertia"])
    return replace(selected, **values)

