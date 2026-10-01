from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import sys
from dataclasses import fields, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "component-scan"
sys.path.insert(0, str(ROOT / "src"))

from tire_properties import tire_grip
from vehicle_config import CAR
from wheel_dynamics import Mobility, WheelStep, advance_wheel

CONFIG = replace(CAR, tire_compliance=True)
FN0 = CONFIG.mass * 9.81 / 4
DT = 1 / 240
ENERGY_LEDGER_TOLERANCE_J = 2e-9
SOLVER_RESIDUAL_LIMIT_N = 0.001
MASS = np.array(((300.0, 0.0, 0.0), (0.0, 320.0, 12.0), (0.0, 12.0, 50.0)))
MASS_EIGENVALUES = np.linalg.eigvalsh(MASS)
INVERSE = np.linalg.inv(MASS)
MOBILITY = Mobility(INVERSE[0, 0], INVERSE[0, 1], INVERSE[0, 2],
                    INVERSE[1, 1], INVERSE[1, 2], INVERSE[2, 2])
VXS = (-30.0, -2.0, 0.0, 2.0, 30.0)
VYS = (-2.0, 0.0, 2.0)
WHEEL_STATES = ("pure-rolling", "locked", "reverse-spin")
LOADS = (0.0, 0.01 * FN0, 0.5 * FN0, FN0, 2.0 * FN0)
MUS = (0.0, 0.45, 1.1)
DEFORMATION_SEEDS = (0.0, 0.01, -0.01)
SEQUENCES = (
    ("rolling", 20.0, 0.2, 0.0, 0.0),
    ("braking", 20.0, 0.2, 0.0, 500.0),
    ("reverse", -8.0, -0.2, -100.0, 0.0),
)
SOURCE_FILES = tuple(sorted((ROOT / "src").rglob("*.py")))
GRID_COLUMNS = (
    "case_id", "vx_before_m_s", "vy_before_m_s", "body_omega_before_rad_s", "wheel_state",
    "omega_before_rad_s", "drive_torque_Nm", "brake_torque_capacity_Nm", "normal_load_N", "mu",
    "deformation_x_before_m", "deformation_y_before_m", "dt_s", "status", "error_type", "error",
    "fx_N", "fy_N", "omega_after_rad_s", "vx_after_m_s", "vy_after_m_s", "body_omega_after_rad_s",
    "relative_omega_after_rad_s", "residual_N", "mode", "deformation_x_after_m", "deformation_y_after_m",
    "patch_kappa", "patch_alpha_rad", "elastic_energy_after_J", "material_dissipation_J",
    "road_dissipation_J", "elastic_numerical_dissipation_J", "mechanical_numerical_dissipation_J",
    "body_kinetic_energy_change_J", "wheel_kinetic_energy_change_J", "elastic_energy_change_J",
    "drive_brake_work_J", "energy_ledger_expected_J", "energy_ledger_lhs_J", "energy_ledger_residual_J",
    "body_momentum_max_error", "wheel_momentum_error_Nm_s", "force_budget_D_N", "force_budget_excess_N",
)
SEQUENCE_COLUMNS = ("sequence", "tick", "mu_phase", "load_phase", "vx_before_m_s", "vy_before_m_s",
                    "body_omega_before_rad_s", "omega_before_rad_s", "drive_torque_Nm", "brake_torque_capacity_Nm",
                    "normal_load_N", "mu", "deformation_x_before_m", "deformation_y_before_m", "status",
                    "error_type", "error") + GRID_COLUMNS[16:]


