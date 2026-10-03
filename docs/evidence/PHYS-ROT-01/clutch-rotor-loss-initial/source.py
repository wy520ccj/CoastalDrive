"""传动下一块预研：双向齿轮损失的容量区间与离合/转子/轮胎同末状态。"""

import difflib
import hashlib
import importlib.util
import json
import runpy
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_rotor_transport import CONFIG, INERTIA, TENSOR, frames

from rotor_dynamics import cross, dot

ENGINE_INERTIA = .2
ENGINE_AXIS = (0., 1., 0.)
OUT = Path(__file__).with_name("clutch-rotor-loss-initial")


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "tests", "tools") for p in sorted((ROOT / folder).rglob("*.py"))}


def extend_frozen_solver():
    """仅在独立副本加入额外转子总自旋；物理容差和全部轮胎方程保留。"""
    original = (ROOT / "src/tire_coupling.py").read_text(encoding="utf-8")
    substitutions = (
        ("steering_torques=((0.0, 0.0, 0.0),) * 4):",
         "steering_torques=((0.0, 0.0, 0.0),) * 4, extra_spin=(0.0, 0.0, 0.0)):"),
        ("spin = tuple(-inertia * sum(speeds[i] * axes[i][a] for i in range(4)) for a in range(3))",
         "spin = tuple(extra_spin[a] - inertia * sum(speeds[i] * axes[i][a] for i in range(4)) for a in range(3))"),
        ("bearing = tuple(sum(torque[a] for torque in torques) for a in range(3))",
         "bearing = tuple(cross(extra_spin, shared_angular)[a] + sum(torque[a] for torque in torques) for a in range(3))"),
        ("return completed\n", "return completed, *body_state()\n"),
    )
    extended = original
    for old, new in substitutions:
        assert extended.count(old) == 1
        extended = extended.replace(old, new)
    (OUT / "frozen-tire-coupling.py").write_text(original, encoding="utf-8")
    path = OUT / "extended-tire-coupling.py"
    path.write_text(extended, encoding="utf-8")
    (OUT / "solver-extension.diff").write_text("".join(difflib.unified_diff(
        original.splitlines(True), extended.splitlines(True), fromfile="frozen", tofile="extended")), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("clutch_rotor_bench", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.advance_coupled


def trial(advance, solve_locked, case, h, bank, steering, engine_gyro=True, efficiency=.88):
    name, ratio, speed, engine_omega, engine_torque, capacity, brakes, loads = case
    velocity, angular = (.15, speed, 0.), (.03, -.02, .2)
    omega = (speed / CONFIG.wheel_radius,) * 4
    if name == "unequal_support":
        omega = (omega[0], omega[1], omega[2] * .7, omega[3] * 1.3)
    deformation = ((.005, -.003), (-.006, .004), (.007, .002), (-.004, -.006))
    contact_frames = frames(bank, steering, loads)
    rear = replace(CONFIG, lateral_stiffness=CONFIG.rear_lateral_stiffness)
    evaluations = []

    def evaluate(clutch):
        end_engine = engine_omega + h * (engine_torque - clutch) / ENGINE_INERTIA
        engine_spin = tuple(ENGINE_INERTIA * end_engine * value for value in ENGINE_AXIS)
        engine_reaction = tuple((clutch - engine_torque) * value for value in ENGINE_AXIS)
        free_angular = tuple(angular[a] + h * dot(TENSOR[a], engine_reaction) for a in range(3))
        # 齿轮双向损失按输入端阻抗求解；静止时解区间内真实反力。
        def gear_evaluate(loss):
            drives = (0., 0., ratio * (clutch - loss) / 2, ratio * (clutch - loss) / 2)
            steps, end_velocity, end_angular = advance(
                velocity, free_angular, omega, contact_frames, deformation, drives, brakes,
                CONFIG, rear, h, inverse_inertia=TENSOR,
                extra_spin=engine_spin if engine_gyro else (0., 0., 0.))
            input_speed = ratio * (steps[2].relative_omega + steps[3].relative_omega) / 2
            return input_speed, steps, end_velocity, end_angular

        negative_limit = -(1 / efficiency - 1) * clutch if clutch >= 0 else (1 - efficiency) * clutch
        positive_limit = (1 - efficiency) * clutch if clutch >= 0 else -(1 / efficiency - 1) * clutch
        lower, upper = gear_evaluate(negative_limit), gear_evaluate(positive_limit)
        if lower[0] < 0:
            loss, gear, gear_mode = negative_limit, lower, 'negative-motion'
        elif upper[0] > 0:
            loss, gear, gear_mode = positive_limit, upper, 'positive-motion'
        else:
            loss, gear = solve_locked(gear_evaluate, negative_limit, positive_limit, lower, upper)
            gear_mode = 'static'
        input_speed, steps, end_velocity, end_angular = gear
        slip = end_engine - dot(end_angular, ENGINE_AXIS) - ratio * (steps[2].relative_omega + steps[3].relative_omega) / 2
        evaluations.append({"clutch_nm": clutch, "slip_radps": slip,
                            "maximum_force_residual_n": max(s.residual for s in steps), "gear_loss_nm": loss, "gear_input_radps": input_speed, "gear_mode": gear_mode})
        return slip, steps, end_velocity, end_angular, end_engine, engine_spin, loss, input_speed, gear_mode

    low, high = evaluate(-capacity), evaluate(capacity)
    if low[0] < 0:
        clutch, result, mode = -capacity, low, "negative-slip"
    elif high[0] > 0:
        clutch, result, mode = capacity, high, "positive-slip"
    else:
        clutch, result = solve_locked(evaluate, -capacity, capacity, low, high)
        mode = "locked"
    if capacity == 0:
        mode = "disengaged"
    slip, steps, end_velocity, end_angular, end_engine, engine_spin, loss, input_speed, gear_mode = result
    kinetic = (.5 * CONFIG.mass * (dot(end_velocity, end_velocity) - dot(velocity, velocity))
               + .5 * sum(INERTIA[a] * (end_angular[a]**2 - angular[a]**2) for a in range(3))
               + .5 * CONFIG.wheel_inertia * sum(s.omega**2 - omega[i]**2 for i, s in enumerate(steps))
               + .5 * ENGINE_INERTIA * (end_engine**2 - engine_omega**2))
    elastic = sum(s.elastic_energy for s in steps) - .5 * CONFIG.tire_contact_stiffness * sum(
        value**2 for strain in deformation for value in strain)
    numerical = (.5 * CONFIG.mass * sum((end_velocity[a] - velocity[a])**2 for a in range(3))
                 + .5 * sum(INERTIA[a] * (end_angular[a] - angular[a])**2 for a in range(3))
                 + .5 * CONFIG.wheel_inertia * sum((s.omega - omega[i])**2 for i, s in enumerate(steps))
                 + .5 * ENGINE_INERTIA * (end_engine - engine_omega)**2)
    combustion = h * engine_torque * (end_engine - dot(end_angular, ENGINE_AXIS))
    clutch_loss = h * clutch * slip
    gear_loss = h * loss * input_speed
    brake_loss = h * sum(s.brake_torque * s.relative_omega for s in steps)
    contact_loss = sum(s.material_dissipation + s.road_dissipation + s.elastic_numerical_dissipation for s in steps)
    energy_error = kinetic + elastic + numerical + clutch_loss + gear_loss + brake_loss + contact_loss - combustion
    spin_end = tuple(engine_spin[a] - CONFIG.wheel_inertia * sum(s.omega * contact_frames[i].spin_axis[a]
                                                              for i, s in enumerate(steps)) for a in range(3))
    spin_start = tuple(ENGINE_INERTIA * engine_omega * ENGINE_AXIS[a] - CONFIG.wheel_inertia * sum(
        omega[i] * frame.spin_axis[a] for i, frame in enumerate(contact_frames)) for a in range(3))
    external = [0.] * 3
    for frame, step in zip(contact_frames, steps):
        force = tuple(frame.tangent[a] * step.fx + frame.axle[a] * step.fy for a in range(3))
        moment = cross(frame.point, force)
        for a in range(3):
            external[a] += h * moment[a]
    momentum_error = tuple(INERTIA[a] * (end_angular[a] - angular[a]) + spin_end[a] - spin_start[a]
                           + h * cross(end_angular, spin_end)[a] - external[a] for a in range(3))
    if engine_gyro:
        assert max(abs(v) for v in momentum_error) < 1e-10, (name, bank, steering, momentum_error)
    else:
        missing = tuple(h * value for value in cross(end_angular, engine_spin))
        assert max(abs(momentum_error[a] - missing[a]) for a in range(3)) < 1e-10
        assert max(abs(v) for v in missing) > 1e-7
    assert abs(energy_error) < 3e-9, (name, bank, steering, energy_error)
    assert max(s.residual for s in steps) < .001
    assert clutch_loss >= -1e-9
    assert gear_loss >= -1e-9
    if abs(input_speed) > 1e-9 and abs(clutch) > 1e-9:
        factor = (clutch - loss) / clutch
        assert abs(factor - (efficiency if clutch * input_speed > 0 else 1 / efficiency)) < 1e-12
    assert abs(clutch) <= capacity
    assert all(s.brake_torque * s.relative_omega >= -1e-7 for s in steps)
    assert all(abs(s.body_omega - dot(end_angular, frame.spin_axis)) < 1e-12
               for frame, s in zip(contact_frames, steps))
    return {"case": name, "h_s": h, "bank_degrees": bank, "steering_degrees": steering,
            "engine_gyro": engine_gyro, "ratio": ratio, "engine_torque_nm": engine_torque,
            "clutch_capacity_nm": capacity, "gear_efficiency":efficiency, "gear_loss_nm":loss, "gear_input_radps":input_speed, "gear_mode":gear_mode, "brake_capacities_nm": brakes, "loads_n": loads,
            "initial_velocity": velocity, "initial_angular": angular, "initial_engine_omega": engine_omega,
            "initial_wheel_omega": omega, "deformation": deformation, "frames": [asdict(f) for f in contact_frames],
            "clutch_mode": mode, "clutch_torque_nm": clutch, "end_slip_radps": slip,
            "end_velocity": end_velocity, "end_angular": end_angular, "end_engine_omega": end_engine,
            "wheel_steps": [asdict(s) for s in steps], "evaluations": evaluations,
            "engine_spin_momentum_nms": engine_spin, "engine_gyro_torque_nm": cross(engine_spin, end_angular),
            "momentum_balance_nms": momentum_error,
            "energy_j": {"kinetic": kinetic, "elastic": elastic, "numerical": numerical,
                         "combustion": combustion, "clutch_loss": clutch_loss, "gear_loss":gear_loss, "brake_loss": brake_loss,
                         "contact_loss": contact_loss, "balance_error": energy_error}}


if __name__ == "__main__":
    OUT.mkdir(exist_ok=False)
    before = hashes()
    (OUT / "source.py").write_bytes(Path(__file__).read_bytes())
    advance = extend_frozen_solver()
    legacy_path = ROOT / "docs/evidence/PHYS-TIRE-04/clutch-tire-coupled-brent.py"
    solve_locked = runpy.run_path(str(legacy_path))["solve_locked"]
    (OUT / "root-source.py").write_bytes(legacy_path.read_bytes())
    supported, unbraked = (2943.,) * 4, (0.,) * 4
    cases = (
        ("accelerating", 12., 5., 220., 160., 300., unbraked, supported),
        ("backdriving", 12., 5., 130., 0., 300., unbraked, supported),
        ("reverse", -12., -5., 220., 160., 300., unbraked, supported),
        ("braking", 12., 12., 436., 0., 300., (600.,) * 4, supported),
        ("stationary_launch", 12., 0., 94., 120., 300., unbraked, supported),
        ("airborne", 12., 5., 220., 150., 300., unbraked, (0.,) * 4),
        ("unequal_support", 12., 5., 220., 150., 300., unbraked, (2943., 2943., 0., 5886.)),
        ("disengaged", 12., 5., 220., 150., 0., unbraked, supported),
    )
    trials = []
    try:
        for case in cases:
            for h in (1 / 240, 1 / 960):
                for bank, steering in ((-20., -30.), (0., 0.), (20., 30.)):
                    result = trial(advance, solve_locked, case, h, bank, steering)
                    trials.append(result)
                    (OUT / f"{case[0]}-{round(1/h)}-{bank:g}.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
                    print(f"PASS {case[0]} h={h:g} bank={bank:g} {result['clutch_mode']} energy={result['energy_j']['balance_error']:.3g}", flush=True)
        for h in (1 / 240, 1 / 960):
            result = trial(advance, solve_locked, cases[5], h, 20., 30., engine_gyro=False)
            trials.append(result)
    except (ArithmeticError, AssertionError) as error:
        (OUT / "failure.json").write_text(json.dumps({"error": repr(error), "completed": len(trials),
            "source_stable": before == hashes(), "source_before": before, "source_after": hashes()}, indent=2), encoding="utf-8")
        raise
    after = hashes()
    report = {"claim": "same-end engine spin + finite clutch + bidirectional gear friction + four compliant contacts; fixed instantaneous world axes; prototype only",
              "source_stable": before == after, "source_before": before, "source_after": after,
              "config": asdict(CONFIG), "body_inertia": INERTIA, "engine_inertia": ENGINE_INERTIA,
              "engine_axis": ENGINE_AXIS, "trials": trials,
              "remaining": ["native finite orientation engine rotor", "combustion/idle/redline controls", "automatic clutch and unloaded shifts",
                            "continuous complete-vehicle two-way gear loss validation", "drive layout", "vehicle lifecycle", "production A/B and T1/T2"]}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"trials":len(trials), "source_stable":before == after,
        "max_energy_error_j": max(abs(t["energy_j"]["balance_error"]) for t in trials),
        "max_positive_momentum_error_nms": max(abs(v) for t in trials if t["engine_gyro"] for v in t["momentum_balance_nms"])}))
