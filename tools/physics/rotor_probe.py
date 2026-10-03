"""生产转子求解的无外力Bullet时间细化；保留每步世界角动量和能量。"""

import argparse
import gzip
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from panda3d.bullet import BulletWorld
from panda3d.core import Vec3
from physics.reference_ab import _source_hashes

from driving_modes import REFERENCE_CAR
from rotor_dynamics import dot
from vehicle import Vehicle
from wheel_geometry import mechanical_axis


def mechanical_state(vehicle):
    body = vehicle._chassis
    orientation = body.getTransform().getQuat()
    angular = body.getAngularVelocity()
    local = orientation.conjugate().xform(angular)
    inertia = body.getInertia()
    body_momentum = orientation.xform(Vec3(*(inertia[a] * local[a] for a in range(3))))
    axes = tuple(mechanical_axis(orientation.getRight(), orientation.getForward(), state.steering)
                 for state in vehicle.tires.states)
    spin = tuple(-vehicle.config.wheel_inertia * sum(vehicle.tires.omega[i] * axes[i][a] for i in range(4))
                 for a in range(3))
    momentum = tuple(body_momentum[a] + spin[a] for a in range(3))
    velocity = body.getLinearVelocity()
    energy = (.5 * vehicle.config.mass * dot(velocity, velocity)
              + .5 * sum(inertia[a] * local[a]**2 for a in range(3))
              + .5 * vehicle.config.wheel_inertia * sum(value**2 for value in vehicle.tires.omega))
    return {"momentum_nms": momentum, "energy_j": energy, "position": tuple(body.getTransform().getPos()),
            "orientation": tuple(orientation), "angular_radps": tuple(angular), "omega_radps": vehicle.tires.omega.copy(),
            "wheels": [asdict(state) for state in vehicle.tires.states]}


def run_free_trial(rate, spin, enabled, duration=1., steering=0.):
    # 该台架只隔离轮轴输运；曲轴机械账由传动台架独立验证。
    config = replace(REFERENCE_CAR, wheel_rotor_transport=enabled, angular_damping=0., finite_drivetrain=False)
    world = BulletWorld()
    world.setGravity(Vec3(0))
    vehicle = Vehicle(world, lambda _x, _y: True, (0, 0, 20), config=config)
    try:
        vehicle._chassis.setAngularVelocity(Vec3(0, 0, .2))
        vehicle.tires.omega = [spin] * 4
        initial = mechanical_state(vehicle)
        rows = [{"tick": 0, "time_s": 0., **initial}]
        h = 1 / rate
        for tick in range(1, round(duration * rate) + 1):
            vehicle.tires.advance(vehicle._chassis, (), (steering, steering), 0., 0., (0.,) * 4, tick, h)
            world.doPhysics(h, 0, h)
            state = mechanical_state(vehicle)
            rows.append({"tick": tick, "time_s": tick * h, **state})
        summary = {"rate_hz": rate, "initial_spin_radps": spin, "transport_enabled": enabled,
                   "config": asdict(config), "steering_degrees": steering,
                   "duration_s": duration, "ticks": tick,
                   "final_momentum_error_nms": math.dist(rows[-1]["momentum_nms"], initial["momentum_nms"]),
                   "maximum_momentum_error_nms": max(math.dist(row["momentum_nms"], initial["momentum_nms"]) for row in rows),
                   "energy_delta_j": rows[-1]["energy_j"] - initial["energy_j"],
                   "steering_work_j": sum(sum(w["steering_work"] for w in row["wheels"]) for row in rows[1:]),
                   "peak_force_residual_n": max(w["force_residual"] for row in rows for w in row["wheels"])}
        return summary, rows
    finally:
        vehicle.close()


def run_matrix(output):
    output.mkdir(parents=True, exist_ok=False)
    before = _source_hashes()
    trials = []
    for spin, enabled in ((0., False), (60., False), (60., True)):
        for rate in (120, 240, 480, 960):
            summary, rows = run_free_trial(rate, spin, enabled)
            filename = f"spin-{spin:g}-rotor-{int(enabled)}-{rate}.jsonl.gz"
            with gzip.open(output / filename, "wt", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, allow_nan=False) + "\n")
            trials.append({**summary, "trace": filename})
            (output / "summary.json").write_text(json.dumps({"status": "running", "trials": trials}, indent=2), encoding="utf-8")
            print(f"spin={spin:g} rotor={enabled} rate={rate} Lerror={summary['final_momentum_error_nms']:.6g}", flush=True)
    after = _source_hashes()
    report = {"status": "completed", "source_sha256_before": before, "source_sha256_after": after,
              "source_stable": before == after, "trials": trials,
              "scope": "free world, native rigid body gyro retained, no ground/gravity/damping/drive/brake; initial state only",
              "precision": "native single precision pose/inertia reads; frozen-axis residual is not finite-world exact conservation",
              "remaining": ["supported A/B", "steering actuator power in native world", "lifecycle", "T1", "human driving"]}
    (output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run_matrix(parser.parse_args().output)
