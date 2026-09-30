"""单轮隐式纵向轮胎力原型；仅用于模型研究，不代表整车 Bullet 证据。"""

import argparse
import json
import math
from pathlib import Path

MASS_KG = 300.0
ROTATIONAL_INERTIA_KGM2 = 1.8
RADIUS_M = 0.33
NORMAL_LOAD_N = 3000.0
FRICTION_COEFFICIENT = 1.1
LONGITUDINAL_STIFFNESS_N = 60000.0
FORCE_LIMIT_N = FRICTION_COEFFICIENT * NORMAL_LOAD_N
DT_VALUES_S = (1 / 120, 1 / 480)

CASES = (
    {"name": "free_rolling", "initial_speed_mps": 10.0, "initial_wheel_speed_rad_s": 10.0 / RADIUS_M,
     "drive_torque_nm": 0.0, "brake_torque_nm": 0.0, "duration_s": 2.0},
    {"name": "drive_from_rest", "initial_speed_mps": 0.0, "initial_wheel_speed_rad_s": 0.0,
     "drive_torque_nm": 900.0, "brake_torque_nm": 0.0, "duration_s": 2.0},
    {"name": "brake_from_20mps", "initial_speed_mps": 20.0, "initial_wheel_speed_rad_s": 20.0 / RADIUS_M,
     "drive_torque_nm": 0.0, "brake_torque_nm": 1500.0, "duration_s": 3.0},
    {"name": "wheel_spin_decay", "initial_speed_mps": 0.0, "initial_wheel_speed_rad_s": 80.0,
     "drive_torque_nm": 0.0, "brake_torque_nm": 0.0, "duration_s": 2.0},
)


def _tire_force(force_n, speed_mps, wheel_speed_rad_s, drive_torque_nm, brake_torque_nm, dt_s):
    next_speed = speed_mps + dt_s * force_n / MASS_KG
    free_wheel_speed = wheel_speed_rad_s + dt_s / ROTATIONAL_INERTIA_KGM2 * (
        drive_torque_nm - RADIUS_M * force_n
    )
    if brake_torque_nm > 0:
        next_wheel_speed = math.copysign(
            max(abs(free_wheel_speed) - dt_s * brake_torque_nm / ROTATIONAL_INERTIA_KGM2, 0.0),
            free_wheel_speed,
        )
    else:
        next_wheel_speed = free_wheel_speed
    denominator = max(abs(next_speed), 1.0)
    tire_force = FORCE_LIMIT_N * math.tanh(
        LONGITUDINAL_STIFFNESS_N
        * (RADIUS_M * next_wheel_speed - next_speed)
        / (denominator * FORCE_LIMIT_N)
    )
    return tire_force, next_speed, next_wheel_speed, free_wheel_speed


def _step(speed_mps, wheel_speed_rad_s, drive_torque_nm, brake_torque_nm, dt_s):
    lower = -FORCE_LIMIT_N
    upper = FORCE_LIMIT_N
    for _ in range(32):
        trial_force = (lower + upper) / 2
        tire_force, *_ = _tire_force(
            trial_force, speed_mps, wheel_speed_rad_s, drive_torque_nm, brake_torque_nm, dt_s
        )
        residual = trial_force - tire_force
        if residual > 0:
            upper = trial_force
        else:
            lower = trial_force

    force_n = (lower + upper) / 2
    tire_force, next_speed, next_wheel_speed, free_wheel_speed = _tire_force(
        force_n, speed_mps, wheel_speed_rad_s, drive_torque_nm, brake_torque_nm, dt_s
    )
    brake_torque_used_nm = (
        ROTATIONAL_INERTIA_KGM2 / dt_s * (free_wheel_speed - next_wheel_speed)
        if brake_torque_nm > 0
        else 0.0
    )
    old_energy = 0.5 * MASS_KG * speed_mps**2 + 0.5 * ROTATIONAL_INERTIA_KGM2 * wheel_speed_rad_s**2
    new_energy = 0.5 * MASS_KG * next_speed**2 + 0.5 * ROTATIONAL_INERTIA_KGM2 * next_wheel_speed**2
    speed_delta = next_speed - speed_mps
    wheel_speed_delta = next_wheel_speed - wheel_speed_rad_s
    expected_energy_delta = (
        dt_s * drive_torque_nm * next_wheel_speed
        - dt_s * brake_torque_used_nm * next_wheel_speed
        - dt_s * force_n * (RADIUS_M * next_wheel_speed - next_speed)
        - 0.5 * MASS_KG * speed_delta**2
        - 0.5 * ROTATIONAL_INERTIA_KGM2 * wheel_speed_delta**2
    )
    return {
        "force_n": force_n,
        "force_residual_n": force_n - tire_force,
        "speed_mps": next_speed,
        "wheel_speed_rad_s": next_wheel_speed,
        "brake_torque_used_nm": brake_torque_used_nm,
        "translational_energy_delta_j": 0.5 * MASS_KG * (next_speed**2 - speed_mps**2),
        "rotational_energy_delta_j": 0.5 * ROTATIONAL_INERTIA_KGM2 * (
            next_wheel_speed**2 - wheel_speed_rad_s**2
        ),
        "total_energy_delta_j": new_energy - old_energy,
        "energy_residual_j": (new_energy - old_energy) - expected_energy_delta,
    }