def encode(value):
    if is_dataclass(value):
        return {field.name: encode(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported config value: {type(value).__name__}")


def source_hashes():
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in SOURCE_FILES}


def wheel_initial_state(kind, vx):
    if kind == "pure-rolling":
        return vx / CONFIG.wheel_radius, 0.0, 0.0
    if kind == "locked":
        return 0.0, 0.0, 500.0
    if kind == "reverse-spin":
        return -vx / CONFIG.wheel_radius, -100.0, 0.0
    raise ValueError(f"unknown wheel state {kind}")


def diagnostics(before, before_omega, deformation, drive, step: WheelStep, load, mu):
    old_body = np.asarray(before, dtype=float)
    new_body = np.asarray((step.vx, step.vy, step.body_omega), dtype=float)
    body_delta = new_body - old_body
    wheel_delta = step.omega - before_omega
    body_kinetic_change = 0.5 * new_body @ MASS @ new_body - 0.5 * old_body @ MASS @ old_body
    wheel_kinetic_change = 0.5 * CONFIG.wheel_inertia * (step.omega**2 - before_omega**2)
    old_elastic = 0.5 * CONFIG.tire_contact_stiffness * sum(value * value for value in deformation)
    elastic_change = step.elastic_energy - old_elastic
    mechanical_numerical = (0.5 * body_delta @ MASS @ body_delta
                             + 0.5 * CONFIG.wheel_inertia * wheel_delta**2)
    drive_brake_work = DT * (drive - step.brake_torque) * step.relative_omega
    expected = (drive_brake_work - step.material_dissipation - step.road_dissipation
                - step.elastic_numerical_dissipation - mechanical_numerical)
    lhs = body_kinetic_change + wheel_kinetic_change + elastic_change
    energy_residual = lhs - expected
    predicted_body_delta = DT * INVERSE @ np.array((step.fx, step.fy, drive - step.brake_torque))
    body_momentum_error = float(np.max(np.abs(body_delta - predicted_body_delta)))
    wheel_momentum_error = (CONFIG.wheel_inertia * wheel_delta
                            - DT * (drive - step.brake_torque - CONFIG.wheel_radius * step.fx))
    grip = tire_grip(load, mu, CONFIG)
    budget_excess = math.hypot(step.fx, step.fy) - grip
    fails = []
    if step.residual >= SOLVER_RESIDUAL_LIMIT_N:
        fails.append("solver_residual")
    if abs(energy_residual) > ENERGY_LEDGER_TOLERANCE_J:
        fails.append("energy_ledger")
    if body_momentum_error > 1e-10:
        fails.append("body_momentum")
    if abs(wheel_momentum_error) > 1e-10:
        fails.append("wheel_momentum")
    if budget_excess > 0.001:
        fails.append("force_budget")
    if step.road_dissipation < -1e-7:
        fails.append("negative_road_dissipation")
    if step.material_dissipation < 0:
        fails.append("negative_material_dissipation")
    if step.elastic_numerical_dissipation < 0:
        fails.append("negative_elastic_numerical_dissipation")
    values = {
        "fx_N": step.fx, "fy_N": step.fy, "omega_after_rad_s": step.omega,
        "vx_after_m_s": step.vx, "vy_after_m_s": step.vy, "body_omega_after_rad_s": step.body_omega,
        "relative_omega_after_rad_s": step.relative_omega, "residual_N": step.residual, "mode": step.mode,
        "deformation_x_after_m": step.deformation_x, "deformation_y_after_m": step.deformation_y,
        "patch_kappa": step.patch_kappa, "patch_alpha_rad": step.patch_alpha,
        "elastic_energy_after_J": step.elastic_energy, "material_dissipation_J": step.material_dissipation,
        "road_dissipation_J": step.road_dissipation,
        "elastic_numerical_dissipation_J": step.elastic_numerical_dissipation,
        "mechanical_numerical_dissipation_J": mechanical_numerical,
        "body_kinetic_energy_change_J": body_kinetic_change,
        "wheel_kinetic_energy_change_J": wheel_kinetic_change,
        "elastic_energy_change_J": elastic_change, "drive_brake_work_J": drive_brake_work,
        "energy_ledger_expected_J": expected, "energy_ledger_lhs_J": lhs,
        "energy_ledger_residual_J": energy_residual, "body_momentum_max_error": body_momentum_error,
        "wheel_momentum_error_Nm_s": wheel_momentum_error, "force_budget_D_N": grip,
        "force_budget_excess_N": budget_excess,
    }
    return values, fails


def exception_values(error):
    return {name: "" for name in GRID_COLUMNS[16:] if name not in ("error_type", "error")}


def case_grid(writer, failures, maxima):
    case_id = 0
    total = len(VXS) * len(VYS) * len(WHEEL_STATES) * len(LOADS) * len(MUS) * len(DEFORMATION_SEEDS)
    for vx in VXS:
        for vy in VYS:
            for kind in WHEEL_STATES:
                omega, drive, brake = wheel_initial_state(kind, vx)
                for load in LOADS:
                    for mu in MUS:
                        for seed in DEFORMATION_SEEDS:
                            case_id += 1
                            deformation = (seed, -seed)
                            body = (vx, vy, 0.1)
                            row = {"case_id": case_id, "vx_before_m_s": vx, "vy_before_m_s": vy,
                                   "body_omega_before_rad_s": body[2], "wheel_state": kind,
                                   "omega_before_rad_s": omega, "drive_torque_Nm": drive,
                                   "brake_torque_capacity_Nm": brake, "normal_load_N": load, "mu": mu,
                                   "deformation_x_before_m": deformation[0], "deformation_y_before_m": deformation[1],
                                   "dt_s": DT, "status": "ok", "error_type": "", "error": ""}
                            try:
                                step = advance_wheel(omega, *body, drive, brake, load, mu, MOBILITY, DT,
                                                     CONFIG, deformation)
                            except Exception as error:  # noqa: BLE001  # 单工况异常必须留账后继续其他诊断。
                                row["status"] = "exception"
                                row["error_type"] = type(error).__name__
                                row["error"] = str(error)
                                row.update(exception_values(error))
                                failures.append({"kind": "exception", "case_id": case_id, "error_type": type(error).__name__,
                                                 "error": str(error), **{key: row[key] for key in (
                                                     "vx_before_m_s", "vy_before_m_s", "wheel_state", "omega_before_rad_s",
                                                     "normal_load_N", "mu", "deformation_x_before_m", "deformation_y_before_m")}})
                            else:
                                values, failed_checks = diagnostics(body, omega, deformation, drive, step, load, mu)
                                row.update(values)
                                if failed_checks:
                                    row["status"] = "failed-check:" + ",".join(failed_checks)
                                    failures.append({"kind": "check", "case_id": case_id, "failed_checks": failed_checks,
                                                     "error_type": "", "error": "", **{key: row[key] for key in (
                                                         "vx_before_m_s", "vy_before_m_s", "wheel_state", "omega_before_rad_s",
                                                         "normal_load_N", "mu", "deformation_x_before_m", "deformation_y_before_m",
                                                         "residual_N", "energy_ledger_residual_J", "force_budget_excess_N")}})
                                for key in ("residual_N", "energy_ledger_residual_J", "body_momentum_max_error",
                                            "wheel_momentum_error_Nm_s", "force_budget_excess_N"):
                                    raw_value = float(values[key])
                                    value = max(0.0, raw_value) if key == "force_budget_excess_N" else abs(raw_value)
                                    maxima[key] = max(maxima.get(key, 0.0), value)
                            writer.writerow([row.get(column, "") for column in GRID_COLUMNS])
    if case_id != total:
        raise RuntimeError(f"fixed grid produced {case_id} cases, expected {total}")
    return {"rows": case_id, "expected_rows": total}


def sequence_scan(writer, failures, maxima):
    mu_schedule = (1.1, 0.45, 0.0, 1.1)
    load_schedule = (0.5 * FN0, 2.0 * FN0, 0.0, FN0, 0.01 * FN0)
    ticks_per_sequence = 240
    completed = {}
    for name, vx0, vy0, drive, brake in SEQUENCES:
        vx, vy, body_omega = vx0, vy0, 0.1
        omega = vx / CONFIG.wheel_radius
        deformation = (0.01, -0.01)
        sequence_failures = 0
        aborted = False
        for tick in range(ticks_per_sequence):
            mu_phase = min(3, tick // 60)
            load_phase = (tick // 24) % len(load_schedule)
            mu, load = mu_schedule[mu_phase], load_schedule[load_phase]
            before = (vx, vy, body_omega)
            row = {"sequence": name, "tick": tick, "mu_phase": mu_phase, "load_phase": load_phase,
                   "vx_before_m_s": vx, "vy_before_m_s": vy, "body_omega_before_rad_s": body_omega,
                   "omega_before_rad_s": omega, "drive_torque_Nm": drive, "brake_torque_capacity_Nm": brake,
                   "normal_load_N": load, "mu": mu, "deformation_x_before_m": deformation[0],
                   "deformation_y_before_m": deformation[1], "status": "ok", "error_type": "", "error": ""}
            try:
                step = advance_wheel(omega, *before, drive, brake, load, mu, MOBILITY, DT,
                                     CONFIG, deformation)
            except Exception as error:  # noqa: BLE001  # 本序列留错并停止，仍运行其他独立序列。
                row["status"] = "exception"
                row["error_type"] = type(error).__name__
                row["error"] = str(error)
                failures.append({"kind": "sequence_exception", "sequence": name, "tick": tick,
                                 "error_type": type(error).__name__, "error": str(error),
                                 "vx_before_m_s": vx, "vy_before_m_s": vy, "omega_before_rad_s": omega,
                                 "normal_load_N": load, "mu": mu, "deformation": deformation})
                writer.writerow([row.get(column, "") for column in SEQUENCE_COLUMNS])
                sequence_failures += 1
                aborted = True
                break
            values, failed_checks = diagnostics(before, omega, deformation, drive, step, load, mu)
            row.update(values)
            if failed_checks:
                row["status"] = "failed-check:" + ",".join(failed_checks)
                failures.append({"kind": "sequence_check", "sequence": name, "tick": tick,
                                 "failed_checks": failed_checks, "vx_before_m_s": vx, "vy_before_m_s": vy,
                                 "omega_before_rad_s": omega, "normal_load_N": load, "mu": mu,
                                 "residual_N": step.residual, "energy_ledger_residual_J": values["energy_ledger_residual_J"]})
                sequence_failures += 1
            for key in ("residual_N", "energy_ledger_residual_J", "body_momentum_max_error",
                        "wheel_momentum_error_Nm_s", "force_budget_excess_N"):
                raw_value = float(values[key])
                value = max(0.0, raw_value) if key == "force_budget_excess_N" else abs(raw_value)
                maxima[key] = max(maxima.get(key, 0.0), value)
            writer.writerow([row.get(column, "") for column in SEQUENCE_COLUMNS])
            vx, vy, body_omega, omega = step.vx, step.vy, step.body_omega, step.omega
            deformation = (step.deformation_x, step.deformation_y)
        completed[name] = {"ticks_written": tick + 1, "aborted_on_exception": aborted,
                           "failed_check_count": sequence_failures}
    return {"sequences": completed, "nominal_ticks_each": ticks_per_sequence,
            "mu_schedule": mu_schedule, "load_schedule_N": load_schedule}


def minimum_failure(failures):
    if not failures:
        return None
    def magnitude(item):
        numeric = ("vx_before_m_s", "vy_before_m_s", "omega_before_rad_s", "normal_load_N", "mu",
                   "deformation_x_before_m", "deformation_y_before_m")
        return sum(abs(float(item.get(key, 0) or 0)) for key in numeric)
    return min(failures, key=magnitude)


def main():
    if OUT.exists():
        raise FileExistsError(f"output directory must not exist; refusing overwrite: {OUT}")
    OUT.mkdir()
    before_hashes = source_hashes()
    try:
        if len(MASS_EIGENVALUES) != 3 or float(MASS_EIGENVALUES.min()) <= 0:
            raise ValueError(f"body generalized mass matrix is not SPD: {MASS_EIGENVALUES.tolist()}")
        np.linalg.cholesky(MASS)
        failures = []
        maxima = {}
        grid_path = OUT / "fixed-component-grid.csv.gz"
        with gzip.open(grid_path, "wt", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(GRID_COLUMNS)
            grid_result = case_grid(writer, failures, maxima)
        sequence_path = OUT / "continuous-sequences.csv.gz"
        with gzip.open(sequence_path, "wt", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(SEQUENCE_COLUMNS)
            sequence_result = sequence_scan(writer, failures, maxima)
        after_hashes = source_hashes()
        sha_unchanged = before_hashes == after_hashes
        if not sha_unchanged:
            failures.append({"kind": "source_sha_changed_during_scan", "error_type": "", "error": "src SHA before/after differ"})
        passed = not failures
        summary = {
            "task": "PHYS-TIRE-03 deterministic component scan", "status": "completed" if passed else "failed",
            "timestamp_utc": datetime.now(UTC).isoformat(), "configuration": encode(CONFIG),
            "tire_compliance_explicitly_enabled": CONFIG.tire_compliance,
            "source_sha256_before": before_hashes, "source_sha256_after": after_hashes,
            "source_file_count": len(before_hashes), "source_unchanged": sha_unchanged,
            "units": {"force": "N", "torque": "N m", "energy": "J", "linear_speed": "m/s", "angular_speed": "rad/s", "deformation": "m", "time": "s"},
            "fn0_N": FN0, "dt_s": DT,
            "body_mass_matrix_kg_generalized": MASS.tolist(), "body_mass_matrix_eigenvalues": MASS_EIGENVALUES.tolist(),
            "body_mass_matrix_spd_verified_by": "positive eigenvalues and Cholesky factorization",
            "fixed_grid": {**grid_result, "file": grid_path.name, "vx_m_s": VXS, "vy_m_s": VYS,
                           "wheel_states": WHEEL_STATES, "loads_N": LOADS, "mu": MUS,
                           "initial_deformation_seed_m": DEFORMATION_SEEDS,
                           "deformation_vector_for_seed": "(seed, -seed)", "failure_count": len(failures)},
            "continuous_sequences": {**sequence_result, "file": sequence_path.name},
            "energy_ledger": {"identity": "delta(Kbody+Kwheel+Kdeformation) = h*(Tdrive-Tbrake)*relative_omega - Dmaterial - Droad - DelasticNumerical - DmechanicalNumerical",
                              "solver_residual_limit_N": SOLVER_RESIDUAL_LIMIT_N,
                              "independent_energy_identity_tolerance_J": ENERGY_LEDGER_TOLERANCE_J,
                              "maximum_absolute_observed": maxima},
            "failure_count": len(failures), "failures": failures,
            "minimum_failure_parameters": minimum_failure(failures),
            "evidence_boundary": "deterministic advance_wheel component scan with explicitly enabled tire compliance; not a full-vehicle validation",
        }
        (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUT / "status.json").write_text(json.dumps({"status": "completed" if passed else "failed",
                                                       "fixed_grid_rows": grid_result["rows"],
                                                       "continuous_sequences": sequence_result["sequences"],
                                                       "failure_count": len(failures),
                                                       "minimum_failure_parameters": minimum_failure(failures),
                                                       "source_unchanged": sha_unchanged}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "completed" if passed else "failed", "output": str(OUT),
                          "fixed_grid_rows": grid_result["rows"], "failure_count": len(failures),
                          "minimum_failure_parameters": minimum_failure(failures),
                          "maximum_observed": maxima, "source_file_count": len(before_hashes),
                          "source_unchanged": sha_unchanged}, ensure_ascii=False, indent=2))
        if not passed:
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as error:
        (OUT / "status.json").write_text(json.dumps({"status": "failed", "error_type": type(error).__name__,
                                                       "error": str(error), "source_sha256_before": before_hashes,
                                                       "source_sha256_after": source_hashes()}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
