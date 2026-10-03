"""完整曲轴/四轮无外力原生时间细化，独立读回世界角动量与机械能。"""

import argparse
import gzip
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.bullet import BulletWorld
from panda3d.core import Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from driving_modes import DrivingMode
from vehicle import Vehicle
from wheel_geometry import mechanical_axis


def mechanical_state(vehicle):
    """直接读取原生姿态/惯量与实际轴速，不借用求解器的动量/能量函数。"""
    body, config = vehicle._chassis, vehicle.config
    orientation = body.getTransform().getQuat()
    angular = body.getAngularVelocity()
    local = orientation.conjugate().xform(angular)
    inertia = body.getInertia()
    body_momentum = orientation.xform(Vec3(*(inertia[a] * local[a] for a in range(3))))
    axes = tuple(mechanical_axis(orientation.getRight(), orientation.getForward(), state.steering)
                 for state in vehicle.tires.states)
    engine_axis = orientation.xform(Vec3(*config.engine_axis))
    engine = vehicle.powertrain.engine_omega
    momentum = tuple(body_momentum[a] + config.engine_inertia * engine * engine_axis[a]
        - config.wheel_inertia * sum(vehicle.tires.omega[i] * axes[i][a] for i in range(4)) for a in range(3))
    energy = (.5 * config.mass * body.getLinearVelocity().lengthSquared()
        + .5 * sum(inertia[a] * local[a] ** 2 for a in range(3))
        + .5 * config.engine_inertia * engine ** 2
        + .5 * config.wheel_inertia * sum(w ** 2 for w in vehicle.tires.omega))
    return {"momentum_nms": momentum, "energy_j": energy, "angular_radps": tuple(angular),
        "orientation": tuple(orientation), "position": tuple(body.getTransform().getPos()),
        "powertrain": asdict(vehicle.powertrain.snapshot()), "wheels": [asdict(w) for w in vehicle.tires.states]}


def run_trial(rate, wheel_spin, output, mode="simulation"):
    config = replace(DrivingMode(mode).vehicle_config, finite_drivetrain=True, angular_damping=0.)
    world = BulletWorld()
    world.setGravity(Vec3(0))
    vehicle = Vehicle(world, lambda _x, _y: True, (0, 0, 20), config=config)
    try:
        # 仅试验初态：空挡、无燃烧/曲轴摩擦、无接触；运行中不重设任何速度。
        vehicle._chassis.setAngularVelocity(Vec3(.03, -.02, .2))
        vehicle.tires.omega = [wheel_spin] * 4
        train = vehicle.powertrain
        train.engine_omega = 500.
        train.gear = train.pending_gear = 0
        train.observe(vehicle._chassis)
        initial = mechanical_state(vehicle)
        maximum_error, peak_residual = 0., 0.
        dt = 1 / rate
        with gzip.open(output, "wt", encoding="utf-8") as stream:
            stream.write(json.dumps({"tick": 0, "state": initial}, allow_nan=False) + "\n")
            for tick in range(1, rate + 1):
                vehicle.tires.advance(vehicle._chassis, (), (0., 0.), 0., 0., (0.,) * 4,
                                      tick, dt, powertrain=train)
                world.doPhysics(dt, 0, dt)
                train.observe(vehicle._chassis)
                state = mechanical_state(vehicle)
                stream.write(json.dumps({"tick": tick, "state": state}, allow_nan=False) + "\n")
                maximum_error = max(maximum_error, math.dist(state["momentum_nms"], initial["momentum_nms"]))
                peak_residual = max(peak_residual, *(w["force_residual"] for w in state["wheels"]))
        return {"mode": mode, "rate_hz": rate, "wheel_spin_radps": wheel_spin, "engine_initial_radps": 500.,
            "duration_s": 1., "config": asdict(config), "trace": output.name,
            "maximum_momentum_error_nms": maximum_error,
            "final_momentum_error_nms": math.dist(state["momentum_nms"], initial["momentum_nms"]),
            "energy_delta_j": state["energy_j"] - initial["energy_j"], "peak_force_residual_n": peak_residual}
    finally:
        vehicle.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--modes", nargs="+", choices=("game", "simulation"), default=["simulation"])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ("src", "tests", "tools") for p in sorted((ROOT / folder).rglob("*.py"))}
    before = hashes()
    report = {"status": "running", "source_before": before, "trials": [],
        "scope": "no ground/gravity/damping/combustion/drag/clutch load; full native body + engine + wheel ledger",
        "precision": "native single precision; time refinement diagnostics, not exact finite-world conservation"}

    def save():
        (args.output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")

    save()
    try:
        for mode in args.modes:
            for spin in (0., 60.):
                for rate in (120, 240, 480, 960):
                    result = run_trial(rate, spin, args.output / f"{mode}-wheel-{spin:g}-{rate}.jsonl.gz", mode)
                    report["trials"].append(result)
                    save()
                    print(f"DONE {mode} wheel={spin:g} rate={rate} Lerror={result['final_momentum_error_nms']:.6g} dE={result['energy_delta_j']:.6g}", flush=True)
    except (ArithmeticError, OSError, ValueError) as error:
        report.update(status="failed", error=repr(error))
        save()
        raise
    after = hashes()
    report.update(status="completed", source_after=after, source_stable=before == after)
    save()
    assert before == after


if __name__ == "__main__":
    main()
