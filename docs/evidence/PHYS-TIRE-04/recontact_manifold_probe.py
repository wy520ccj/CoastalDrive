"""冻结源码子进程观测Bullet再接触；不改原物理时序或生产配置。"""

import argparse
import csv
import gzip
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FROZEN = Path(__file__).parent / "mechanical-rigid/baseline-source"
TRIALS = ((2, 10), (8, 10), (2, 80), (8, 80))


def hashes():
    files = sorted((FROZEN / "src").rglob("*.py"))+sorted((FROZEN / "tools").rglob("*.py"))
    return {path.relative_to(FROZEN).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def worker(output, steps, iterations, geometry="plane", duration=1.1):
    sys.path[:0] = [str(FROZEN / "src"), str(FROZEN / "tools")]
    from panda3d.bullet import (
        BulletBoxShape,
        BulletManifoldPoint,
        BulletRigidBodyNode,
        BulletTriangleMesh,
        BulletTriangleMeshShape,
        BulletWheelRaycastInfo,
        BulletWorld,
    )
    from panda3d.core import BitMask32, ConfigVariableInt, TransformState, Vec3
    from physics import esc_probe as esc
    from physics.tire_compliance_probe import energy_summary, trial_config

    from driver_assist import SIMULATION_INPUT
    from driving_modes import REFERENCE_CAR
    from vehicle import Vehicle

    for module in (esc, sys.modules["vehicle"], sys.modules["tire_coupling"], sys.modules["wheel_dynamics"]):
        if not Path(module.__file__).resolve().is_relative_to(FROZEN.resolve()):
            raise ValueError(f"未导入冻结源码：{module.__file__}")
    solver = ConfigVariableInt("bullet-solver-iterations")
    solver.setValue(iterations)
    config = replace(trial_config("airborne-recontact", True, "simulation"), tire_substeps=steps)
    if geometry in ("box", "mesh"):
        def create_geometry_vehicle(vehicle_config):
            # 与冻结reference_ab创建时序相同，仅ground形状/放置替换。
            world = BulletWorld()
            world.setGravity(Vec3(0, 0, -9.81))
            ground = BulletRigidBodyNode("reference-ab-ground")
            if geometry == "box":
                ground.addShape(BulletBoxShape(Vec3(1000, 1000, .5)))
                ground.setTransform(TransformState.makePos(Vec3(0, 0, -.5)))
            else:
                mesh = BulletTriangleMesh()
                mesh.addTriangle(Vec3(-1000, -1000, 0), Vec3(1000, -1000, 0), Vec3(1000, 1000, 0))
                mesh.addTriangle(Vec3(-1000, -1000, 0), Vec3(1000, 1000, 0), Vec3(-1000, 1000, 0))
                ground.addShape(BulletTriangleMeshShape(mesh, dynamic=False))
            ground.setIntoCollideMask(BitMask32.bit(0) | BitMask32.bit(1))
            world.attachRigidBody(ground)
            spawn_z = .55+vehicle_config.center_of_mass_height-REFERENCE_CAR.center_of_mass_height
            vehicle = Vehicle(world, lambda _x, _y: True, (0, 0, spawn_z),
                              name="reference-ab-vehicle", config=vehicle_config, input_config=SIMULATION_INPUT)
            return world, vehicle
        esc._create_vehicle = create_geometry_vehicle
    before = hashes()
    captured = []
    calls = 0

    def body_state(body):
        pose = body.getTransform()
        angular = body.getAngularVelocity()
        orientation = pose.getQuat()
        local = orientation.conjugate().xform(angular)
        momentum = orientation.xform(Vec3(*(local[index]*config.body_inertia[index] for index in range(3))))
        return {"position": tuple(pose.getPos()), "orientation": tuple(orientation), "hpr": tuple(pose.getHpr()),
                "velocity": tuple(body.getLinearVelocity()), "angular_world": tuple(angular),
                "yaw_world_z": float(angular.z), "yaw_body_up": float(local.z),
                "angular_momentum_world": tuple(momentum)}

    def raycast_states(vehicle):
        result = []
        for index, wheel in enumerate(vehicle._vehicle.getWheels()):
            ray = wheel.getRaycastInfo()
            result.append({"wheel": index, "hard_point_ws": tuple(ray.getHardPointWs()),
                           "direction_ws": tuple(ray.getWheelDirectionWs()),
                           "contact_point_ws": tuple(ray.getContactPointWs()),
                           "contact_normal_ws": tuple(ray.getContactNormalWs()),
                           "suspension_length_m": float(ray.getSuspensionLength()),
                           "suspension_rest_length_m": float(wheel.getSuspensionRestLength()),
                           "wheel_radius_m": float(wheel.getWheelRadius()),
                           "contact_flag": bool(ray.isInContact())})
        return result

    def observed_step(world, vehicle, command):
        nonlocal calls
        calls += 1
        previous_velocity = Vec3(vehicle._chassis.getLinearVelocity())
        force_pose = vehicle._chassis.getTransform()
        force_contacts = vehicle._wheel_contacts
        force_tick = vehicle._contact_tick
        vehicle.apply_command(command)
        # airborne-recontact原入口不静置，首个调用即真实离地试验tick1。
        recording = True
        if recording:
            pre = body_state(vehicle._chassis)
            before_bullet = {"body": pre, "snapshot": asdict(vehicle.snapshot()),
                             "raycast_cache": raycast_states(vehicle),
                             "force_pose_position": tuple(force_pose.getPos()),
                             "force_pose_orientation": tuple(force_pose.getQuat()),
                             "force_contacts": [asdict(contact) for contact in force_contacts],
                             "force_contact_tick": force_tick,
                             "external_total_force_n": tuple(vehicle._chassis.getTotalForce()),
                             "external_total_torque_nm": tuple(vehicle._chassis.getTotalTorque())}
        world.doPhysics(esc.FIXED_DT, 0, esc.FIXED_DT)
        if recording:
            post = body_state(vehicle._chassis)
            manifolds = []
            summed_impulse = Vec3(0)
            summed_angular_impulse = Vec3(0)
            for manifold in world.getManifolds():
                a, b = manifold.getNode0(), manifold.getNode1()
                if a != vehicle._chassis and b != vehicle._chassis:
                    continue
                chassis_is_a = a == vehicle._chassis
                sign = 1 if chassis_is_a else -1
                points = []
                for point in manifold.getManifoldPoints():
                    normal = Vec3(point.getNormalWorldOnB())
                    normal_impulse = normal*(sign*point.getAppliedImpulse())
                    lateral1 = Vec3(point.getLateralFrictionDir1())
                    lateral2 = Vec3(point.getLateralFrictionDir2())
                    friction_impulse = (lateral1*point.getAppliedImpulseLateral1()+
                                        lateral2*point.getAppliedImpulseLateral2())*sign
                    impulse = normal_impulse+friction_impulse
                    position = Vec3(point.getPositionWorldOnA() if chassis_is_a else point.getPositionWorldOnB())
                    arm = position-Vec3(*pre["position"])
                    angular_impulse = arm.cross(impulse)
                    summed_impulse += impulse
                    summed_angular_impulse += angular_impulse
                    points.append({"distance_m": float(point.getDistance()), "normal_world_on_b": tuple(normal),
                                   "position_world_on_a": tuple(point.getPositionWorldOnA()),
                                   "position_world_on_b": tuple(point.getPositionWorldOnB()),
                                   "applied_normal_impulse_ns": float(point.getAppliedImpulse()),
                                   "lateral_initialized": bool(point.getLateralFrictionInitialized()),
                                   "lateral_direction_1": tuple(lateral1), "lateral_direction_2": tuple(lateral2),
                                   "applied_lateral_impulse_1_ns": float(point.getAppliedImpulseLateral1()),
                                   "applied_lateral_impulse_2_ns": float(point.getAppliedImpulseLateral2()),
                                   "index_a": int(point.getIndex0()), "index_b": int(point.getIndex1()),
                                   "part_id_a": int(point.getPartId0()), "part_id_b": int(point.getPartId1()),
                                   "chassis_impulse_ns": tuple(impulse), "chassis_normal_impulse_ns": tuple(normal_impulse),
                                   "chassis_friction_impulse_ns": tuple(friction_impulse),
                                   "angular_impulse_about_pre_cg_nms": tuple(angular_impulse)})
                manifolds.append({"node_a": a.getName(), "node_b": b.getName(), "chassis_is_a": chassis_is_a, "points": points})
            delta_p = (Vec3(*post["velocity"])-Vec3(*pre["velocity"]))*config.mass
            delta_l = Vec3(*post["angular_momentum_world"])-Vec3(*pre["angular_momentum_world"])
            captured.append({"tick": calls, "pre_bullet": before_bullet,
                             "post_bullet_raycast": raycast_states(vehicle),
                             "post_bullet": post, "manifolds": manifolds,
                             "observed_delta_p_ns": tuple(delta_p), "observed_delta_L_nms": tuple(delta_l),
                             "manifold_sum_impulse_ns": tuple(summed_impulse),
                             "manifold_sum_angular_impulse_about_pre_cg_nms": tuple(summed_angular_impulse),
                             "delta_p_minus_manifold_ns": tuple(delta_p-summed_impulse),
                             "delta_L_minus_manifold_nms": tuple(delta_l-summed_angular_impulse)})
        vehicle.after_step(previous_velocity)

    report = {"status": "running", "frozen_source_before": before,
              "solver_iterations_requested": iterations, "solver_iterations_prc_value": solver.getValue(),
              "solver_variable_description": solver.getDescription(),
              "module_paths": {name: sys.modules[name].__file__ for name in ("physics.esc_probe", "vehicle", "tire_coupling", "wheel_dynamics")},
              "manifold_API": {name: getattr(BulletManifoldPoint, name).__doc__ for name in (
                  "getAppliedImpulse", "getAppliedImpulseLateral1", "getAppliedImpulseLateral2",
                  "getLateralFrictionDir1", "getLateralFrictionDir2", "getNormalWorldOnB",
                  "getPositionWorldOnA", "getPositionWorldOnB", "getDistance")},
              "raycast_API": {name: getattr(BulletWheelRaycastInfo, name).__doc__ for name in (
                  "getHardPointWs", "getWheelDirectionWs", "getContactPointWs", "getContactNormalWs",
                  "getSuspensionLength", "isInContact")}}
    try:
        esc._step = observed_step
        summary, rows = esc.run_trial("airborne-recontact", True, duration, "simulation", vehicle_config=config)
        esc.write_csv(output / "esc.csv.gz", rows)
        with gzip.open(output / "manifold.jsonl.gz", "wt", encoding="utf-8") as stream:
            for row in captured:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+"\n")
        report.update(status="completed", trial=summary, energy=energy_summary(rows), geometry=geometry,
                      maximum_abs_xy_m=max(max(abs(row["state.position.0"]), abs(row["state.position.1"])) for row in rows),
                      captured_ticks=len(captured),
                      first_nonzero_manifold_impulse_tick=next((row["tick"] for row in captured if any(row["manifold_sum_impulse_ns"])), None),
                      tick80=captured[79])
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["frozen_source_after"] = hashes()
        report["frozen_source_unchanged"] = before == report["frozen_source_after"]
        write_json(output / "summary.json", report)


