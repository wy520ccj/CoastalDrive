"""只读mesh完整轨迹，列出子步/反馈差异与有限几何实际使用范围。"""

import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

directory = Path(__file__).parent
ledger = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
entries = {}
raw_rows = {}
for trial in ledger["trials"]:
    child = directory / trial["directory"]
    with gzip.open(child / "esc.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with gzip.open(child / "manifold.jsonl.gz", "rt", encoding="utf-8") as stream:
        observations = [json.loads(line) for line in stream]
    steps = trial["steps"]
    raw_rows[steps] = rows
    positive = [point for row in observations for manifold in row["manifolds"] for point in manifold["points"]
                if point["applied_normal_impulse_ns"] > 0]
    entry = {key: trial["trial"][key] for key in (
        "path_distance_m", "stopped", "time_to_stop_s", "stopping_path_distance_m", "heading_change_deg",
        "peak_abs_unwrapped_heading_deg", "final_horizontal_speed_mps", "esc_active_seconds", "abs_active_seconds",
        "recontact_counts", "airborne_wheel_seconds")}
    for name in ("yaw_world_z", "yaw_body_up"):
        values = [row["post_bullet"][name] for row in observations]
        entry[f"final_{name}_radps"] = values[-1]
        entry[f"peak_abs_{name}_radps"] = max(abs(value) for value in values)
        entry[f"abs_{name}_integral_rad"] = sum(abs(value)/120 for value in values)
    active_rays = [ray for row in observations for ray in row["post_bullet_raycast"] if ray["contact_flag"]]
    active_normals = [ray["contact_normal_ws"] for ray in active_rays]
    entry.update({
        "first_body_impulse_tick": trial["first_nonzero_manifold_impulse_tick"],
        "first_wheel_sample_support_tick": [next((int(row["tick"]) for row in rows if row[f"state.wheel_dynamics.{i}.sample_support"] == "True"), None) for i in range(4)],
        "energy": trial["energy"], "config": trial["trial"]["config"],
        "raw_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (child / "esc.csv.gz", child / "manifold.jsonl.gz", child / "summary.json")},
        "geometry": {
            "maximum_chassis_abs_xy_m": trial["maximum_abs_xy_m"],
            "maximum_contact_abs_xy_m": max((max(abs(point["position_world_on_b"][0]), abs(point["position_world_on_b"][1])) for point in positive), default=None),
            "maximum_valid_ray_contact_abs_xy_m": max((max(abs(ray["contact_point_ws"][0]), abs(ray["contact_point_ws"][1])) for ray in active_rays), default=None),
            "minimum_valid_ray_contact_distance_to_diagonal_m": min((abs(ray["contact_point_ws"][0]-ray["contact_point_ws"][1])/math.sqrt(2) for ray in active_rays), default=None),
            "minimum_contact_distance_to_shared_diagonal_m": min((abs(point["position_world_on_b"][0]-point["position_world_on_b"][1])/math.sqrt(2) for point in positive), default=None),
            "maximum_absolute_ground_contact_z_m": max((abs(point["position_world_on_b"][2]) for point in positive), default=None),
            "triangle_indices_at_positive_impulse": sorted({point["index_b"] for point in positive}),
            "ticks_two_triangle_indices_have_positive_impulses": [row["tick"] for row in observations if len({point["index_b"] for manifold in row["manifolds"] for point in manifold["points"] if point["applied_normal_impulse_ns"] > 0}) > 1],
            "all_active_raycast_normals_exact_up": all(normal == [0., 0., 1.] for normal in active_normals),
            "minimum_manifold_normal_z": min((point["normal_world_on_b"][2] for point in positive), default=None),
        }})
    entries[str(steps)] = entry

comparisons = {}
for a, b in ((2, 4), (4, 8), (8, 16), (2, 8), (2, 16)):
    differences = {key: entries[str(b)][key]-entries[str(a)][key] for key in (
        "path_distance_m", "heading_change_deg", "peak_abs_unwrapped_heading_deg",
        "final_yaw_world_z_radps", "final_yaw_body_up_radps", "abs_yaw_world_z_integral_rad", "abs_yaw_body_up_integral_rad")}
    for key in ("time_to_stop_s", "stopping_path_distance_m"):
        differences[key] = (entries[str(b)][key]-entries[str(a)][key]
                            if entries[str(a)][key] is not None and entries[str(b)][key] is not None else None)
    first = {}
    for name, fields in {
        "ABS_active": [f"state.brake_states.{i}.abs_active" for i in range(4)],
        "ABS_command": [f"state.brake_states.{i}.commanded" for i in range(4)],
        "ESC_active": ["state.stability_state.active"],
        "ESC_requests": [f"state.stability_state.brake_requests.{i}" for i in range(4)],
        "completed_world_yaw": ["completed_yaw_rate_radps"],
        "sample_support": [f"state.wheel_dynamics.{i}.sample_support" for i in range(4)],
    }.items():
        first[name] = None
        for old, new in zip(raw_rows[a], raw_rows[b]):
            va, vb = [old[field] for field in fields], [new[field] for field in fields]
            if va != vb:
                first[name] = {"tick": int(old["tick"]), "A": va, "B": vb}
                break
    comparisons[f"{b}_minus_{a}"] = {"deltas": differences, "first_exact_field_difference": first}

report = {"scope": "simulation truth geometry diagnostic; raw exact first differences are not acceptance thresholds; original plane results remain separate",
          "geometry": "two static horizontal triangles [-1000,1000]^2 z0, shared x=y diagonal, zero-thickness mesh; all original vehicle/inputs and solver10 retained",
          "frozen_source_unchanged": ledger["frozen_source_unchanged"], "trials": entries, "comparisons": comparisons}
(directory / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
print(json.dumps({steps: {key: entry[key] for key in ("heading_change_deg", "path_distance_m", "time_to_stop_s", "stopping_path_distance_m", "abs_active_seconds", "esc_active_seconds")}
                  for steps, entry in entries.items()}, indent=2))
print(json.dumps({name: data["deltas"] for name, data in comparisons.items()}, indent=2))
