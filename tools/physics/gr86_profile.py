"""按保存的原厂锚点与明确工程初值生成完整GR86硬件文件。"""

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
import itertools

from physics.export_reference import BRAKE_FIELDS, STABILITY_FIELDS, TRACTION_FIELDS, VEHICLE_FIELDS

from driving_modes import REFERENCE_CAR
from vehicle_parameters import save_vehicle_config

PROFILE_ID = "gr86-2022-premium-6mt"
PROFILE_PATH = ROOT / "assets/game/vehicle-configs" / (PROFILE_ID + ".json")


def interpolate(points, x):
    for (x0, y0), (x1, y1) in itertools.pairwise(points):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    raise ValueError("扭矩图插值坐标超过已保存范围")


def generate(output):
    evidence = ROOT / "docs/evidence/PHYS-REAL-01"
    source = json.loads((evidence / "source-preparation.json").read_text(encoding="utf-8"))
    graphic = json.loads((evidence / "torque-graphic-vectors.json").read_text(encoding="utf-8"))
    prior = json.loads((evidence / "inertia-partition.json").read_text(encoding="utf-8"))
    fields, anchors = source["manufacturer_fields"], source["derived_anchors"]
    points = graphic["red_path_xy_points"]
    peak_x, peak_y = min(points, key=lambda point: point[1])
    labels = graphic["axis_label_bboxes"]
    x1000 = (labels["1000"][0] + labels["1000"][2]) / 2
    x7000 = (labels["7000"][0] + labels["7000"][2]) / 2
    rated_y = interpolate(points, x7000)
    peak, rated = anchors["peak_torque_nm"], anchors["torque_at_rated_power_nm"]
    torque_scale = (peak - rated) / (rated_y - peak_y)
    curve = []
    for x, y in points:
        rpm = (1000 + (x - x1000) * 2700 / (peak_x - x1000) if x <= peak_x
               else 3700 + (x - peak_x) * 3300 / (x7000 - peak_x))
        if rpm < 7500:
            curve.append((rpm, peak - (y - peak_y) * torque_scale))
    curve.append((7000., rated))
    x7500 = peak_x + (7500 - 3700) * (x7000 - peak_x) / 3300
    curve.append((7500., peak - (interpolate(points, x7500) - peak_y) * torque_scale))
    curve.sort()

    mass, radius, share = source["published_test"]["si_mass_kg"], anchors["unloaded_nominal_tire_radius_m"], fields["front_weight_share"]["value"]
    heave_hz, compression_ratio, extension_ratio = 1.7, .35, .60
    frequency = math.tau * heave_hz
    corner_masses = (mass * share / 2,) * 2 + (mass * (1 - share) / 2,) * 2
    springs = tuple(m * frequency ** 2 for m in corner_masses)
    compression = tuple(2 * compression_ratio * m * frequency for m in corner_masses)
    extension = tuple(2 * extension_ratio * m * frequency for m in corner_masses)
    static_compression = 9.81 / frequency ** 2
    inertia_case, = (case for case in prior["cases"] if case["assumed_center_of_mass_height_m"] == .45)
    values = {
        "mass": mass, "torque_curve": tuple(curve), "gear_ratios": tuple(fields["gear_ratios"]["value"]),
        "reverse_gear_ratio": fields["reverse_ratio"]["value"], "final_drive": fields["final_drive"]["value"],
        "wheelbase": fields["wheelbase"]["value"] / 1000, "track_width": fields["front_track"]["value"] / 1000,
        "axle_track_widths": (fields["front_track"]["value"] / 1000, fields["rear_track"]["value"] / 1000),
        "front_weight_share": share, "center_of_mass_height": .45,
        "body_inertia": tuple(inertia_case["candidate_body_inertia_xyz_kg_m2"]),
        "wheel_radius": radius, "wheel_width": .215, "drag_coefficient": .276,
        "frontal_area": .84 * fields["width"]["value"] / 1000 * fields["height"]["value"] / 1000,
        "collision_half_width": 1.015, "collision_half_length": 2.13256,
        "collision_half_height": .59, "body_center_height": .72,
        "wheel_connection_height": radius + .4 - static_compression,
        "steering_degrees": anchors["nominal_center_steering_limit_deg"],
        "suspension_spring_rates": springs, "suspension_compression_damping": compression,
        "suspension_extension_damping": extension, "suspension_stop_rates": tuple(10 * k for k in springs),
        "idle_rpm": 900., "engine_redline_rpm": 7500.,
        "differential_damping": (0., 600., 0.), "differential_capacity": (0., 2000., 0.),
        "axle_torque_bias_ratios": (1., 2.5),
        "brake_torque": mass * 9.81 * radius * 1.25, "front_brake_share": .70,
        "road_friction": 1.05, "longitudinal_stiffness": 60000. * mass / 1200,
        "lateral_stiffness": 50000. * mass / 1200, "rear_lateral_stiffness": 50000. * mass / 1200,
    }
    config = replace(REFERENCE_CAR, **values)
    manufacturer = {"gear_ratios", "reverse_gear_ratio", "final_drive", "wheelbase", "track_width",
                    "axle_track_widths", "front_weight_share", "wheel_width", "drag_coefficient"}
    derived = {"torque_curve", "wheel_radius", "steering_degrees"}
    metadata = {
        "design_id": PROFILE_ID, "version": "engineering-r2", "kind": "sourced_vehicle",
        "candidate": source["candidate"], "sources": source["sources"],
        "status": "complete loadable engineering candidate; dynamic calibration pending",
        "performance_targets": source["published_test"],
        "torque_derivation": {"method": "piecewise RPM map through 1000/3700/7000; graphic ordinate scaled through exact torque/power ratings",
                              "peak_torque_N_m": peak, "peak_rpm": 3700., "torque_at_7000_N_m": rated,
                              "input_graph_sha256": hashlib.sha256((evidence / "torque-graphic-vectors.json").read_bytes()).hexdigest()},
        "suspension_prior": {"heave_frequency_hz": heave_hz, "compression_damping_ratio": compression_ratio,
                             "extension_damping_ratio": extension_ratio, "static_compression_m": static_compression,
                             "rest_length_m": .4, "definition": "whole mass supported by four axial springs; current core has no independent unsprung mass"},
        "inertia_prior_sha256": hashlib.sha256((evidence / "inertia-partition.json").read_bytes()).hexdigest(),
        "geometry": {"OEM_width_without_mirrors_m": 1.775, "full_approximate_asset_width_m": 2.03,
                     "collider_basis": "full imported visual body including mirrors; nominal OEM width kept separate"},
        "differential": {"OEM_type": "Torsen", "current_model": "regularized torque-bias friction with real terminal axle load",
                         "rear_TBR_model": 2.5, "rear_regularization_N_m_s_rad": 600.,
                         "status": "load-dependent model; TBR and regularization are engineering priors, not published OEM values",
                         "source": "https://torsen.com/how-it-works/", "drive_and_coast_bias": "same ratio in this model"},
        "payload": {"curb_mass_kg": mass, "driver_equipment_kg": 0., "status": "published test payload not reported; curb-mass protocol explicit"},
        "vehicle_fields": {}, "nested_field_metadata": {},
    }
    for name, value in asdict(config).items():
        unit, definition = VEHICLE_FIELDS[name]
        status = "manufacturer" if name in manufacturer else "measured" if name == "mass" else "derived" if name in derived else "engineering_prior"
        metadata["vehicle_fields"][name] = {"unit": unit, "definition": definition, "status": status,
                                            "value": value, "basis": "saved matched-version sources" if status != "engineering_prior"
                                            else "explicit generic mechanism or engineering initial value; not OEM measurement"}
    for group, definitions in (("braking", BRAKE_FIELDS), ("traction", TRACTION_FIELDS), ("stability", STABILITY_FIELDS)):
        metadata["nested_field_metadata"][group] = {name: {"unit": unit, "definition": definition, "status": "engineering_prior"}
                                                    for name, (unit, definition) in definitions.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    save_vehicle_config(output, config, metadata=metadata)
    print(json.dumps({"profile": str(output), "fields": len(metadata["vehicle_fields"]),
                      "peak_torque_N_m": peak, "rated_power_W": rated * math.tau * 7000 / 60,
                      "static_compression_m": static_compression}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROFILE_PATH)
    generate(parser.parse_args().output)
