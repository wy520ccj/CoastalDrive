"""保留历史Box内核与圆角margin的凸包支撑诊断，不改变通用凸体支持函数。"""

import argparse
import gzip
import hashlib
import importlib.util
import json
import subprocess
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = HERE / "mechanical-rigid/baseline-source"


def observer_module():
    spec = importlib.util.spec_from_file_location("manifold_observer", HERE / "recontact_manifold_cache_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def worker(output, variant, steps, duration, iterations):
    sys.path[:0] = [str(FROZEN / "src"), str(FROZEN / "tools")]
    from panda3d.bullet import BulletBoxShape, BulletConvexHullShape
    from panda3d.core import ConfigVariableBool, TransformState, Vec3
    from physics import esc_probe

    observer = observer_module()
    create = esc_probe._create_vehicle
    geometry = {}
    ConfigVariableBool("bullet-split-impulse").setValue(False)

    def describe(body):
        children, corners = [], []
        for index in range(body.getNumShapes()):
            shape, pose = body.getShape(index), body.getShapeTransform(index)
            points = (geometry["input_hull_points"] if isinstance(shape, BulletConvexHullShape) else
                      [tuple(shape.getHalfExtentsWithMargin()[a]*sign[a] for a in range(3))
                       for sign in product((-1, 1), repeat=3)])
            children.append({"input_points": points, "margin": shape.getMargin(),
                             "matrix": [[pose.getMat().getCell(a, b) for b in range(4)] for a in range(4)]})
            corners.extend(tuple(pose.getMat().xformPoint(Vec3(*point))) for point in points)
        margin = body.getShape(0).getMargin() if isinstance(body.getShape(0), BulletConvexHullShape) else 0
        return {"children": children, "nominal_corner_aabb_min": [min(p[a] for p in corners)-margin for a in range(3)],
                "nominal_corner_aabb_max": [max(p[a] for p in corners)+margin for a in range(3)],
                "nominal_corners": corners, "mass": body.getMass(), "inertia": tuple(body.getInertia())}

    def create_partition(config):
        world, car = create(config)
        body = car._chassis
        geometry["before"] = describe(body)
        if variant != "original":
            shape = body.getShape(0)
            half, center = shape.getHalfExtentsWithoutMargin(), body.getShapeTransform(0).getPos()
            original_margin = shape.getMargin()
            body.removeShape(shape)
            signs = list(product((-1, 0, 1), repeat=3)) if variant == "hull-centers" else list(product((-1, 1), repeat=3))
            # 面/边中点在角点前；它们不改变凸包体积，只参与支持值相同的选择。
            signs = sorted((p for p in signs if p != (0, 0, 0)), key=lambda p: sum(v != 0 for v in p))
            geometry["input_hull_points"] = [tuple(half[a]*p[a] for a in range(3)) for p in signs]
            hull = BulletConvexHullShape()
            hull.setMargin(original_margin)
            for point in geometry["input_hull_points"]:
                hull.addPoint(Vec3(*point))
            body.addShape(hull, TransformState.makePos(center))
            body.setInertia(Vec3(*config.body_inertia))
        geometry["after"] = describe(body)
        geometry["nominal_aabb_max_error_m"] = max(abs(geometry["after"][key][a]-geometry["before"][key][a])
                                                   for key in ("nominal_corner_aabb_min", "nominal_corner_aabb_max") for a in range(3))
        geometry["limitations"] = "Both hull variants use the exact original Box inner half extents and .04m margin. General GJK support function and physical rounded convex volume are preserved. Box specialized plane support used the sharp outer vertex instead; native plane manifold changes deliberately."
        return world, car

    esc_probe._create_vehicle = create_partition
    try:
        observer.worker(output, steps, iterations, "plane", duration)
    finally:
        path = output / "summary.json"
        report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "failed"}
        report.update(variant=variant, geometry=geometry)
        save(path, report)


def run(output, variants, steps, duration, iterations):
    output.mkdir(parents=True, exist_ok=False)
    observer = observer_module()
    before = observer.hashes()
    plan = [(variant, count) for variant in variants for count in steps]
    report = {"status": "running", "source_before": before, "trials": [], "not_run": plan.copy(),
              "protocol": {"source": "frozen f2c1450", "world": "original infinite plane, gravity, masks, 120Hz",
                           "duration_s": duration, "solver_iterations": iterations, "split_impulse": False,
                           "initialization": "same airborne +2m and rolling speed; collider replacement before first step only",
                           "scope": "native equal-volume convex hull redundant support diagnosis; no production/source/controller change"}}
    try:
        for variant, count in plan:
            child = output / f"{variant}-steps{count}"
            child.mkdir()
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--output", str(child.resolve()),
                                     "--variant", variant, "--steps", str(count), "--duration", str(duration),
                                     "--iterations", str(iterations)], capture_output=True, text=True, check=False)
            (child / "execution.log").write_text(result.stdout+result.stderr, encoding="utf-8")
            result.check_returncode()
            trial = json.loads((child / "summary.json").read_text(encoding="utf-8"))
            if variant == "original" and iterations == 10:
                trial["baseline_comparison"] = observer.compare_reference(child / "esc.csv.gz",
                    HERE.parent / f"PHYS-TIRE-03/substeps/simulation-airborne-recontact-{count}.csv.gz")
                if not trial["baseline_comparison"]["strict_equal_existing_cells"]:
                    raise ValueError("original不等于既有基线")
            with gzip.open(child / "manifold.jsonl.gz", "rt", encoding="utf-8") as stream:
                rows = [json.loads(line) for line in stream]
            first = next((row for row in rows if any(p["applied_normal_impulse_ns"] > 0 for m in row["manifolds"] for p in m["points"])), None)
            trial["first_impulse"] = None if first is None else {
                "tick": first["tick"], "pre_body": first["pre_bullet"]["body"], "post_body": first["post_bullet"],
                "points": [p for m in first["manifolds"] for p in m["points"] if p["applied_normal_impulse_ns"] > 0]}
            save(child / "summary.json", trial)
            report["trials"].append({"variant": variant, "tire_substeps": count, "directory": child.name, **trial})
            report["not_run"].pop(0)
            save(output / "summary.json", report)
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["source_after"] = observer.hashes()
        report["source_unchanged"] = before == report["source_after"]
        report["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        save(output / "summary.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--variant", choices=("original", "hull-corners", "hull-centers"))
    parser.add_argument("--variants", nargs="+", default=("original", "hull-corners", "hull-centers"))
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--substeps", nargs="+", type=int, default=(2,))
    parser.add_argument("--duration", type=float, default=1.1)
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()
    if args.worker:
        worker(args.output, args.variant, args.steps, args.duration, args.iterations)
    else:
        run(args.output, args.variants, args.substeps, args.duration, args.iterations)
