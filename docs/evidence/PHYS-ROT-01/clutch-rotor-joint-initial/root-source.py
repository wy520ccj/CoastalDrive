"""传动预研：生产四轮接触与离合共同末状态，固定轴向，不修改驾驶源码。"""

import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/"src"))

from driving_modes import REFERENCE_CAR
from tire_compliance import deformation_frame
from tire_coupling import ContactFrame, advance_coupled, cross, dot
from wheel_dynamics import Mobility

OUT = Path(__file__).with_name("clutch-tire-coupled-brent")
CONFIG = REFERENCE_CAR
INERTIA = CONFIG.body_inertia
ENGINE_INERTIA = .2
ENGINE_AXIS = (0., 1., 0.)


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "tests", "tools") for p in sorted((ROOT/folder).rglob("*.py"))}


def frames_for(loads):
    frames = []
    for i, (x, y) in enumerate(((-.84, 1.1), (.84, 1.1), (-.84, -1.1), (.84, -1.1))):
        tangent, axle, point = (0., 1., 0.), (1., 0., 0.), (x, y, -.42)
        hub = (x, y, -.42+CONFIG.wheel_radius)
        mx, my = cross(hub, tangent), cross(point, axle)
        rx, ry, rt = (tuple(vector[a]/INERTIA[a] for a in range(3)) for vector in (mx, my, axle))
        mobility = Mobility(1/CONFIG.mass+dot(mx, rx), dot(mx, ry), dot(mx, rt),
                            1/CONFIG.mass+dot(my, ry), dot(my, rt), dot(axle, rt))
        frames.append(ContactFrame(0., loads[i] > 0, loads[i], .45, tangent, axle, point, hub, mobility,
                                   deformation_frame(tangent, (0., 0., 1.)), rx, ry, rt))
    return frames


def solve_locked(evaluate, a, b, result_a, result_b):
    """同一有界离合滑差的Brent插值/二分，末滑差门槛保持1e-11 rad/s。"""
    fa, fb = result_a[0], result_b[0]
    if abs(fa) < abs(fb):
        a, b, fa, fb, result_a, result_b = b, a, fb, fa, result_b, result_a
    c, fc, d = a, fa, a
    previous_bisection = True
    for _ in range(64):
        if abs(fb) < 1e-11:
            return b, result_b
        if fa != fc and fb != fc:
            s = (a*fb*fc/((fa-fb)*(fa-fc))+b*fa*fc/((fb-fa)*(fb-fc))
                 +c*fa*fb/((fc-fa)*(fc-fb)))
        else:
            s = b-fb*(b-a)/(fb-fa)
        edge = (3*a+b)/4
        inside = edge < s < b if edge < b else b < s < edge
        recent_span = abs(b-c) if previous_bisection else abs(c-d)
        if not inside or abs(s-b) >= recent_span/2 or recent_span < 1e-12:
            s = (a+b)/2
            previous_bisection = True
        else:
            previous_bisection = False
        result_s = evaluate(s)
        fs = result_s[0]
        d, c, fc = c, b, fb
        if fa*fs < 0:
            b, fb, result_b = s, fs, result_s
        else:
            a, fa, result_a = s, fs, result_s
        if abs(fa) < abs(fb):
            a, b, fa, fb, result_a, result_b = b, a, fb, fa, result_b, result_a
    raise ArithmeticError(f"离合Brent共同末滑差未收敛: {fb} rad/s")