def compare_reference(path, old_path):
    def read(p):
        with gzip.open(p, "rt", newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))
    new, old = read(path), read(old_path)[:133]
    different = []
    shared = set(new[0]) & set(old[0])
    for a, b in zip(new, old):
        for key in sorted(shared):
            if a[key] != b[key]:
                different.append({"tick": int(a["tick"]), "field": key, "new": a[key], "old": b[key]})
    return {"reference": old_path.relative_to(ROOT).as_posix(),
            "reference_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
            "rows_new": len(new), "rows_reference": len(old), "shared_fields": len(shared),
            "different_cells": len(different), "first_differences": different[:10],
            "strict_equal_existing_cells": len(new) == len(old) and not different}


def run(output, geometry="plane", duration=1.1, selected_steps=None):
    output.mkdir(parents=True, exist_ok=False)
    before = hashes()
    trials = (tuple((steps, 10) for steps in (selected_steps or (2, 8))) if geometry != "plane" else TRIALS)
    pending = list(trials)
    report = {"status": "running", "frozen_source_before": before, "trials": [], "protocol": {
        "baseline": "git archive f2c145090d7c2342b0ba242bca8a066732748b0c src+tools; child process imports only frozen source",
        "ordering": "previous_velocity; apply_command; observe pre-Bullet; doPhysics(dt,0,dt); observe post-Bullet/manifolds; after_step(previous_velocity)",
        "scope": "selected tire substeps; plane10/80 or box10 contact-solver iterations; diagnostic only, no production setting or acceptance change",
        "geometry": geometry, "duration_s": duration,
        "box_geometry": "ground half extents(1000,1000,.5), body origin z=-.5, top z=0; finite thick geometry differs from infinite plane; retain gravity/collision/input/masks/config",
        "mesh_geometry": "static mesh two +Z-wound horizontal triangles at z0, corners +/-1000, shared diagonal x=y; finite boundary and diagonal contacts checked by point/index",
        "impulse_sign": "normal_world_on_b and lateral friction directions multiplied by reported impulse; + for chassis nodeA, - for nodeB",
        "angular_momentum": "R*diag(body_inertia)*R^-1*omega_world, separate pre/post poses; manifold moment about pre-Bullet CG using post contact positions",
        "limitations": "manifold excludes raycast suspension and other external contributions; gyro/integration and moment-arm changes remain; difference cannot all be assigned to collision",
        "yaw": "both world angular.z and body-up projection recorded; no coordinate conflation"}}
    try:
        for steps, iterations in trials:
            child = output / f"steps{steps}-solver{iterations}"
            child.mkdir()
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--output", str(child.resolve()),
                                     "--steps", str(steps), "--iterations", str(iterations), "--geometry", geometry,
                                     "--duration", str(duration)], cwd=FROZEN, capture_output=True, text=True, check=False)
            (child / "execution.log").write_text(result.stdout+result.stderr, encoding="utf-8")
            if result.returncode:
                raise RuntimeError(f"frozen child failed: {child.name}, exit={result.returncode}")
            summary = json.loads((child / "summary.json").read_text(encoding="utf-8"))
            if iterations == 10 and geometry == "plane" and duration == 1.1:
                old = ROOT / f"docs/evidence/PHYS-TIRE-03/substeps/simulation-airborne-recontact-{steps}.csv.gz"
                summary["existing_reference_comparison"] = compare_reference(child / "esc.csv.gz", old)
            report["trials"].append({"steps": steps, "solver_iterations": iterations, "directory": child.name, **summary})
            pending.remove((steps, iterations))
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", failed_trial=pending[0], not_run=pending[1:], error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["frozen_source_after"] = hashes()
        report["frozen_source_unchanged"] = before == report["frozen_source_after"]
        report["probe_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        write_json(output / "summary.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--steps", type=int)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--geometry", choices=("plane", "box", "mesh"), default="plane")
    parser.add_argument("--duration", type=float, default=1.1)
    parser.add_argument("--substeps", nargs="+", type=int)
    args = parser.parse_args()
    if args.worker:
        worker(args.output, args.steps, args.iterations, args.geometry, args.duration)
    else:
        run(args.output, args.geometry, args.duration, args.substeps)
