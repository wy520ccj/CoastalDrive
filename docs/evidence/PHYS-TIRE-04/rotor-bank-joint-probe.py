"""不同机械轴、路面横向及有效滚动力臂的同末轮胎/制动/转子虚功台架。"""

import importlib.util
import json
import math
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bank_joint", HERE / "rotor-coupled-prototype.py")
joint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(joint)

from tire_compliance import deformation_frame
from tire_coupling import ContactFrame, cross, dot
from wheel_dynamics import Mobility

OUT = HERE / "rotor-bank-joint-probe"


def normalized(v):
    length = math.sqrt(dot(v, v))
    return tuple(value / length for value in v)


def trial(bank, steer, speed, brake, h):
    config = joint.CONFIG
    velocity, angular = (.3, speed, 0.), (.03, -.02, .1)
    omega = (speed / config.wheel_radius,) * 4
    drives, brakes = (0., 0., 150., 150.), (brake,) * 4
    deformation = ((.005, -.003), (-.006, .004), (.007, .002), (-.004, -.006))
    inertia = joint.INERTIA
    normal = (math.sin(math.radians(bank)), 0., math.cos(math.radians(bank)))
    frames, axes, radii = [], [], []
    for i, (x, y) in enumerate(((-.84, 1.1), (.84, 1.1), (-.84, -1.1), (.84, -1.1))):
        angle = math.radians(steer if i < 2 else 0.)
        axis = (math.cos(angle), -math.sin(angle), 0.)
        tangent = normalized(cross(normal, axis))
        lateral = cross(tangent, normal)
        point = (x, y, -.42)
        radius = config.wheel_radius * math.sqrt(1 - dot(axis, normal) ** 2)
        hub = tuple(point[a] + config.wheel_radius * normal[a] for a in range(3))
        mx = tuple(cross(point, tangent)[a] - radius * axis[a] for a in range(3))
        my = cross(point, lateral)
        rx, ry, rt = (tuple(v[a] / inertia[a] for a in range(3)) for v in (mx, my, axis))
        mobility = Mobility(1 / config.mass + dot(mx, rx), dot(mx, ry), dot(mx, rt),
                            1 / config.mass + dot(my, ry), dot(my, rt), dot(axis, rt))
        frames.append(ContactFrame(steer if i < 2 else 0., True, 2943., .45, tangent, lateral,
                                   point, hub, mobility, deformation_frame(tangent, normal), rx, ry, rt))
        axes.append(axis)
        radii.append(radius)
    result = joint.joint_step(velocity, angular, omega, frames, deformation, drives, brakes, h, True,
                              mechanical_axes=axes, rolling_radii=radii)
    steps, end_v, end_a, spin, gyro, force, torque, iterations = result
    kinetic = (.5 * config.mass * (dot(end_v, end_v) - dot(velocity, velocity))
               + .5 * sum(inertia[a] * (end_a[a] ** 2 - angular[a] ** 2) for a in range(3))
               + .5 * config.wheel_inertia * sum(s.omega ** 2 - omega[i] ** 2 for i, s in enumerate(steps)))
    elastic = sum(s.elastic_energy for s in steps) - .5 * config.tire_contact_stiffness * sum(
        v * v for strain in deformation for v in strain)
    numerical = (.5 * config.mass * sum((end_v[a] - velocity[a]) ** 2 for a in range(3))
                 + .5 * sum(inertia[a] * (end_a[a] - angular[a]) ** 2 for a in range(3))
                 + .5 * config.wheel_inertia * sum((s.omega - omega[i]) ** 2 for i, s in enumerate(steps)))
    actuator = h * sum((drives[i] - s.brake_torque) * s.relative_omega for i, s in enumerate(steps))
    losses = sum(s.material_dissipation + s.road_dissipation + s.elastic_numerical_dissipation for s in steps)
    energy_error = kinetic + elastic + numerical + losses - actuator
    external = [0.] * 3
    for i, s in enumerate(steps):
        contact = tuple(frames[i].tangent[a] * s.fx + frames[i].axle[a] * s.fy for a in range(3))
        for a in range(3):
            external[a] += h * cross(frames[i].point, contact)[a]
    balance = tuple(inertia[a] * (end_a[a] - angular[a])
                    - config.wheel_inertia * sum((s.omega - omega[i]) * axes[i][a] for i, s in enumerate(steps))
                    + h * cross(end_a, spin)[a] - external[a] for a in range(3))
    assert abs(energy_error) < 3e-9, (bank, steer, "energy", energy_error)
    assert max(abs(v) for v in balance) < 1e-10
    assert abs(dot(gyro, end_a)) < 1e-10
    assert all(abs(s.body_omega - dot(end_a, axes[i])) < 1e-12 for i, s in enumerate(steps))
    assert all(s.brake_torque * s.relative_omega >= -1e-7 for s in steps)
    return {"bank_deg": bank, "steer_deg": steer, "speed_mps": speed, "brake_nm": brake, "h_s": h,
            "config": asdict(config), "initial_velocity": velocity, "initial_angular": angular,
            "initial_spins": omega, "deformations": deformation, "drives_nm": drives, "brakes_nm": brakes,
            "frames": [asdict(f) for f in frames], "mechanical_axes": axes, "rolling_radii_m": radii,
            "steps": [asdict(s) for s in steps], "end_velocity": end_v, "end_angular": end_a,
            "gyro_torque_nm": gyro, "force_n": force, "torque_nm": torque, "iterations": iterations,
            "energy_error_j": energy_error, "transport_balance_nms": balance,
            "maximum_force_residual_n": max(s.residual for s in steps)}


if __name__ == "__main__":
    OUT.mkdir(exist_ok=False)
    for source in (Path(__file__), HERE / "rotor-coupled-prototype.py"):
        (OUT / source.name).write_bytes(source.read_bytes())
    before = joint.source_hashes()
    trials = []
    for bank in (-20., 0., 20.):
        for steer in (-30., 0., 30.):
            for speed, brake in ((20., 0.), (-12., 500.), (0., 1200.)):
                for h in (1 / 240, 1 / 960):
                    result = trial(bank, steer, speed, brake, h)
                    trials.append(result)
    after = joint.source_hashes()
    assert before == after
    (OUT / "summary.json").write_text(json.dumps({
        "claim": "tilted-contact fixed-instantaneous-axis joint mechanical fixture, no road/world integration",
        "source_sha256_before": before, "source_sha256_after": after, "source_stable": before == after,
        "trials": trials}, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"trials": len(trials), "maximum_energy_error_j": max(abs(t["energy_error_j"]) for t in trials),
                      "maximum_force_residual_n": max(t["maximum_force_residual_n"] for t in trials),
                      "maximum_iterations": max(t["iterations"] for t in trials)}))
