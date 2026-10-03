"""两模式5°真实斜面坡停；同输入转子A/B，保持原10s位移及力平衡门槛。"""

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

from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import Vec3
from physics.reference_ab import _source_hashes, _step

from driver_assist import SIMULATION_INPUT
from driving_modes import DrivingMode
from vehicle import Vehicle
from vehicle_state import FIXED_DT, VehicleCommand


def run_trial(mode, enabled, path):
    config = replace(mode.vehicle_config, wheel_rotor_transport=enabled)
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    theta = math.radians(5.)
    ground = BulletRigidBodyNode("转子坡停斜面")
    ground.addShape(BulletPlaneShape(Vec3(0, -math.sin(theta), math.cos(theta)), 0))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda _x, _y: True, (0, 0, .55), pitch=5., config=config, input_config=SIMULATION_INPUT)
    try:
        command = VehicleCommand(brake=1.)
        for _ in range(600):
            _step(world, car, command)
        initial = car.snapshot().position
        forces, maximum_residual = [], 0.
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            stream.write(json.dumps({"tick": 0, "state": asdict(car.snapshot()), "command": asdict(command)}, allow_nan=False) + "\n")
            for tick in range(1, 1201):
                _step(world, car, command)
                state = car.snapshot()
                stream.write(json.dumps({"tick": tick, "state": asdict(state), "command": asdict(command)}, allow_nan=False) + "\n")
                forces.append(sum(w.longitudinal_impulse for w in state.wheel_dynamics) / FIXED_DT)
                maximum_residual = max(maximum_residual, *(w.force_residual for w in state.wheel_dynamics))
        displacement = math.dist(initial, car.snapshot().position)
        expected = config.mass * 9.81 * math.sin(theta)
        mean_force = sum(forces) / len(forces)
        return {"mode": mode.value, "transport_enabled": enabled, "config": asdict(config),
                "duration_s": 10., "settle_s": 5., "step_hz": 120, "sample_stride": 1,
                "displacement_m": displacement, "mean_longitudinal_force_n": mean_force,
                "expected_force_n": expected, "maximum_force_residual_n": maximum_residual,
                "passed": displacement < .01 and abs(mean_force / expected - 1) < .01 and maximum_residual < .001,
                "trace": path.name}
    finally:
        car.close()


def run_matrix(output):
    output.mkdir(parents=True, exist_ok=False)
    before = _source_hashes()
    trials = []
    for mode in DrivingMode:
        for enabled in (False, True):
            trial = run_trial(mode, enabled, output / f"{mode.value}-rotor-{int(enabled)}.jsonl.gz")
            trials.append(trial)
            (output / "summary.json").write_text(json.dumps({"status": "running", "trials": trials}, indent=2), encoding="utf-8")
            print(f"{mode.value} rotor={enabled} drift={trial['displacement_m']:.6g} force={trial['mean_longitudinal_force_n']:.6g} passed={trial['passed']}", flush=True)
    after = _source_hashes()
    report = {"status": "completed", "passed": all(t["passed"] for t in trials),
              "trials": trials, "source_sha256_before": before, "source_sha256_after": after,
              "source_stable": before == after, "scope": "native support + brakes; no runtime position/velocity edits; headless evidence"}
    (output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    result = run_matrix(parser.parse_args().output)
    raise SystemExit(0 if result["passed"] else 1)
