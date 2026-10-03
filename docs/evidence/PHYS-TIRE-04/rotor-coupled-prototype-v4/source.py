"""转子预研：轴向反力与四轮接触共同末状态；冻结驾驶源码不变。"""

import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_tire_coupling import CONFIG, INERTIA, contact_frames
from tire_compliance import contact_force, energy_terms
from tire_coupling import cross, dot
from tire_forces import slip_state
from tire_properties import tire_grip, tire_stiffness
from wheel_dynamics import advance_wheel

OUT = Path(__file__).with_name("rotor-coupled-prototype-v4")


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "tests", "tools") for p in sorted((ROOT / folder).rglob("*.py"))}


def joint_step(velocity, angular, omega, frames, deformation, drives, brakes, h, gyro, inverse_tensor=None):
    """固定瞬时惯量/轴向的隐式子步；gyro也使用同一末轮速与末车体角速。"""
    configurations = (CONFIG, CONFIG, replace(CONFIG, lateral_stiffness=CONFIG.rear_lateral_stiffness),
                      replace(CONFIG, lateral_stiffness=CONFIG.rear_lateral_stiffness))
    forces = [(0., 0., 0.)] * 4
    local_steps = [None] * 4
    radius, inertia = CONFIG.wheel_radius, CONFIG.wheel_inertia
    tensor = np.diag(tuple(1 / v for v in INERTIA)) if inverse_tensor is None else np.array(inverse_tensor)
    body_inertia = np.linalg.inv(tensor)
    rolling = tuple(max(abs(dot(tuple(velocity[a] + cross(angular, frame.hub)[a] for a in range(3)),
                                frame.tangent)), abs(radius * omega[i])) >= CONFIG.static_contact_speed
                    for i, frame in enumerate(frames))

    def mechanical_state(exclude=None):
        total_force, torque = [0.] * 3, [0.] * 3
        # 陀螺项取完整迭代的末轮速；局部更新不把第i轮的自旋从车上移除。
        end_omega = tuple(omega[i] + h * (drives[i] - forces[i][2] - radius * forces[i][0]) / inertia
                          for i in range(4))
        spin = tuple(-inertia * sum(end_omega[i] * frame.axle[a] for i, frame in enumerate(frames))
                     for a in range(3))
        for i, frame in enumerate(frames):
            if i == exclude:
                continue
            fx, fy, used_brake = forces[i]
            for a in range(3):
                total_force[a] += frame.tangent[a] * fx + frame.axle[a] * fy
                torque[a] += (cross(frame.hub, frame.tangent)[a] * fx
                              + cross(frame.point, frame.axle)[a] * fy
                              + frame.axle[a] * (drives[i] - used_brake))
        if gyro:
            x, y, z = spin
            skew = np.array(((0., -z, y), (z, 0., -x), (-y, x, 0.)))
            end_angular = np.linalg.solve(body_inertia - h * skew,
                                          body_inertia @ angular + h * np.array(torque))
            gyro_torque = cross(spin, tuple(end_angular))
        else:
            end_angular = tuple(np.array(angular) + h * tensor @ torque)
            gyro_torque = (0., 0., 0.)
        end_velocity = tuple(velocity[a] + h * total_force[a] / CONFIG.mass for a in range(3))
        return end_velocity, tuple(end_angular), end_omega, spin, gyro_torque, total_force, torque

    for iteration in range(20):
        # 轴承反力在本次力迭代内一起更新；局部Newton仍求原轮胎方程。
        _v, _a, _w, _s, gyro_torque, _f, _t = mechanical_state()
        order = range(4) if iteration % 2 == 0 else range(3, -1, -1)
        for i in order:
            frame = frames[i]
            known_velocity, _known_angular, *_rest = mechanical_state(exclude=i)
            torque_without = [0.] * 3
            for j, other in enumerate(frames):
                if j == i:
                    continue
                fx, fy, used_brake = forces[j]
                for a in range(3):
                    torque_without[a] += (cross(other.hub, other.tangent)[a] * fx
                                          + cross(other.point, other.axle)[a] * fy
                                          + other.axle[a] * (drives[j] - used_brake))
            known_angular = tuple(np.array(angular) + h * tensor @ (np.array(torque_without) + gyro_torque))
            hub_speed = tuple(known_velocity[a] + cross(known_angular, frame.hub)[a] for a in range(3))
            point_speed = tuple(known_velocity[a] + cross(known_angular, frame.point)[a] for a in range(3))
            step = advance_wheel(omega[i], dot(hub_speed, frame.tangent), dot(point_speed, frame.axle),
                                 dot(known_angular, frame.axle), drives[i], brakes[i], frame.load,
                                 frame.mu, frame.mobility, h, configurations[i], deformation[i],
                                 force_tolerance=.0001, rolling_contact=rolling[i],
                                 force_initial=forces[i][:2])
            forces[i] = (step.fx, step.fy, step.brake_torque)
            local_steps[i] = step
        end_velocity, end_angular, end_omega, spin, gyro_torque, total_force, torque = mechanical_state()
        completed, force_error, brake_error = [], 0., 0.
        for i, frame in enumerate(frames):
            fx, fy, used_brake = forces[i]
            vx = dot(tuple(end_velocity[a] + cross(end_angular, frame.hub)[a] for a in range(3)), frame.tangent)
            vy = dot(tuple(end_velocity[a] + cross(end_angular, frame.point)[a] for a in range(3)), frame.axle)
            body_omega = dot(end_angular, frame.axle)
            grip = tire_grip(frame.load, frame.mu, configurations[i])
            cx, cy = tire_stiffness(frame.load, configurations[i])
            target, elastic, rate, patch, pk, pa, mode = contact_force(
                (fx, fy), deformation[i], (radius * end_omega[i] - vx, -vy),
                max(abs(vx), CONFIG.slip_speed), rolling[i], grip, cx, cy, h,
                CONFIG.tire_contact_stiffness, CONFIG.tire_contact_damping, CONFIG.tire_shape, CONFIG.tire_curvature)
            error = math.hypot(fx - target[0], fy - target[1])
            relative = end_omega[i] + body_omega
            correction = relative / (h * (1 / inertia + frame.mobility.tt))
            berror = abs(used_brake - max(-brakes[i], min(brakes[i], used_brake + correction))) / radius
            force_error, brake_error = max(force_error, error), max(brake_error, berror)
            kappa, alpha = slip_state(vx, vy, end_omega[i], radius, CONFIG)
            energy, material, road, numerical = energy_terms(
                (fx, fy), deformation[i], elastic, rate, patch, h,
                CONFIG.tire_contact_stiffness, CONFIG.tire_contact_damping)
            completed.append(replace(local_steps[i], omega=end_omega[i], relative_omega=relative,
                                     vx=vx, vy=vy, body_omega=body_omega, kappa=kappa, alpha=alpha,
                                     residual=max(error, berror), mode=mode if frame.load else "airborne",
                                     deformation_x=elastic[0], deformation_y=elastic[1],
                                     patch_kappa=pk, patch_alpha=pa, elastic_energy=energy,
                                     material_dissipation=material, road_dissipation=road,
                                     elastic_numerical_dissipation=numerical,
                                     deformation_rate_x=rate[0], deformation_rate_y=rate[1]))
        if force_error < .001 and brake_error < 1e-9:
            return tuple(completed), end_velocity, end_angular, spin, gyro_torque, total_force, torque, iteration + 1
    raise ArithmeticError(f"共同末状态不收敛: contact={force_error}, brake={brake_error}")


