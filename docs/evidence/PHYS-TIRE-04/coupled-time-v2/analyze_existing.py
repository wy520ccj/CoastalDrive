"""只读共同积分协议轨迹；用真实宏末量和控制数值比较，不比较索引。"""

import csv
import gzip
import hashlib
import json
from pathlib import Path

directory = Path(__file__).parent
ledger = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
rows_by_count = {}
trials = {}
for trial in ledger["trials"]:
    count = trial["micro_count"]
    child = directory / f"micro{count}"
    with gzip.open(child / "esc-macro.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows_by_count[count] = rows
    first_manifold = None
    final_body = None
    peak_world = peak_up = integral_world = integral_up = 0.0
    first_support = [None]*4
    contacts = [False]*4
    micro_recontacts = [0]*4
    micro_airborne = [0.0]*4
    with gzip.open(child / "micro.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            body = row["post_bullet_body"]
            final_body = body
            peak_world = max(peak_world, abs(body["yaw_world_z"]))
            peak_up = max(peak_up, abs(body["yaw_body_up"]))
            integral_world += abs(body["yaw_world_z"])*trial["micro_dt_s"]
            integral_up += abs(body["yaw_body_up"])*trial["micro_dt_s"]
            positive = [point for manifold in row["manifolds"] for point in manifold["points"] if point["normal_impulse_ns"] > 0]
            if positive and first_manifold is None:
                first_manifold = {"macro_tick": row["macro_tick"], "micro_index": row["micro_index"],
                                  "time_s": row["time_s"], "positive_point_count": len(positive), "points": positive,
                                  "pre_body": row["pre_bullet"]["body"], "post_body": body}
            for index, wheel in enumerate(row["completed_snapshot"]["wheel_dynamics"]):
                support = wheel["sample_support"]
                if support and first_support[index] is None:
                    first_support[index] = {"time_s": row["time_s"], "macro_tick": row["macro_tick"], "micro_index": row["micro_index"]}
                micro_recontacts[index] += int(support and not contacts[index])
                micro_airborne[index] += 0.0 if support else trial["micro_dt_s"]
                contacts[index] = support
    summary = trial["trial"]
    fields = ("heading_change_deg", "peak_abs_unwrapped_heading_deg", "path_distance_m",
              "time_to_stop_s", "stopping_path_distance_m", "final_horizontal_speed_mps", "esc_active_seconds", "abs_active_seconds")
    trials[str(count)] = {**{field: summary[field] for field in fields}, "final_macro_body": final_body,
                          "micro_peak_abs_world_yaw_radps": peak_world, "micro_peak_abs_body_up_yaw_radps": peak_up,
                          "micro_abs_world_yaw_integral_rad": integral_world, "micro_abs_body_up_yaw_integral_rad": integral_up,
                          "first_body_impulse": first_manifold, "first_micro_supported_sample": first_support,
                          "micro_true_recontact_counts": micro_recontacts, "micro_airborne_seconds": micro_airborne,
                          "controller_actual_calls": trial["controller_actual_calls"], "micro_dissipation_sum_j": trial["micro_dissipation_sum_j"],
                          "macro_residual_max_n": max(float(row[f"macro_micro_peak.{index}.force_residual_n"]) for row in rows[1:] for index in range(4)),
                          "raw_sha256": {name: hashlib.sha256((child / name).read_bytes()).hexdigest() for name in ("esc-macro.csv.gz", "micro.jsonl.gz", "summary.json")}}

comparisons = {}
for a, b in ((1, 2), (2, 4), (4, 8), (1, 8)):
    deltas = {field: trials[str(b)][field]-trials[str(a)][field] for field in (
        "heading_change_deg", "path_distance_m", "time_to_stop_s", "stopping_path_distance_m", "esc_active_seconds", "abs_active_seconds")}
    first = {}
    for name, fields in {
        "completed_world_yaw": ["completed_yaw_rate_radps"],
        "macro_position": [f"state.position.{axis}" for axis in range(3)],
        "macro_velocity": [f"state.velocity.{axis}" for axis in range(3)],
        "ABS_command": [f"state.brake_states.{index}.commanded" for index in range(4)],
        "ABS_pressure": [f"state.brake_states.{index}.pressure" for index in range(4)],
        "ABS_active": [f"state.brake_states.{index}.abs_active" for index in range(4)],
        "ESC_active": ["state.stability_state.active"],
        "ESC_request": [f"state.stability_state.brake_requests.{index}" for index in range(4)],
        "powertrain_actual_torque": ["actual_powertrain_drive_torque_nm"],
        "macro_sample_support": [f"state.wheel_dynamics.{index}.sample_support" for index in range(4)],
    }.items():
        first[name] = None
        for old, new in zip(rows_by_count[a], rows_by_count[b]):
            va, vb = [old[field] for field in fields], [new[field] for field in fields]
            if va != vb:
                first[name] = {"macro_tick": int(old["tick"]), "time_s": float(old["time_s"]), "A": va, "B": vb}
                break
    comparisons[f"{b}_minus_{a}"] = {"deltas": deltas, "first_exact_actual_value_difference": first}

report = {"scope": "integration prototype observation only; numeric first differences not acceptance cutoff; micro indices never used as physical divergence",
          "micro1_gate": ledger["micro1_baseline"], "source_unchanged": ledger["source_unchanged"],
          "column_phases": {
              "macro_completed": "state.position/heading/velocity/speed and completed_yaw/sideslip are true end of lastmicro=end macro; stop/path/heading in trial use macro samples",
              "lastmicro_force": "state.dynamics, fx/fy, force_kappa/alpha, force_patch_kappa/alpha, strain/energy/dissipation and tire_moment reflect lastmicro force phase; tire mean moment uses lastmicro impulse/microdt",
              "lastmicro_acceleration": "state.acceleration/lateral_acceleration use lastmicro pre/post velocity difference divided microdt; not macro-average acceleration; load filter evolves everymicro",
              "controller_macro_start": "five controller results sampled/advanced at macro firstmicro with macrodt, then held; ABS pressure and engine output held within macro, feedback_tick labels firstmicro previous completed micro",
              "macro_energy": "macro_micro_sum columns sum intrinsic dissipation for everymicro; original dissipation columns are lastmicro only; elastic_energy is stored energy at lastmicro end, not summed",
              "index_units": "CarState contact/sample/feedback_tick are micro indices while CSV tick/time are externalmacro indices/time"},
          "trials": trials, "comparisons": comparisons}
(directory / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
print(json.dumps({count: {"first_body_impulse_time": trial["first_body_impulse"]["time_s"],
                         "micro_contacts": trial["micro_true_recontact_counts"], "micro_airborne": trial["micro_airborne_seconds"]}
                  for count, trial in trials.items()}, indent=2))
print(json.dumps({name: {"deltas": data["deltas"], "first_difference_ticks": {key: value["macro_tick"] if value else None for key, value in data["first_exact_actual_value_difference"].items()}}
                  for name, data in comparisons.items()}, indent=2))
