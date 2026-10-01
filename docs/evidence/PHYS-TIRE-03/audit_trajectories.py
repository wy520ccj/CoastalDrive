from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
INPUT_DIRS = (EVIDENCE / "vehicle-ab", EVIDENCE / "substeps")
REPORT = EVIDENCE / "trajectory-audit-corrected.json"
WHEELS = range(4)
RESIDUAL_LIMIT_N = 0.001
GRIP_EXCESS_LIMIT_N = 0.001
DISSIPATION_FIELDS = (
    "material_dissipation", "elastic_numerical_dissipation", "frame_dissipation",
)
RAW_DISSIPATION_FIELDS = (*DISSIPATION_FIELDS, "road_dissipation")
NUMERIC_WHEEL_FIELDS = (
    "omega", "rotation", "relative_omega", "longitudinal_speed", "lateral_speed",
    "kappa", "alpha", "fx", "fy", "drive_torque", "brake_capacity", "brake_torque",
    "normal_load", "steering", "force_contact_tick", "force_residual", "force_kappa",
    "force_alpha", "sample_tick", "longitudinal_impulse", "lateral_impulse",
    "brake_angular_impulse", "force_grip", "sample_grip", "force_longitudinal_stiffness",
    "force_lateral_stiffness", "deformation_x", "deformation_y", "force_patch_kappa",
    "force_patch_alpha", "elastic_energy", "material_dissipation", "road_dissipation",
    "elastic_numerical_dissipation", "frame_dissipation", "deformation_rate_x",
    "deformation_rate_y",
)
REQUIRED_FIELDS = (
    "fx", "fy", "normal_load", "force_residual", "force_grip", "deformation_x",
    "deformation_y", "deformation_rate_x", "deformation_rate_y", "material_dissipation",
    "road_dissipation", "elastic_numerical_dissipation", "frame_dissipation",
)
SLIP_FIELDS = {
    "force_patch": ("force_patch_kappa", "force_patch_alpha"),
    "force_phase_wheel": ("force_kappa", "force_alpha"),
    "completed_observation": ("kappa", "alpha"),
}


class Statistics:
    def __init__(self):
        self.count = 0
        self.minimum = None
        self.maximum = None
        self.maximum_absolute = None

    def add(self, value):
        self.count += 1
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)
        magnitude = abs(value)
        self.maximum_absolute = magnitude if self.maximum_absolute is None else max(self.maximum_absolute, magnitude)

    def result(self):
        return {"count": self.count, "min": self.minimum, "max": self.maximum,
                "max_abs": self.maximum_absolute}


def sha_src():
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "src").rglob("*.py"))}


def src_subset(hashes):
    return {path.replace("\\", "/"): value for path, value in hashes.items()
            if path.replace("\\", "/").startswith("src/")}


def experiment_index(directory):
    summary_path = directory / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "completed":
        raise RuntimeError(f"experiment summary is not completed: {summary_path}")
    index = {}
    if directory.name == "vehicle-ab":
        for case in summary["cases"]:
            for variant in ("A", "B"):
                index[(case["mode"], case["case"], variant)] = {
                    "config": case[variant]["config"], "ticks": case[variant].get("ticks")}
        before = summary["source_sha256_before"]
        after = summary["source_sha256_after"]
    else:
        for trial in summary["trials"]:
            for variant in ("2", "8"):
                index[(trial["mode"], trial["case"], variant)] = {
                    "config": trial[variant]["config"], "ticks": trial[variant].get("ticks")}
        before = summary["source_before"]
        after = summary["source_after"]
    protocol = summary.get("protocol", {})
    return index, {"path": summary_path.relative_to(ROOT).as_posix(), "status": summary["status"],
                   "sha_before_after_equal": before == after,
                   "source_sha_before_all": before, "source_sha_after_all": after,
                   "source_sha_before": src_subset(before), "source_sha_after": src_subset(after),
                   "protocol": protocol}


def file_identity(directory, path):
    stem = path.name[:-7]  # 去掉.csv.gz后缀。
    parts = stem.split("-")
    mode, variant = parts[0], parts[-1]
    case = "-".join(parts[1:-1])
    return mode, case, variant


def number(row, field):
    raw = row.get(field, "")
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def add_violation(violations, key, sample):
    item = violations[key]
    item["count"] += 1
    if len(item["examples"]) < 20:
        item["examples"].append(sample)