def trial(name, speed, yaw, spins, drives, brakes, loads, h, gyro):
    velocity, angular = (.3, speed, 0.), (.03, -.02, yaw)
    frames = contact_frames(loads, .45)
    deformation = ((.005, -.003), (-.006, .004), (.007, .002), (-.004, -.006))
    result = joint_step(velocity, angular, spins, frames, deformation, drives, brakes, h, gyro)
    steps, v_end, a_end, spin, gtorque, force, torque, iterations = result
    kinetic = (.5 * CONFIG.mass * (dot(v_end, v_end) - dot(velocity, velocity))
               + .5 * sum(INERTIA[a] * (a_end[a] ** 2 - angular[a] ** 2) for a in range(3))
               + .5 * CONFIG.wheel_inertia * sum(s.omega ** 2 - spins[i] ** 2 for i, s in enumerate(steps)))
    elastic = sum(s.elastic_energy for s in steps) - .5 * CONFIG.tire_contact_stiffness * sum(
        value ** 2 for strain in deformation for value in strain)
    numerical = (.5 * CONFIG.mass * sum((v_end[a] - velocity[a]) ** 2 for a in range(3))
                 + .5 * sum(INERTIA[a] * (a_end[a] - angular[a]) ** 2 for a in range(3))
                 + .5 * CONFIG.wheel_inertia * sum((s.omega - spins[i]) ** 2 for i, s in enumerate(steps)))
    actuator_work = h * sum(drives[i] * s.relative_omega for i, s in enumerate(steps))
    brake_work = h * sum(s.brake_torque * s.relative_omega for s in steps)
    contact_loss = sum(s.material_dissipation + s.road_dissipation + s.elastic_numerical_dissipation for s in steps)
    energy_error = kinetic + elastic + numerical + brake_work + contact_loss - actuator_work
    external = [0.] * 3
    for i, s in enumerate(steps):
        contact = tuple(frames[i].tangent[a] * s.fx + frames[i].axle[a] * s.fy for a in range(3))
        for a in range(3):
            external[a] += h * cross(frames[i].point, contact)[a]
    # 固定瞬时轴向的Euler输运方程；不把它称作有限旋转后的世界动量严格守恒。
    transport = cross(a_end, spin)
    momentum_error = tuple(INERTIA[a] * (a_end[a] - angular[a])
                           - CONFIG.wheel_inertia * sum((s.omega - spins[i]) * frames[i].axle[a]
                                                      for i, s in enumerate(steps))
                           + h * transport[a] - external[a] for a in range(3))
    assert abs(energy_error) < 3e-9, (name, gyro, energy_error)
    assert abs(dot(gtorque, a_end)) < 1e-10
    if gyro:
        assert max(abs(v) for v in momentum_error) < 1e-10
    assert max(s.residual for s in steps) < .001
    assert all(s.brake_torque * s.relative_omega >= -1e-7 for s in steps)
    return {"name": name, "h_s": h, "gyro": gyro, "initial_velocity": velocity,
            "initial_angular": angular, "initial_spins": spins, "drives_nm": drives,
            "brakes_nm": brakes, "loads_n": loads, "deformation": deformation,
            "steps": [asdict(s) for s in steps], "end_velocity": v_end, "end_angular": a_end,
            "end_spin_momentum_nms": spin, "gyro_torque_nm": gtorque,
            "iterations": iterations, "energy_error_j": energy_error,
            "euler_transport_balance_nms": momentum_error,
            "maximum_force_residual_n": max(s.residual for s in steps)}


