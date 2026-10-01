"""从已完成原始CSV提取控制误差与真实接点制动力矩，另存衍生结果。"""

import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
report = json.loads((ROOT / "matrix-final/summary.json").read_text(encoding="utf-8"))
results = []
for pair in report["cases"]:
    result = {"mode": pair["mode"], "case": pair["case"]}
    for label in ("A", "B"):
        path = ROOT / "matrix-final" / pair[label]["csv_gz"]
        with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        beta_error = sum(abs(float(row["state.stability_state.sideslip_error"])) / 120 for row in rows[1:])
        moving_beta_error = sum(abs(float(row["state.stability_state.sideslip_error"])) / 120
                                for row in rows[1:] if abs(float(row["state.speed"])) >= 1.5)
        active = [row for row in rows[1:] if row["state.stability_state.active"] == "True"]
        requests = [float(row["state.stability_state.desired_brake_moment"]) for row in active]
        actual = [sum(float(row[f"tire_moment.{i}.mean_fx_contact_yaw_nm"]) for i in range(4)) for row in active]
        result[label] = {
            "raw_sideslip_integral_rad_s": pair[label]["abs_sideslip_integral_rad_s"],
            "control_sideslip_error_integral_rad_s": beta_error,
            "moving_sideslip_error_integral_rad_s": moving_beta_error,
            "yaw_error_integral_rad": pair[label]["abs_yaw_error_integral_rad"],
            "peak_heading_deg": pair[label]["peak_abs_unwrapped_heading_deg"],
            "stopping_path_distance_m": pair[label]["stopping_path_distance_m"],
            "active_ticks": len(active),
            "torque_scale_min": min(float(row["state.stability_state.torque_scale"]) for row in rows),
            "desired_and_actual_longitudinal_moment_same_sign_ticks": sum(a * b > 0 for a, b in zip(requests, actual)),
            "actual_longitudinal_yaw_moment_peak_abs_nm": max(map(abs, actual), default=0),
            "allocation_residual_over_1nm_seconds": pair[label]["allocation_residual_over_1nm_seconds"],
            "peak_allocation_residual_nm": pair[label]["peak_abs_allocation_residual_nm"],
            "rows": len(rows), "csv_gz_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    results.append(result)

output = {"cases": results,
          "interpretation": "Pressure lag, ABS, joint slip and existing driver brakes can make actual longitudinal moment differ from desired moment. Contact-only projected moment excludes suspension, axle reaction, collision and external loads; sign count is diagnostic, not a universal correctness gate.",
          "matrix_source_unchanged": report["source_sha256_before"] == report["source_sha256_after"]}
(ROOT / "derived-results.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
for case in results:
    a, b = case["A"], case["B"]
    print(case["mode"], case["case"],
          "heading", round(a["peak_heading_deg"], 3), round(b["peak_heading_deg"], 3),
          "yaw_error", round(a["yaw_error_integral_rad"], 4), round(b["yaw_error_integral_rad"], 4),
          "beta_error", round(a["control_sideslip_error_integral_rad_s"], 4), round(b["control_sideslip_error_integral_rad_s"], 4),
          "force_sign", b["desired_and_actual_longitudinal_moment_same_sign_ticks"], b["active_ticks"])
