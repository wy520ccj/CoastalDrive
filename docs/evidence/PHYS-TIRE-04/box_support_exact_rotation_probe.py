"""冻结单box原/精确四元数Z180度等实体表示，诊断支持顶点坐标偏置。"""
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


def load_observer():
    path = HERE / "recontact_manifold_probe.py"
    spec = importlib.util.spec_from_file_location("frozen_manifold_observer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def worker(output, variant):
    sys.path[:0] = [str(FROZEN / "src"), str(FROZEN / "tools")]
    from panda3d.bullet import BulletRigidBodyNode
    from panda3d.core import ConfigVariableBool, Quat, TransformState, Vec3
    from physics import esc_probe

    observer = load_observer()
    ConfigVariableBool("bullet-split-impulse").setValue(False)
    create = esc_probe._create_vehicle
    geometry = {}

    def describe(body):
        shape, local = body.getShape(0), body.getShapeTransform(0)
        half = shape.getHalfExtentsWithMargin()
        corners = sorted(tuple(local.getMat().xformPoint(Vec3(*(half[i] * signs[i] for i in range(3)))))
                         for signs in product((-1, 1), repeat=3))
        return {"corners_local": corners, "corner_aabb_min": [min(p[i] for p in corners) for i in range(3)],
                "corner_aabb_max": [max(p[i] for p in corners) for i in range(3)],
                "shape_count": body.getNumShapes(), "half_extents_with_margin": tuple(half),
                "half_extents_without_margin": tuple(shape.getHalfExtentsWithoutMargin()),
                "margin": shape.getMargin(), "shape_transform_position": tuple(local.getPos()),
                "shape_transform_hpr": tuple(local.getHpr()),
                "shape_transform_quat_wxyz": tuple(local.getQuat()),
                "shape_transform_matrix": [[local.getMat().getCell(i, j) for j in range(4)] for i in range(4)], "shape_bounds_native": str(body.getShapeBounds()),
                "mass": body.getMass(), "inertia": tuple(body.getInertia()),
                "body_pose": tuple(body.getTransform().getPos()), "body_hpr": tuple(body.getTransform().getHpr())}

    def create_variant(config):
        world, car = create(config)
        body = car._chassis
        geometry["before"] = describe(body)
        if variant == "mirror":
            shape = body.getShape(0)
            center = body.getShapeTransform(0).getPos()
            body.removeShape(shape)
            rotation = Quat(0, 0, 0, 1)
            assert tuple(rotation.xform(Vec3(1, 0, 0))) == (-1.0, 0.0, 0.0)
            assert tuple(rotation.xform(Vec3(0, 1, 0))) == (0.0, -1.0, 0.0)
            assert tuple(rotation.xform(Vec3(0, 0, 1))) == (0.0, 0.0, 1.0)
            requested = TransformState.makePosQuatScale(center, rotation, Vec3(1))
            geometry["requested_quaternion_wxyz"] = tuple(rotation)
            geometry["requested_transform_quaternion_wxyz"] = tuple(requested.getQuat())
            geometry["requested_transform_matrix"] = [[requested.getMat().getCell(i, j) for j in range(4)] for i in range(4)]
            body.addShape(shape, requested)
            body.setInertia(Vec3(*config.body_inertia))
        geometry["after"] = describe(body)
        old, new = geometry["before"]["corners_local"], geometry["after"]["corners_local"]
        geometry["maximum_nearest_corner_error_m"] = max(min(sum((a[i] - b[i]) ** 2 for i in range(3)) ** .5 for b in new) for a in old)
        geometry["maximum_corner_aabb_error_m"] = max(abs(geometry["before"][key][i] - geometry["after"][key][i]) for key in ("corner_aabb_min", "corner_aabb_max") for i in range(3))
        return world, car

    esc_probe._create_vehicle = create_variant
    try:
        observer.worker(output, 2, 10, "plane", 1.1)
        trajectory = output / "manifold.jsonl.gz"
        with gzip.open(trajectory, "rt", encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle]
        child_rotation = Quat(*geometry["after"]["shape_transform_quat_wxyz"])
        for record in records:
            body_rotation = Quat(*record["pre_bullet"]["body"]["orientation"])
            world_to_shape = child_rotation.conjugate() * body_rotation.conjugate()
            record["pre_bullet"]["world_up_in_shape_local"] = tuple(world_to_shape.xform(Vec3(0, 0, 1)))
            record["manifold_normals_in_pre_shape_local"] = [
                tuple(world_to_shape.xform(Vec3(*point["normal_world_on_b"])))
                for manifold in record["manifolds"] for point in manifold["points"]]
        with gzip.open(trajectory, "wt", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, allow_nan=False) + "\n")
    finally:
        path = output / "summary.json"
        report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "failed"}
        report.update(variant=variant, geometry_equivalence=geometry,
                      split_impulse_prc_value=ConfigVariableBool("bullet-split-impulse").getValue(),
                      shape_API={name: BulletRigidBodyNode.__dict__.get(name).__doc__
                                 if name in BulletRigidBodyNode.__dict__ else getattr(BulletRigidBodyNode, name).__doc__
                                 for name in ("getShape", "getShapeTransform", "removeShape", "addShape", "getInertia", "setInertia")})
        write(path, report)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    observer = load_observer()
    pending = ["original", "mirror"]
    report = {"status": "running", "source_before": observer.hashes(), "trials": [],
              "protocol": "frozen f2c1450 src/tools; n2,120Hz,solver10,splitFalse,unchanged infinite plane;132 ticks; single box mirror exact Quat(w=0,x=0,y=0,z=1) before first step only; mass/CG/hardware preserved, explicit reference inertia restored; diagnosis only, no production repair"}
    try:
        for variant in pending.copy():
            child = output / variant
            child.mkdir()
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--variant", variant,
                                     "--output", str(child.resolve())], capture_output=True, text=True, check=False)
            (child / "execution.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            result.check_returncode()
            trial = json.loads((child / "summary.json").read_text(encoding="utf-8"))
            if variant == "original":
                trial["old_133_rows_comparison"] = observer.compare_reference(child / "esc.csv.gz", HERE.parent / "PHYS-TIRE-03/substeps/simulation-airborne-recontact-2.csv.gz")
                if not trial["old_133_rows_comparison"]["strict_equal_existing_cells"]:
                    raise ValueError("original与旧133行共享字段不严格相等")
            with gzip.open(child / "manifold.jsonl.gz", "rt", encoding="utf-8") as handle:
                contacts = [json.loads(line) for line in handle]
            first = next((row for row in contacts if any(point["applied_normal_impulse_ns"] != 0 for manifold in row["manifolds"] for point in manifold["points"])), None)
            trial["first_impulse_row"] = first
            write(child / "summary.json", trial)
            report["trials"].append({"variant": variant, "directory": variant, "summary": trial})
            pending.remove(variant)
            write(output / "summary.json", report)
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", failed_trial=pending[0] if pending else None,
                      not_run=pending[1:], error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["source_after"] = observer.hashes()
        report["source_unchanged"] = report["source_before"] == report["source_after"]
        report["probe_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        write(output / "summary.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--variant", choices=("original", "mirror"))
    args = parser.parse_args()
    if args.worker:
        worker(args.output, args.variant)
    else:
        run(args.output)
