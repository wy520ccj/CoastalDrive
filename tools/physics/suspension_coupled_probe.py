"""两模式旧原生/SI耦合悬架短轨迹；保留单侧支撑、斜面与力限的不利响应。"""

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import TransformState, Vec3
from physics.reference_ab import _step

from driving_modes import DrivingMode
from vehicle import Vehicle
from vehicle_contacts import road_support
from vehicle_state import VehicleCommand

CASES = ("flat-free", "bank", "one-side", "drop-limit")


def trial(mode, enabled, case, rows):
    config = replace(DrivingMode(mode).vehicle_config, suspension_coupled_enabled=enabled)
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode(case)
    if case == "one-side":
        ground.addShape(BulletBoxShape(Vec3(.4, 40, .05)))
        ground.setTransform(TransformState.makePos(Vec3(-.84, 0, -.05)))
    else:
        normal = Vec3(-.2, 0, 1).normalized() if case == "bank" else Vec3(0, 0, 1)
        ground.addShape(BulletPlaneShape(normal, 0))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda x, y: True, (0, 0, 1.1 if case == "drop-limit" else .4), config=config)
    try:
        command = VehicleCommand(gear=0)
        if case == "flat-free":
            for _ in range(180):
                _step(world, car, command)
            car._chassis.setLinearVelocity(Vec3(0, 0, .5))  # 一次性试验初始条件。
        for tick in range(360):
            _step(world, car, command)
            state = car.snapshot()
            rows.append({"tick": tick + 1, "car": asdict(state), "body_angular": tuple(car._chassis.getAngularVelocity()),
                         "native_force": tuple(w.getWheelsSuspensionForce() for w in car._vehicle.getWheels())})
            assert all(math.isfinite(v) for v in (*state.position, *state.velocity, state.roll, state.pitch))
            assert all(0 <= c.normal_load <= config.suspension_force_limit + 1e-7 for c in state.wheel_contacts)
            assert all(abs(t.force_residual) < .001 for t in state.wheel_dynamics)
            if enabled:
                assert state.suspension_state.force_tick == state.contact_tick
                assert all(t.normal_load == (c.normal_load if c.in_contact and road_support(c.contact_normal) else 0.)
                           for t, c in zip(state.wheel_dynamics, state.wheel_contacts))
                assert all(value == 0 for value in rows[-1]["native_force"])
                assert abs(state.suspension_state.step.energy_residual) < 1e-7
        summaries = [row["car"]["suspension_state"] for row in rows] if enabled else []
        return {"mode": mode, "coupled": enabled, "case": case, "config": asdict(config), "ticks": len(rows),
                "max_abs_roll_deg": max(abs(r["car"]["roll"]) for r in rows),
                "max_compression_m": max(c["compression"] for r in rows for c in r["car"]["wheel_contacts"]),
                "final_position": rows[-1]["car"]["position"],
                "max_tire_residual_n": max(abs(t["force_residual"]) for r in rows for t in r["car"]["wheel_dynamics"]),
                "max_suspension_energy_residual_j": max((abs(s["step"]["energy_residual"]) for s in summaries), default=None),
                "sum_signed_force_limit_work_j": sum(s["step"]["force_limit_work"] for s in summaries),
                "sum_signed_geometry_work_j": sum(s["geometry_work"] for s in summaries)}
    finally:
        car.close()


def run(output, prior=None, reuse_native_only=False):
    output.mkdir(parents=True, exist_ok=False)
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for group in ("src", "tests", "tools") for p in sorted((ROOT / group).rglob("*.py"))}
    report = {"status": "running", "protocol": "2 modes x 4 cases x 2 branches; 360 native 120Hz steps per trace; initial-condition velocity change only before flat-free recording; signed geometry and force-limit work remain model boundary ports", "source_before": hashes(), "results": []}
    pending = [(mode, case, enabled) for mode in ("game", "simulation") for case in CASES for enabled in (False, True)]
    if prior is not None:
        previous = json.loads((prior / "summary.json").read_text(encoding="utf-8"))
        changed = [name for name, digest in previous["source_after"].items()
                   if report["source_before"][name] != digest]
        assert previous["source_stable"]
        if reuse_native_only:
            assert set(changed) <= {"src/vehicle_suspension.py", "tests/test_suspension_native.py",
                                    "tests/test_vehicle_contacts.py", "tests/test_rotor_lifecycle.py",
                                    Path(__file__).relative_to(ROOT).as_posix()}
        else:
            assert changed == [Path(__file__).relative_to(ROOT).as_posix()]
        for result in previous["results"]:
            if reuse_native_only and result["coupled"]:
                continue
            trace = Path(os.path.relpath(prior / result["trace"], output)).as_posix()
            report["results"].append({**result, "trace": trace, "reused_from": str(prior / "summary.json")})
            pending.remove((result["mode"], result["case"], result["coupled"]))
        report["reuse"] = {"prior": str(prior), "completed_cases": len(report["results"]),
                          "changed_sources": changed, "reason": "native branch does not execute changed SI adapter; case inputs and native force path identical" if reuse_native_only else "only steep-contact diagnostic expectation changed; all physics and case inputs identical"}
    try:
        for mode, case, enabled in list(pending):
            rows = []
            name = f"{mode}-{case}-{'coupled' if enabled else 'native'}.jsonl.gz"
            try:
                result = trial(mode, enabled, case, rows)
            finally:
                with gzip.open(output / name, "wt", encoding="utf-8") as stream:
                    for row in rows:
                        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            report["results"].append({**result, "trace": name})
            pending.remove((mode, case, enabled))
            print(f"DONE {name}: max roll {result['max_abs_roll_deg']:.4f}", flush=True)
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", error=repr(error), failed_trial=pending[0], not_run=pending[1:])
        raise
    else:
        report["status"] = "completed"
    finally:
        report.update(source_after=hashes())
        report["source_stable"] = report["source_before"] == report["source_after"]
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert report["source_stable"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior", type=Path)
    parser.add_argument("--reuse-native-only", action="store_true")
    args = parser.parse_args()
    run(args.output, args.prior, args.reuse_native_only)