if __name__ == "__main__":
    OUT.mkdir(exist_ok=False)
    before = source_hashes()
    (OUT / "source.py").write_bytes(Path(__file__).read_bytes())
    cases = (
        ("free_spin", 0., .2, (60.,) * 4, (0.,) * 4, (0.,) * 4, (0.,) * 4),
        ("accelerating", 20., .1, (61.,) * 4, (0., 0., 150., 150.), (0.,) * 4, (2943.,) * 4),
        ("reverse_braking", -12., -.1, (-36.,) * 4, (0., 0., -100., -100.), (500.,) * 4, (2943.,) * 4),
        ("unequal_support", 20., .1, (60., 62., 58., 75.), (0., 0., 150., 150.), (0.,) * 4,
         (0., 300., 5500., 5886.)),
        ("stationary_braking", 0., .1, (0.,) * 4, (0.,) * 4, (1200.,) * 4, (2943.,) * 4),
    )
    trials = []
    for case in cases:
        for h in (1 / 240, 1 / 960):
            for gyro in (False, True):
                result = trial(*case, h, gyro)
                trials.append(result)
                (OUT / f"{case[0]}-{round(1/h)}-gyro-{int(gyro)}.json").write_text(
                    json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                print(f"PASS {case[0]} h=1/{round(1/h)} gyro={gyro} energy={result['energy_error_j']:.3g}", flush=True)
    after = source_hashes()
    assert before == after
    free_negative = [t for t in trials if t["name"] == "free_spin" and not t["gyro"]]
    for trial in free_negative:
        expected = tuple(trial["h_s"] * v for v in cross(trial["end_angular"], trial["end_spin_momentum_nms"]))
        assert max(abs(v) for v in expected) > 1e-8
        assert max(abs(trial["euler_transport_balance_nms"][a] - expected[a]) for a in range(3)) < 1e-10
    (OUT / "summary.json").write_text(json.dumps({
        "claim": "fixed-instantaneous-axis joint gyro/contact mechanical prototype; not production acceptance",
        "config": asdict(CONFIG), "body_inertia": INERTIA, "trials": trials,
        "source_sha256_before": before, "source_sha256_after": after, "source_stable": before == after,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "numpy_version": np.__version__,
        "incomplete": ["native finite orientation integration", "mechanical versus road-contact axes",
                       "steering actuator work", "engine/clutch/driveline", "production lifecycle and A/B"]},
        indent=2, allow_nan=False) + "\n", encoding="utf-8")