def per_file_audit(directory, path, experiment):
    config = experiment["config"]
    stiffness = float(config["tire_contact_stiffness"])
    damping = float(config["tire_contact_damping"])
    compliant = bool(config["tire_compliance"])
    prefix_rel = str(path.relative_to(ROOT))
    per_wheel = {}
    violations = defaultdict(lambda: {"count": 0, "examples": []})
    row_count = 0
    finite_values_checked = 0
    tick_min = tick_max = None
    with gzip.open(path, "rt", newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        headers = set(reader.fieldnames or ())
        for wheel in WHEELS:
            missing = [f"state.wheel_dynamics.{wheel}.{field}" for field in REQUIRED_FIELDS
                       if f"state.wheel_dynamics.{wheel}.{field}" not in headers]
            if missing:
                raise ValueError(f"{path.name} missing required wheel fields: {missing}")
            fields_map = {name: Statistics() for name in (
                "normal_load_N", "fx_N", "fy_N", "force_magnitude_N", "force_grip_N",
                "force_grip_excess_N", "force_residual_N", "Kz_plus_b_rate_minus_force_x_N",
                "Kz_plus_b_rate_minus_force_y_N", "force_patch_kappa", "force_patch_alpha",
                "force_phase_kappa", "force_phase_alpha", "completed_observation_kappa",
                "completed_observation_alpha", "patch_vs_completed_kappa_difference",
                "patch_vs_completed_alpha_difference", "force_contact_tick_minus_sample_tick",
            )}
            for dissipation in RAW_DISSIPATION_FIELDS:
                fields_map[f"{dissipation}_J"] = Statistics()
            per_wheel[wheel] = {"fields": fields_map, "zero_load_observations": 0,
                                "airborne_observations": 0, "zero_load_nonzero_force_count": 0,
                                "airborne_nonzero_force_count": 0, "residual_violation_count": 0,
                                "force_grip_violation_count": 0, "negative_dissipation_counts": defaultdict(int),
                                "completed_observation_airborne_count": 0,
                                "Kz_plus_b_rate_identity_observations": 0,
                                "different_force_and_observe_tick_count": 0}
        for row_index, row in enumerate(reader):
            row_count += 1
            tick_value = number(row, "tick")
            if tick_value is not None:
                tick_min = tick_value if tick_min is None else min(tick_min, tick_value)
                tick_max = tick_value if tick_max is None else max(tick_max, tick_value)
            for wheel in WHEELS:
                prefix = f"state.wheel_dynamics.{wheel}."
                state = per_wheel[wheel]
                fields_map = state["fields"]
                for field in (reader.fieldnames or ()):
                    if not field.startswith(prefix):
                        continue
                    value = number(row, field)
                    if value is None:
                        continue
                    finite_values_checked += 1
                    if not math.isfinite(value):
                        add_violation(violations, "non_finite_wheel_value", {
                            "file": prefix_rel, "row_index": row_index, "tick": tick_value,
                            "wheel": wheel, "field": field, "value": row[field]})
                values = {name: number(row, prefix + name) for name in NUMERIC_WHEEL_FIELDS}
                values = {name: value if value is None or math.isfinite(value) else None
                          for name, value in values.items()}
                fx, fy = values["fx"], values["fy"]
                load, grip = values["normal_load"], values["force_grip"]
                residual = values["force_residual"]
                if load is not None:
                    fields_map["normal_load_N"].add(load)
                if fx is not None:
                    fields_map["fx_N"].add(fx)
                if fy is not None:
                    fields_map["fy_N"].add(fy)
                if grip is not None:
                    fields_map["force_grip_N"].add(grip)
                magnitude = math.hypot(fx, fy) if fx is not None and fy is not None else None
                if magnitude is not None:
                    fields_map["force_magnitude_N"].add(magnitude)
                if magnitude is not None and grip is not None:
                    excess = magnitude - grip
                    fields_map["force_grip_excess_N"].add(excess)
                    if excess > GRIP_EXCESS_LIMIT_N:
                        state["force_grip_violation_count"] += 1
                        add_violation(violations, "force_exceeds_grip_budget", {
                            "file": prefix_rel, "row_index": row_index, "tick": tick_value,
                            "wheel": wheel, "fx_N": fx, "fy_N": fy, "magnitude_N": magnitude,
                            "force_grip_N": grip, "excess_N": excess})
                if residual is not None:
                    fields_map["force_residual_N"].add(residual)
                    if residual >= RESIDUAL_LIMIT_N:
                        state["residual_violation_count"] += 1
                        add_violation(violations, "solver_residual_at_or_above_0.001N", {
                            "file": prefix_rel, "row_index": row_index, "tick": tick_value,
                            "wheel": wheel, "residual_N": residual})
                # road_support/force_mode describe the force solve; wheel_contacts is
                # the later post-Bullet observation and must not relabel that force.
                road_support = row.get(prefix + "road_support", "")
                force_mode = row.get(prefix + "force_mode", "")
                airborne = road_support.lower() == "false" and force_mode != "uninitialized"
                contact_field = f"state.wheel_contacts.{wheel}.in_contact"
                observed_contact = row.get(contact_field, "")
                if observed_contact.lower() == "false":
                    state["completed_observation_airborne_count"] += 1
                if load == 0.0:
                    state["zero_load_observations"] += 1
                    if magnitude is not None and magnitude != 0.0:
                        state["zero_load_nonzero_force_count"] += 1
                        add_violation(violations, "nonzero_force_at_zero_normal_load", {
                            "file": prefix_rel, "row_index": row_index, "tick": tick_value,
                            "wheel": wheel, "normal_load_N": load, "fx_N": fx, "fy_N": fy})
                if airborne:
                    state["airborne_observations"] += 1
                    if magnitude is not None and magnitude != 0.0:
                        state["airborne_nonzero_force_count"] += 1
                        add_violation(violations, "nonzero_force_while_airborne", {
                            "file": prefix_rel, "row_index": row_index, "tick": tick_value,
                            "wheel": wheel, "normal_load_N": load, "fx_N": fx, "fy_N": fy})
                for dissipation in RAW_DISSIPATION_FIELDS:
                    dissipation_value = values[dissipation]
                    if dissipation_value is None:
                        continue
                    fields_map[f"{dissipation}_J"].add(dissipation_value)
                    if dissipation in DISSIPATION_FIELDS and dissipation_value < 0.0:
                        state["negative_dissipation_counts"][dissipation] += 1
                        add_violation(violations, f"negative_{dissipation}", {
                            "file": prefix_rel, "row_index": row_index, "tick": tick_value,
                            "wheel": wheel, "value_J": dissipation_value})
                if compliant:
                    for axis, force_name, deformation_name, rate_name in (
                        ("x", "fx", "deformation_x", "deformation_rate_x"),
                        ("y", "fy", "deformation_y", "deformation_rate_y"),
                    ):
                        force = values[force_name]
                        deformation = values[deformation_name]
                        rate = values[rate_name]
                        if force is None or deformation is None or rate is None:
                            continue
                        identity_error = stiffness * deformation + damping * rate - force
                        identity_name = f"Kz_plus_b_rate_minus_force_{axis}_N"
                        fields_map[identity_name].add(identity_error)
                        state["Kz_plus_b_rate_identity_observations"] += 1
                slip_values = {}
                for phase, (kappa_field, alpha_field) in SLIP_FIELDS.items():
                    kappa = values[kappa_field]
                    alpha = values[alpha_field]
                    slip_values[phase] = (kappa, alpha)
                    if kappa is not None:
                        fields_map[{"force_patch": "force_patch_kappa", "force_phase_wheel": "force_phase_kappa",
                                    "completed_observation": "completed_observation_kappa"}[phase]].add(kappa)
                    if alpha is not None:
                        fields_map[{"force_patch": "force_patch_alpha", "force_phase_wheel": "force_phase_alpha",
                                    "completed_observation": "completed_observation_alpha"}[phase]].add(alpha)
                patch_k, patch_a = slip_values["force_patch"]
                sample_k, sample_a = slip_values["completed_observation"]
                if patch_k is not None and sample_k is not None:
                    fields_map["patch_vs_completed_kappa_difference"].add(patch_k - sample_k)
                if patch_a is not None and sample_a is not None:
                    fields_map["patch_vs_completed_alpha_difference"].add(patch_a - sample_a)
                force_tick = values["force_contact_tick"]
                sample_tick = values["sample_tick"]
                if force_tick is not None and sample_tick is not None:
                    tick_delta = force_tick - sample_tick
                    fields_map["force_contact_tick_minus_sample_tick"].add(tick_delta)
                    if tick_delta != 0:
                        state["different_force_and_observe_tick_count"] += 1
    wheel_results = {}
    for wheel, state in per_wheel.items():
        wheel_results[str(wheel)] = {
            "metrics": {name: stats.result() for name, stats in state["fields"].items()},
            "zero_load_observations": state["zero_load_observations"],
            "airborne_observations": state["airborne_observations"],
            "completed_observation_airborne_count": state["completed_observation_airborne_count"],
            "zero_load_nonzero_force_count": state["zero_load_nonzero_force_count"],
            "airborne_nonzero_force_count": state["airborne_nonzero_force_count"],
            "residual_violation_count": state["residual_violation_count"],
            "force_grip_violation_count": state["force_grip_violation_count"],
            "negative_dissipation_counts": dict(state["negative_dissipation_counts"]),
            "Kz_plus_b_rate_identity_applicable": compliant,
            "Kz_plus_b_rate_identity_observations": state["Kz_plus_b_rate_identity_observations"],
            "different_force_and_observe_tick_count": state["different_force_and_observe_tick_count"],
        }
    violation_counts = {name: item["count"] for name, item in violations.items()}
    return {
        "file": prefix_rel, "rows": row_count, "wheel_observations": row_count * len(WHEELS),
        "tick_min": tick_min, "tick_max": tick_max, "mode": file_identity(directory, path)[0],
        "case": file_identity(directory, path)[1], "variant": file_identity(directory, path)[2],
        "config_tire_compliance": compliant, "expected_tick_count_from_summary": experiment["ticks"],
        "expected_csv_rows_including_initial": None if experiment["ticks"] is None else experiment["ticks"] + 1,
        "config_tire_contact_stiffness_N_per_m": stiffness,
        "config_tire_contact_damping_Ns_per_m": damping,
        "numeric_wheel_values_checked_for_finiteness": finite_values_checked,
        "per_wheel": wheel_results, "violation_counts": violation_counts,
        "violation_examples": {name: item["examples"] for name, item in violations.items()},
    }


def run_audit():
    if REPORT.exists():
        raise FileExistsError(f"audit report already exists; refusing overwrite: {REPORT}")
    source_before = sha_src()
    files = []
    summaries = {}
    for directory in INPUT_DIRS:
        index, summary_info = experiment_index(directory)
        summaries[directory.name] = summary_info
        paths = sorted(directory.glob("*.csv.gz"))
        if not paths:
            raise FileNotFoundError(f"no trajectory CSV.gz files in {directory}")
        for path in paths:
            identity = file_identity(directory, path)
            try:
                experiment = index[identity]
            except KeyError as error:
                raise KeyError(f"no summary config for trajectory {path.name}: {identity}") from error
            result = per_file_audit(directory, path, experiment)
            source_hash_at_generation = summary_info["source_sha_before"]
            source_hash_after_generation = summary_info["source_sha_after"]
            result["source_sha256_unchanged_during_generation"] = source_hash_at_generation == source_hash_after_generation
            result["source_sha256_before_generation_matches_audit_start"] = source_hash_at_generation == source_before
            result["source_sha256_after_generation_matches_audit_start"] = source_hash_after_generation == source_before
            expected_rows = result["expected_csv_rows_including_initial"]
            if expected_rows is not None and expected_rows != result["rows"]:
                result["violation_counts"]["trajectory_row_count_mismatch"] = 1
                result["violation_examples"]["trajectory_row_count_mismatch"] = [{
                    "file": result["file"], "expected_rows_including_initial": expected_rows,
                    "actual_rows": result["rows"],
                }]
            files.append(result)
    source_after = sha_src()
    violations = defaultdict(int)
    for result in files:
        for name, count in result["violation_counts"].items():
            violations[name] += count
    violation_total = sum(violations.values())
    return {
        "task": "PHYS-TIRE-03 full trajectory integrity audit",
        "status": "completed" if violation_total == 0 and source_before == source_after else "failed",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "scope": "contact force/deformation/dissipation records only; this does not measure complete Bullet/chassis/engine/brake energy",
        "force_phase_vs_observation_phase": {
            "force_kappa_alpha": "wheel slip at tire force solve (force_contact_tick)",
            "force_patch_kappa_alpha": "contact patch slip at tire force solve (force_contact_tick)",
            "kappa_alpha": "wheel slip observed after Bullet step (sample_tick)",
            "these_signals_are_reported_separately": True,
            "force_contact_tick_minus_sample_tick": "normal phase offset, raw min/max retained; -1 means the force solve preceded Bullet observation by one tick and is not a violation",
        },
        "thresholds": {"original_force_solver_residual_strictly_below_N": RESIDUAL_LIMIT_N,
                       "force_magnitude_minus_grip_at_most_N": GRIP_EXCESS_LIMIT_N,
                       "zero_load_and_airborne_force": "exactly zero; no tolerance or clamping"},
        "summary_inputs": summaries,
        "src_sha256_before": source_before, "src_sha256_after": source_after,
        "src_source_unchanged_during_audit": source_before == source_after,
        "source_file_count": len(source_before), "trajectory_file_count": len(files),
        "trajectory_row_count": sum(result["rows"] for result in files),
        "wheel_observation_count": sum(result["wheel_observations"] for result in files),
        "violation_counts": dict(violations), "violation_total": violation_total,
        "files": files,
        "road_dissipation_policy": "preserve signed raw values and report min/max; negative values are reported, not clamped or treated as material/numerical dissipation",
        "baseline_rigid_evidence": "mechanical-rigid/ is read-only and was not altered; Kz+b rate identity is not applicable to tire_compliance=false baseline trials",
    }


def main():
    report = run_audit()
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {
        "status": report["status"], "report": str(REPORT),
        "trajectory_files": report["trajectory_file_count"], "rows": report["trajectory_row_count"],
        "wheel_observations": report["wheel_observation_count"],
        "violation_counts": report["violation_counts"], "source_unchanged": report["src_source_unchanged_during_audit"],
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
