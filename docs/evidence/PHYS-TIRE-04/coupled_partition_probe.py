"""冻结源码四分块接触与共同micro积分原型；控制/动力120Hz，不用于生产。"""

import argparse
import csv
import gzip
import hashlib
import inspect
import json
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FROZEN = Path(__file__).parent / "mechanical-rigid/baseline-source"
MACRO_DT = 1/120
MICRO_COUNTS = (1, 2, 4, 8)
DISSIPATIONS = ("material_dissipation", "road_dissipation", "elastic_numerical_dissipation", "frame_dissipation")


def source_hashes():
    files = sorted((FROZEN / "src").rglob("*.py"))+sorted((FROZEN / "tools").rglob("*.py"))
    hashes = {path.relative_to(FROZEN).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    hashes["prototype/coupled_time_probe.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return hashes


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def load_frozen():
    sys.path[:0] = [str(FROZEN / "src"), str(FROZEN / "tools")]
    from physics import esc_probe

    import vehicle
    from powertrain import Powertrain
    from vehicle_brakes import Brakes
    from vehicle_stability import StabilityControl
    from vehicle_steering import SteeringRack
    from vehicle_traction import TractionControl

    signatures = {}
    for cls in (SteeringRack, TractionControl, StabilityControl, Powertrain, Brakes):
        signature = inspect.signature(cls.advance)
        positional = [parameter for parameter in signature.parameters.values()
                      if parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        if positional[-1].name != "dt":
            raise ValueError(f"控制advance最后位置参数不是dt：{cls.__name__}{signature}")
        signatures[cls.__name__] = str(signature)
    for name in ("physics.esc_probe", "vehicle", "tire_coupling", "wheel_dynamics", "powertrain"):
        if not Path(sys.modules[name].__file__).resolve().is_relative_to(FROZEN.resolve()):
            raise ValueError(f"未导入冻结源码：{name}")
    return esc_probe, vehicle, signatures


def worker(output, count):
    esc, vehicle_module, signatures = load_frozen()
    from itertools import product

    from panda3d.bullet import BulletBoxShape
    from panda3d.core import ConfigVariableBool, ConfigVariableInt, Mat4, TransformState, Vec3
    from physics.tire_compliance_probe import trial_config

    ConfigVariableInt("bullet-solver-iterations").setValue(10)
    ConfigVariableBool("bullet-split-impulse").setValue(False)
    micro_dt = MACRO_DT/count
    vehicle_module.FIXED_DT = micro_dt
    config = replace(trial_config("airborne-recontact", True, "simulation"), tire_substeps=2)
    create_original = esc._create_vehicle
    controller_results = {}
    controller_calls = {name: 0 for name in ("steering", "traction", "stability", "powertrain", "brakes")}
    last_force_frame = {}
    original_contact_moments = esc.tire_contact_moments
    micro_index = 0
    macro_tick = 0
    aggregates = []
    before = source_hashes()

    def cached_advance(name, original):
        def advance(*args, **kwargs):
            if micro_index == 0:
                # dt最后位置参数已独立签名核对；真实控制器每macro只推进一次。
                controller_results[name] = original(*args[:-1], MACRO_DT, **kwargs)
                controller_calls[name] += 1
            return controller_results[name]
        return advance

    def create_observed(vehicle_config):
        world, car = create_original(vehicle_config)
        body_node = car._chassis
        shape = body_node.getShape(0)
        half, center = shape.getHalfExtentsWithMargin(), body_node.getShapeTransform(0).getPos()
        body_node.removeShape(shape)
        for sx, sy in product((-1, 1), repeat=2):
            matrix = Mat4(sx, 0, 0, 0, 0, sy, 0, 0, 0, 0, sx*sy, 0,
                          center.x+sx*half.x/2, center.y+sy*half.y/2, center.z, 1)
            body_node.addShape(BulletBoxShape(Vec3(half.x/2, half.y/2, half.z)), TransformState.makeMat(matrix))
        body_node.setInertia(Vec3(*vehicle_config.body_inertia))
        for name, component in (("steering", car.steering), ("traction", car.traction),
                                ("stability", car.stability), ("powertrain", car.powertrain), ("brakes", car.brakes)):
            component.advance = cached_advance(name, component.advance)
        return world, car

    def body(body_node):
        pose = body_node.getTransform()
        angular = body_node.getAngularVelocity()
        return {"position": tuple(pose.getPos()), "orientation": tuple(pose.getQuat()), "hpr": tuple(pose.getHpr()),
                "velocity": tuple(body_node.getLinearVelocity()), "angular_world": tuple(angular),
                "yaw_world_z": float(angular.z), "yaw_body_up": float(pose.getQuat().conjugate().xform(angular).z)}

    def observed_step(world, car, command):
        nonlocal macro_tick, micro_index
        macro_tick += 1
        summed = [{field: 0.0 for field in DISSIPATIONS} for _ in range(4)]
        residual = [0.0]*4
        for micro_index in range(count):
            previous_velocity = Vec3(car._chassis.getLinearVelocity())
            last_force_frame["pose"] = car._chassis.getTransform()
            last_force_frame["contacts"] = car._wheel_contacts
            last_force_frame["tick"] = car._contact_tick
            force_contacts = [asdict(contact) for contact in car._wheel_contacts]
            force_tick = car._contact_tick
            car.apply_command(command)
            pre = {"body": body(car._chassis), "snapshot": asdict(car.snapshot()),
                   "force_contacts": force_contacts, "force_contact_tick": force_tick,
                   "external_force": tuple(car._chassis.getTotalForce()), "external_torque": tuple(car._chassis.getTotalTorque())}
            world.doPhysics(micro_dt, 0, micro_dt)
            post = body(car._chassis)
            manifolds = []
            for manifold in world.getManifolds():
                a, b = manifold.getNode0(), manifold.getNode1()
                if a != car._chassis and b != car._chassis:
                    continue
                manifolds.append({"a": a.getName(), "b": b.getName(), "chassis_is_a": a == car._chassis,
                                  "points": [{"distance": float(point.getDistance()),
                                              "normal_b": tuple(point.getNormalWorldOnB()),
                                              "point_a": tuple(point.getPositionWorldOnA()), "point_b": tuple(point.getPositionWorldOnB()),
                                              "normal_impulse_ns": float(point.getAppliedImpulse()),
                                              "lateral_direction_1": tuple(point.getLateralFrictionDir1()),
                                              "lateral_direction_2": tuple(point.getLateralFrictionDir2()),
                                              "lateral_impulse_1_ns": float(point.getAppliedImpulseLateral1()),
                                              "lateral_impulse_2_ns": float(point.getAppliedImpulseLateral2())}
                                             for point in manifold.getManifoldPoints()]})
            car.after_step(previous_velocity)
            state = car.snapshot()
            for index, wheel in enumerate(state.wheel_dynamics):
                summed[index]["material_dissipation"] += wheel.material_dissipation
                summed[index]["road_dissipation"] += wheel.road_dissipation
                summed[index]["elastic_numerical_dissipation"] += wheel.elastic_numerical_dissipation
                summed[index]["frame_dissipation"] += wheel.frame_dissipation
                residual[index] = max(residual[index], abs(wheel.force_residual))
            row = {"macro_tick": macro_tick, "micro_index": micro_index, "micro_sample_tick": car._contact_tick,
                   "time_s": (macro_tick-1)*MACRO_DT+(micro_index+1)*micro_dt, "command": asdict(command),
                   "controller_advanced_this_micro": micro_index == 0, "pre_bullet": pre,
                   "post_bullet_body": post, "completed_snapshot": asdict(state), "manifolds": manifolds}
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+"\n")
        aggregates.append({"macro_tick": macro_tick, "wheel_dissipation_sum_j": summed,
                           "peak_abs_force_residual_n": residual})

    def last_micro_contact_moments(pose, contacts, tick, wheels):
        if count == 1:
            return original_contact_moments(pose, contacts, tick, wheels)
        # 原观察器只支持一个物理步；多micro必须使用lastmicro实际施力帧，保留原tick断言。
        moments = original_contact_moments(last_force_frame["pose"], last_force_frame["contacts"],
                                           last_force_frame["tick"], wheels)
        for values in moments:
            for name in ("mean_fx_contact_yaw_nm", "mean_fy_contact_yaw_nm", "mean_total_contact_yaw_nm"):
                values[name] *= count  # 原helper除macroDT，lastmicro冲量须除microDT。
        return moments

    report = {"status": "running", "source_before": before, "micro_count": count, "micro_dt_s": micro_dt,
              "macro_dt_s": MACRO_DT, "controller_dt_s": MACRO_DT, "advance_signatures": signatures,
              "prototype": "single world; original plane/config/commands/init; controller results advance once per macro then held; tire/brake torque/contacts/elasticity and Bullet suspension/collision advance each micro; vehicle module dt changed in child only",
              "module_paths": {name: sys.modules[name].__file__ for name in ("physics.esc_probe", "vehicle", "tire_coupling", "wheel_dynamics")}}
    try:
        with gzip.open(output / "micro.jsonl.gz", "wt", encoding="utf-8") as stream:
            esc._create_vehicle = create_observed
            esc._step = observed_step
            esc.tire_contact_moments = last_micro_contact_moments
            summary, rows = esc.run_trial("airborne-recontact", True, 6, "simulation", vehicle_config=config)
        for row, aggregate in zip(rows[1:], aggregates):
            for index in range(4):
                for field in DISSIPATIONS:
                    row[f"macro_micro_sum.{index}.{field}_j"] = aggregate["wheel_dissipation_sum_j"][index][field]
                row[f"macro_micro_peak.{index}.force_residual_n"] = aggregate["peak_abs_force_residual_n"][index]
        esc.write_csv(output / "esc-macro.csv.gz", rows)
        report.update(status="completed", trial=summary, controller_actual_calls=controller_calls,
                      macro_ticks=macro_tick, micro_ticks=macro_tick*count,
                      micro_dissipation_sum_j=[{field: sum(aggregate["wheel_dissipation_sum_j"][index][field] for aggregate in aggregates)
                                               for field in DISSIPATIONS} for index in range(4)])
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["source_after"] = source_hashes()
        report["source_unchanged"] = before == report["source_after"]
        write_json(output / "summary.json", report)


def compare_baseline(new_path):
    old_path = ROOT / "docs/evidence/PHYS-TIRE-04/box-partition-full/quarters-steps2/esc.csv.gz"
    def read(path):
        with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))
    new, old = read(new_path), read(old_path)
    fields = sorted(set(new[0]) & set(old[0]))
    differences = [{"tick": int(a["tick"]), "field": field, "new": a[field], "old": b[field]}
                   for a, b in zip(new, old) for field in fields if a[field] != b[field]]
    return {"reference": old_path.relative_to(ROOT).as_posix(), "reference_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
            "new_rows": len(new), "old_rows": len(old), "shared_fields": len(fields),
            "different_cells": len(differences), "first_differences": differences[:20],
            "strict_equal": len(new) == len(old) == 721 and not differences}


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    pending = list(MICRO_COUNTS)
    report = {"status": "running", "source_before": before, "trials": [], "protocol": {
        "external_macro": "120Hz command/sampling, 720macro ticks; steering/TCS/ESC/powertrain/brakes actual updates once per macro with dt1/120",
        "physics_micro": "1/2/4/8 common tire + Bullet + suspension + after_step micro subdivisions; tire_substeps fixed2; one authoritative world",
        "energy": "intrinsic state dissipation fields describe last micro only; extra macro_micro_sum columns sum all micro contributions and macro_micro_peak columns preserve residual maxima",
        "ticks": "sample_tick/contact_tick/feedback_tick are micro indices; CSV tick/time are macro; raw JSONL labels both",
        "contact_moment": "lastmicro actual force pose/contact/tick; original consistency assertion retained; mean force uses micro impulse/microdt, not macro-start geometry",
        "scope": "diagnostic integration protocol prototype only; not production implementation or acceptance threshold",
        "baseline_gate": "micro1 must match all 721 rows existing plane shared fields exactly before other trials"}}
    try:
        for count in MICRO_COUNTS:
            child = output / f"micro{count}"
            child.mkdir()
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--count", str(count),
                                     "--output", str(child.resolve())], cwd=FROZEN, capture_output=True, text=True, check=False)
            (child / "execution.log").write_text(result.stdout+result.stderr, encoding="utf-8")
            if result.returncode:
                raise RuntimeError(f"micro{count}子进程失败，exit={result.returncode}")
            trial = json.loads((child / "summary.json").read_text(encoding="utf-8"))
            report["trials"].append(trial)
            if count == 1:
                comparison = compare_baseline(child / "esc-macro.csv.gz")
                report["micro1_baseline"] = comparison
                if not comparison["strict_equal"]:
                    raise ValueError("micro1与冻结plane共享字段不相等，停止后续原型试验")
            pending.remove(count)
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", failed_trial=pending[0], not_run=pending[1:], error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["source_after"] = source_hashes()
        report["source_unchanged"] = before == report["source_after"]
        write_json(output / "summary.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--count", type=int, choices=MICRO_COUNTS)
    parser.add_argument("--check-imports", action="store_true")
    args = parser.parse_args()
    if args.check_imports:
        _esc, _vehicle, checked_signatures = load_frozen()
        print(json.dumps({"signatures": checked_signatures, "module": _vehicle.__file__, "physics_started": False}, indent=2))
    elif args.worker:
        worker(args.output, args.count)
    else:
        if args.output is None:
            parser.error("--output is required for execution")
        run(args.output)