def trial(case, h):
    name, ratio, speed, initial_engine, engine_torque, capacity, brakes, loads = case
    velocity, angular = (.15, speed, 0.), (.03, -.02, .01)
    omega = (speed/CONFIG.wheel_radius,)*4
    deformation = ((.005, -.003), (-.006, .004), (.007, .002), (-.004, -.006))
    frames = frames_for(loads)
    rear = replace(CONFIG, lateral_stiffness=CONFIG.rear_lateral_stiffness)
    evaluations = []

    def evaluate(torque):
        free_angular = tuple(angular[a]+h*(torque-engine_torque)*ENGINE_AXIS[a]/INERTIA[a]
                             for a in range(3))
        drives = (0., 0., ratio*torque/2, ratio*torque/2)
        steps = advance_coupled(velocity, free_angular, omega, frames, deformation, drives, brakes,
                                CONFIG, rear, h)
        force, total_torque = [0.]*3, [(torque-engine_torque)*ENGINE_AXIS[a] for a in range(3)]
        for i, step in enumerate(steps):
            frame = frames[i]
            for a in range(3):
                force[a] += frame.tangent[a]*step.fx+frame.axle[a]*step.fy
                total_torque[a] += (cross(frame.hub, frame.tangent)[a]*step.fx
                                   +cross(frame.point, frame.axle)[a]*step.fy
                                   +frame.axle[a]*(drives[i]-step.brake_torque))
        end_velocity = tuple(velocity[a]+h*force[a]/CONFIG.mass for a in range(3))
        end_angular = tuple(angular[a]+h*total_torque[a]/INERTIA[a] for a in range(3))
        end_engine = initial_engine+h*(engine_torque-torque)/ENGINE_INERTIA
        slip = end_engine-dot(end_angular, ENGINE_AXIS)-ratio*(steps[2].relative_omega+steps[3].relative_omega)/2
        evaluations.append({"clutch_torque_nm": torque, "end_slip_radps": slip,
                            "maximum_force_residual_n": max(step.residual for step in steps)})
        return slip, steps, force, total_torque, end_velocity, end_angular, end_engine

    low, high = -capacity, capacity
    low_result, high_result = evaluate(low), evaluate(high)
    if low_result[0] < 0:
        torque, result, mode = low, low_result, "negative-slip"
    elif high_result[0] > 0:
        torque, result, mode = high, high_result, "positive-slip"
    else:
        torque, result = solve_locked(evaluate, low, high, low_result, high_result)
        mode = "locked"
    slip, steps, force, total_torque, end_velocity, end_angular, end_engine = result
    kinetic_change = (.5*CONFIG.mass*(dot(end_velocity, end_velocity)-dot(velocity, velocity))
                      +.5*sum(INERTIA[a]*(end_angular[a]**2-angular[a]**2) for a in range(3))
                      +.5*CONFIG.wheel_inertia*sum(step.omega**2-omega[i]**2 for i, step in enumerate(steps))
                      +.5*ENGINE_INERTIA*(end_engine**2-initial_engine**2))
    elastic_change = sum(step.elastic_energy for step in steps)-.5*CONFIG.tire_contact_stiffness*sum(
        value*value for strain in deformation for value in strain)
    mechanical_BE = (.5*CONFIG.mass*sum((end_velocity[a]-velocity[a])**2 for a in range(3))
                     +.5*sum(INERTIA[a]*(end_angular[a]-angular[a])**2 for a in range(3))
                     +.5*CONFIG.wheel_inertia*sum((step.omega-omega[i])**2 for i, step in enumerate(steps))
                     +.5*ENGINE_INERTIA*(end_engine-initial_engine)**2)
    combustion_work = h*engine_torque*(end_engine-dot(end_angular, ENGINE_AXIS))
    clutch_work = h*torque*slip
    brake_work = h*sum(step.brake_torque*step.relative_omega for step in steps)
    contact_loss = sum(step.material_dissipation+step.road_dissipation+step.elastic_numerical_dissipation
                       for step in steps)
    energy_error = kinetic_change+elastic_change+mechanical_BE+contact_loss+brake_work+clutch_work-combustion_work
    angular_change = [INERTIA[a]*(end_angular[a]-angular[a])
                      +ENGINE_INERTIA*(end_engine-initial_engine)*ENGINE_AXIS[a] for a in range(3)]
    external = [0.]*3
    for i, step in enumerate(steps):
        frame = frames[i]
        contact = tuple(frame.tangent[a]*step.fx+frame.axle[a]*step.fy for a in range(3))
        moment = cross(frame.point, contact)
        for a in range(3):
            angular_change[a] -= CONFIG.wheel_inertia*(step.omega-omega[i])*frame.axle[a]
            external[a] += h*moment[a]
    angular_error = max(abs(angular_change[a]-external[a]) for a in range(3))
    end_state_error = max(abs(step.body_omega-dot(end_angular, frames[i].axle)) for i, step in enumerate(steps))
    assert abs(energy_error) < 3e-9, (name, "energy", energy_error)
    assert angular_error < 1e-10, (name, "angular momentum", angular_error)
    assert end_state_error < 1e-12, (name, "shared end state", end_state_error)
    assert max(step.residual for step in steps) < .001
    assert abs(torque) <= capacity
    assert clutch_work >= -1e-9
    assert all(step.brake_torque*step.relative_omega >= -1e-7 for step in steps)
    return {"case": name, "h_s": h, "ratio": ratio, "engine_torque_nm": engine_torque,
            "capacity_nm": capacity, "initial_velocity": velocity, "initial_angular": angular,
            "initial_wheel_omega": omega, "initial_engine_omega": initial_engine,
            "initial_deformations": deformation, "loads_n": loads, "brake_capacities_nm": brakes,
            "clutch_mode": mode, "clutch_torque_nm": torque, "end_slip_radps": slip,
            "end_velocity": end_velocity, "end_angular": end_angular, "end_engine_omega": end_engine,
            "wheel_steps": [asdict(step) for step in steps], "evaluations": evaluations,
            "energy_terms_j": {"kinetic_change": kinetic_change, "elastic_change": elastic_change,
                               "mechanical_BE": mechanical_BE, "contact_loss": contact_loss,
                               "brake_work": brake_work, "clutch_work": clutch_work,
                               "combustion_work": combustion_work, "balance_error": energy_error},
            "angular_momentum_error_nms": angular_error, "shared_body_omega_error_radps": end_state_error}


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    before = hashes()
    supported, unbraked = (2943.,)*4, (0.,)*4
    cases = (
        ("accelerating", 12., 5., 220., 160., 300., unbraked, supported),
        ("backdriving", 12., 5., 130., 0., 300., unbraked, supported),
        ("reverse", -12., -5., 220., 160., 300., unbraked, supported),
        ("braking", 12., 12., 436., 0., 300., (600.,)*4, supported),
        ("stationary_launch", 12., 0., 94., 120., 300., unbraked, supported),
        ("airborne", 12., 5., 220., 150., 300., unbraked, (0.,)*4),
        ("unequal_support", 12., 5., 220., 150., 300., unbraked, (2943., 2943., 0., 5886.)),
        ("disengaged", 12., 5., 220., 150., 0., unbraked, supported),
    )
    trials = []
    for case in cases:
        for h in (1/240, 1/960):
            result = trial(case, h)
            (OUT/f"{case[0]}-{round(1/h)}.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n",
                                                          encoding="utf-8")
            trials.append(result)
            print(f"PASS {case[0]} h=1/{round(1/h)} {result['clutch_mode']} Tc={result['clutch_torque_nm']:.6f}",
                  flush=True)
    after = hashes()
    report = {"claim": "fixed-axis one-step joint engine/clutch/production-contact prototype; no production integration",
              "source_stable": before == after, "source_sha256_before": before, "source_sha256_after": after,
              "config": asdict(CONFIG), "body_inertia": INERTIA, "engine_inertia": ENGINE_INERTIA,
              "engine_axis": ENGINE_AXIS, "trials": trials}
    (OUT/"summary.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"trials": len(trials), "source_stable": before == after,
                      "maximum_energy_error_j": max(abs(t['energy_terms_j']['balance_error']) for t in trials),
                      "maximum_angular_error_nms": max(t['angular_momentum_error_nms'] for t in trials)}))