def _simulate(case, dt_s):
    speed = case["initial_speed_mps"]
    wheel_speed = case["initial_wheel_speed_rad_s"]
    steps = round(case["duration_s"] / dt_s)
    max_abs_force = 0.0
    max_abs_force_residual = 0.0
    max_abs_energy_residual = 0.0
    max_energy_increase = 0.0
    total_translational_delta = 0.0
    total_rotational_delta = 0.0
    no_external_work = case["drive_torque_nm"] == 0 and case["brake_torque_nm"] == 0
    energy_monotone_without_external_work = True
    vehicle_speed_reversed = False
    wheel_speed_reversed = False

    for _ in range(steps):
        step = _step(
            speed,
            wheel_speed,
            case["drive_torque_nm"],
            case["brake_torque_nm"],
            dt_s,
        )
        speed = step["speed_mps"]
        wheel_speed = step["wheel_speed_rad_s"]
        max_abs_force = max(max_abs_force, abs(step["force_n"]))
        max_abs_force_residual = max(max_abs_force_residual, abs(step["force_residual_n"]))
        max_abs_energy_residual = max(max_abs_energy_residual, abs(step["energy_residual_j"]))
        max_energy_increase = max(max_energy_increase, step["total_energy_delta_j"])
        total_translational_delta += step["translational_energy_delta_j"]
        total_rotational_delta += step["rotational_energy_delta_j"]
        if no_external_work and step["total_energy_delta_j"] > 1e-10:
            energy_monotone_without_external_work = False
        if case["brake_torque_nm"] > 0:
            vehicle_speed_reversed |= speed < -1e-10
            wheel_speed_reversed |= wheel_speed < -1e-10

    return {
        "case": case["name"],
        "dt_s": dt_s,
        "steps": steps,
        "duration_s": steps * dt_s,
        "initial_speed_mps": case["initial_speed_mps"],
        "initial_wheel_speed_rad_s": case["initial_wheel_speed_rad_s"],
        "drive_torque_nm": case["drive_torque_nm"],
        "brake_torque_nm": case["brake_torque_nm"],
        "final_speed_mps": speed,
        "final_wheel_speed_rad_s": wheel_speed,
        "max_abs_force_n": max_abs_force,
        "force_limit_n": FORCE_LIMIT_N,
        "max_abs_force_residual_n": max_abs_force_residual,
        "translational_energy_change_j": total_translational_delta,
        "rotational_energy_change_j": total_rotational_delta,
        "total_energy_change_j": total_translational_delta + total_rotational_delta,
        "max_abs_energy_identity_residual_j": max_abs_energy_residual,
        "max_step_energy_increase_j": max_energy_increase,
        "no_external_work": no_external_work,
        "energy_monotone_without_external_work": (
            energy_monotone_without_external_work if no_external_work else None
        ),
        "vehicle_speed_reversed_during_braking": vehicle_speed_reversed,
        "wheel_speed_reversed_during_braking": wheel_speed_reversed,
        "braking_no_reversal": not vehicle_speed_reversed and not wheel_speed_reversed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = [_simulate(case, dt_s) for case in CASES for dt_s in DT_VALUES_S]
    result = {
        "model_scope": "一维单轮隐式数值原型；不是 Bullet 整车证据",
        "parameters": {
            "mass_kg": MASS_KG,
            "rotational_inertia_kgm2": ROTATIONAL_INERTIA_KGM2,
            "radius_m": RADIUS_M,
            "normal_load_n": NORMAL_LOAD_N,
            "mu": FRICTION_COEFFICIENT,
            "longitudinal_stiffness_n": LONGITUDINAL_STIFFNESS_N,
            "force_limit_n": FORCE_LIMIT_N,
            "slip_denominator": "max(abs(v_next), 1 m/s)",
            "bisection_iterations": 32,
        },
        "free_rolling_duration_assumption_s": 2.0,
        "dt_values_s": DT_VALUES_S,
        "cases": CASES,
        "results": rows,
    }
    result["passed"] = all(
        row["max_abs_force_n"] <= FORCE_LIMIT_N
        and row["max_abs_force_residual_n"] < 1e-4
        and row["max_abs_energy_identity_residual_j"] < 1e-8
        and (not row["no_external_work"] or row["energy_monotone_without_external_work"])
        and (row["brake_torque_nm"] == 0 or row["braking_no_reversal"])
        for row in rows
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({"passed": result["passed"], "cases": len(rows)}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
