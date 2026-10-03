"""Read-only CG-projected collision partition prototype on the plane-impact fixture."""

import hashlib
import itertools
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import Mat4, TransformState, Vec3

from driving_modes import REFERENCE_CAR
from vehicle_config import body_center
from vehicle_state import FIXED_DT


EVIDENCE = Path(__file__).resolve().parent
OUT = EVIDENCE
CAPTURED_CENTERED_COLLISION_SHA256 = (
    "2e6d2438f825be5884199dda21b02e6858cfac666642a60a9af7411d396a1a59"
)
SOURCE_FILES = (
    "src/vehicle_collision.py",
    "src/vehicle_config.py",
    "src/driving_modes.py",
    "src/vehicle_state.py",
    "docs/evidence/PHYS-TIRE-04/cg-plane-impact-probe.py",
)


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_hashes():
    return {name: file_sha256(ROOT / name) for name in SOURCE_FILES}


def axis_intervals(low, high):
    boundaries = [low]
    if low < 0 < high:
        boundaries.append(0.0)
    boundaries.append(high)
    return tuple((a, b) for a, b in zip(boundaries, boundaries[1:]))


def cg_projected_shapes(config):
    """Partition the nominal body box at the local CG projection, with no margin."""
    center = Vec3(*body_center(config))
    xs = axis_intervals(center.x - config.collision_half_width,
                        center.x + config.collision_half_width)
    ys = axis_intervals(center.y - config.collision_half_length,
                        center.y + config.collision_half_length)
    parts = []
    for x_interval, y_interval in itertools.product(xs, ys):
        x_low, x_high = x_interval
        y_low, y_high = y_interval
        half = Vec3((x_high - x_low) / 2,
                    (y_high - y_low) / 2,
                    config.collision_half_height)
        shape_center = Vec3((x_high + x_low) / 2,
                            (y_high + y_low) / 2,
                            center.z)
        sx = -1 if shape_center.x < 0 else 1
        sy = -1 if shape_center.y < 0 else 1
        shape = BulletBoxShape(half)
        shape.setMargin(0)
        matrix = Mat4(Mat4.identMat())
        matrix.setCell(0, 0, -sx)
        matrix.setCell(1, 1, -sy)
        matrix.setCell(2, 2, sx * sy)
        matrix.setRow(3, (shape_center.x, shape_center.y, shape_center.z, 1))
        parts.append((shape, TransformState.makeMat(matrix)))
    return tuple(parts)


def captured_centered_shapes(config):
    """Reconstructed old four-Box geometry from the recorded 2e6d... source SHA."""
    half = Vec3(config.collision_half_width, config.collision_half_length,
                config.collision_half_height)
    center = Vec3(*body_center(config))
    half = Vec3(half.x / 2, half.y / 2, half.z)
    parts = []
    for sx, sy in itertools.product((-1, 1), repeat=2):
        shape = BulletBoxShape(half)
        shape.setMargin(0)
        matrix = Mat4(Mat4.identMat())
        matrix.setCell(0, 0, -sx)
        matrix.setCell(1, 1, -sy)
        matrix.setCell(2, 2, sx * sy)
        matrix.setRow(3, (center.x + sx * half.x,
                          center.y + sy * half.y, center.z, 1))
        parts.append((shape, TransformState.makeMat(matrix)))
    return tuple(parts)


def vec_tuple(value):
    return tuple(float(value[index]) for index in range(3))


def matrix_rows(matrix):
    return [[float(matrix.getCell(row, column)) for column in range(4)]
            for row in range(4)]


def read_original_box_inertia(config):
    body = BulletRigidBodyNode("original-whole-box-inertia")
    body.setMass(config.mass)
    original = BulletBoxShape(Vec3(config.collision_half_width,
                                   config.collision_half_length,
                                   config.collision_half_height))
    body.addShape(original, TransformState.makePos(Vec3(*body_center(config))))
    return vec_tuple(body.getInertia())


def make_body(config, representation):
    body = BulletRigidBodyNode("impact-body")
    body.setMass(config.mass)
    body.setDeactivationEnabled(False)
    if representation == "captured-pre-change-centered-boxes":
        readback_inertia = read_original_box_inertia(config)
        for shape, pose in captured_centered_shapes(config):
            body.addShape(shape, pose)
        body.setInertia(Vec3(*config.body_inertia))
    elif representation == "prototype-cg-projected-boxes":
        original = BulletBoxShape(Vec3(config.collision_half_width,
                                       config.collision_half_length,
                                       config.collision_half_height))
        original_pose = TransformState.makePos(Vec3(*body_center(config)))
        body.addShape(original, original_pose)
        readback_inertia = vec_tuple(body.getInertia())
        body.removeShape(original)
        for shape, pose in cg_projected_shapes(config):
            body.addShape(shape, pose)
        # Keep the explicit reference-car inertia after the native whole-Box read.
        body.setInertia(Vec3(*config.body_inertia))
    else:
        raise ValueError(representation)
    return body, readback_inertia


def shape_geometry(body):
    parts = []
    for index in range(body.getNumShapes()):
        shape = body.getShape(index)
        half = shape.getHalfExtentsWithMargin()
        pose = body.getShapeTransform(index)
        matrix = pose.getMat()
        corners = [matrix.xformPoint(Vec3(half.x * sx, half.y * sy, half.z * sz))
                   for sx, sy, sz in itertools.product((-1, 1), repeat=3)]
        bounds = [[min(float(p[axis]) for p in corners),
                   max(float(p[axis]) for p in corners)] for axis in range(3)]
        parts.append({
            "shape_index": index,
            "shape_type": type(shape).__name__,
            "half_extents": vec_tuple(half),
            "margin": float(shape.getMargin()),
            "transform_matrix": matrix_rows(matrix),
            "aabb_local": bounds,
            "volume_m3": 8 * half.x * half.y * half.z,
        })
    return parts


def geometry_audit(config, parts):
    center = body_center(config)
    expected = [[center[0] - config.collision_half_width,
                 center[0] + config.collision_half_width],
                [center[1] - config.collision_half_length,
                 center[1] + config.collision_half_length],
                [center[2] - config.collision_half_height,
                 center[2] + config.collision_half_height]]
    union = [[min(part["aabb_local"][axis][0] for part in parts),
              max(part["aabb_local"][axis][1] for part in parts)] for axis in range(3)]
    aabb_candidates = []
    for a, b in itertools.combinations(parts, 2):
        depths = [max(0.0, min(a["aabb_local"][axis][1], b["aabb_local"][axis][1])
                      - max(a["aabb_local"][axis][0], b["aabb_local"][axis][0]))
                  for axis in range(3)]
        overlap_volume = math.prod(depths)
        if overlap_volume > 0:
            aabb_candidates.append({"shape_a": a["shape_index"], "shape_b": b["shape_index"],
                                    "conservative_aabb_intersection_volume_m3": overlap_volume})

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0])

    def norm(value):
        return math.sqrt(dot(value, value))

    def sat_margin(a, b):
        def obb(part):
            matrix = part["transform_matrix"]
            axes = []
            for row in matrix[:3]:
                length = norm(row[:3])
                axes.append(tuple(value / length for value in row[:3]))
            return tuple(matrix[3][:3]), part["half_extents"], axes

        center_a, half_a, axes_a = obb(a)
        center_b, half_b, axes_b = obb(b)
        offset = tuple(center_b[i] - center_a[i] for i in range(3))
        axes = axes_a + axes_b + [cross(axis_a, axis_b)
                                  for axis_a in axes_a for axis_b in axes_b]
        margins = []
        for axis in axes:
            length = norm(axis)
            if length < 1e-10:
                continue
            axis = tuple(value / length for value in axis)
            radius_a = sum(half_a[i] * abs(dot(axes_a[i], axis)) for i in range(3))
            radius_b = sum(half_b[i] * abs(dot(axes_b[i], axis)) for i in range(3))
            margins.append(radius_a + radius_b - abs(dot(offset, axis)))
        # Positive on all SAT axes means a real OBB intersection; tiny positives
        # can result from TransformState's float quaternion round-trip.
        return min(margins)

    sat_overlaps = []
    for a, b in itertools.combinations(parts, 2):
        margin = sat_margin(a, b)
        if margin > 0:
            sat_overlaps.append({"shape_a": a["shape_index"], "shape_b": b["shape_index"],
                                 "sat_penetration_m": margin})
    nominal_volume = (2 * config.collision_half_width
                      * 2 * config.collision_half_length
                      * 2 * config.collision_half_height)
    return {
        "expected_nominal_aabb_local": expected,
        "union_actual_corner_aabb_local": union,
        "maximum_aabb_boundary_error_m": max(
            abs(union[axis][side] - expected[axis][side])
            for axis in range(3) for side in range(2)),
        "nominal_volume_m3": nominal_volume,
        "sum_of_native_shape_volumes_m3": sum(part["volume_m3"] for part in parts),
        "volume_error_m3": sum(part["volume_m3"] for part in parts) - nominal_volume,
        "partition_intervals_are_disjoint_by_construction": True,
        "native_aabb_intersection_candidates": aabb_candidates,
        "maximum_native_aabb_candidate_volume_m3": max(
            (item["conservative_aabb_intersection_volume_m3"] for item in aabb_candidates),
            default=0.0),
        "native_obb_sat_positive_intersections": sat_overlaps,
        "maximum_native_obb_sat_penetration_m": max(
            (item["sat_penetration_m"] for item in sat_overlaps), default=0.0),
        "native_obb_intersection_beyond_2e-5m_guard": any(
            item["sat_penetration_m"] > 2e-5 for item in sat_overlaps),
    }


def capture_point(point, manifold, body):
    body_is_a = manifold.getNode0() == body
    body_point = point.getPositionWorldOnA() if body_is_a else point.getPositionWorldOnB()
    return {
        "body_is_node0": body_is_a,
        "distance_m": float(point.getDistance()),
        "normal_world_on_b": vec_tuple(point.getNormalWorldOnB()),
        "position_world_on_a_m": vec_tuple(point.getPositionWorldOnA()),
        "position_world_on_b_m": vec_tuple(point.getPositionWorldOnB()),
        "position_world_on_body_m": vec_tuple(body_point),
        "normal_impulse_ns": float(point.getAppliedImpulse()),
        "lateral_impulse_1_ns": float(point.getAppliedImpulseLateral1()),
        "lateral_impulse_2_ns": float(point.getAppliedImpulseLateral2()),
    }


def run_trial(share, wheelbase, representation):
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("impact-plane")
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
    config = replace(REFERENCE_CAR, front_weight_share=share, wheelbase=wheelbase,
                     centered_collision_support=True)
    body, original_box_inertia = make_body(config, representation)
    body.setTransform(TransformState.makePos(Vec3(0, 0, 2.5)))
    world.attachRigidBody(ground)
    world.attachRigidBody(body)
    parts = shape_geometry(body)
    rows = []
    for tick in range(240):
        world.doPhysics(FIXED_DT, 0, FIXED_DT)
        manifolds = []
        for manifold in world.getManifolds():
            if manifold.getNode0() != body and manifold.getNode1() != body:
                continue
            manifolds.append({
                "node0": manifold.getNode0().getName(),
                "node1": manifold.getNode1().getName(),
                "points": [capture_point(point, manifold, body)
                           for point in manifold.getManifoldPoints()],
            })
        transform = body.getTransform()
        rows.append({
            "tick": tick + 1,
            "time_s": (tick + 1) * FIXED_DT,
            "position_world_m": vec_tuple(transform.getPos()),
            "hpr_deg": vec_tuple(transform.getHpr()),
            "angular_velocity_world_radps": vec_tuple(body.getAngularVelocity()),
            "linear_velocity_world_mps": vec_tuple(body.getLinearVelocity()),
            "native_manifolds": manifolds,
        })
    positive_contacts = [point for row in rows for manifold in row["native_manifolds"]
                         for point in manifold["points"] if point["normal_impulse_ns"] > 0]
    if not positive_contacts:
        raise RuntimeError(f"No positive plane impulse: share={share}, {representation}")
    first = next(row for row in rows if any(
        point["normal_impulse_ns"] > 0
        for manifold in row["native_manifolds"] for point in manifold["points"]))
    first_positive = [point for manifold in first["native_manifolds"]
                      for point in manifold["points"] if point["normal_impulse_ns"] > 0]
    return {
        "front_weight_share": share,
        "wheelbase_m": wheelbase,
        "body_center_local_m": list(body_center(config)),
        "cg_projection_local_m": [0.0, 0.0],
        "representation": representation,
        "config": asdict(config),
        "initial_position_world_m": [0.0, 0.0, 2.5],
        "fixed_dt_s": FIXED_DT,
        "ticks_recorded": len(rows),
        "original_whole_box_inertia_readback_kgm2": list(original_box_inertia),
        "final_body_inertia_kgm2": vec_tuple(body.getInertia()),
        "explicit_reference_inertia_kgm2": list(REFERENCE_CAR.body_inertia),
        "shapes": parts,
        "geometry_audit": geometry_audit(config, parts),
        "first_positive_impulse": {
            "tick": first["tick"],
            "time_s": first["time_s"],
            "hpr_deg": first["hpr_deg"],
            "angular_velocity_world_radps": first["angular_velocity_world_radps"],
            "positive_contact_points": first_positive,
            "normal_impulse_sum_ns": sum(p["normal_impulse_ns"] for p in first_positive),
        },
        "peak_abs_pitch_deg": max(abs(row["hpr_deg"][1]) for row in rows),
        "peak_abs_roll_deg": max(abs(row["hpr_deg"][2]) for row in rows),
        "rows": rows,
    }


def exact_shape_signature(trial):
    return [{key: part[key] for key in
             ("shape_type", "half_extents", "margin", "transform_matrix")}
            for part in trial["shapes"]]


def main():
    OUT.mkdir(exist_ok=True)
    before = source_hashes()
    cases = ((0.5, 2.2), (0.6, 2.2), (0.4, 2.2), (0.9, 6.0))
    trials = [run_trial(share, wheelbase, representation)
              for share, wheelbase in cases
              for representation in ("captured-pre-change-centered-boxes",
                                     "prototype-cg-projected-boxes")]
    after = source_hashes()
    default_current = next(t for t in trials if t["front_weight_share"] == 0.5
                           and t["representation"] == "captured-pre-change-centered-boxes")
    default_prototype = next(t for t in trials if t["front_weight_share"] == 0.5
                             and t["representation"] == "prototype-cg-projected-boxes")
    comparisons = []
    for share, wheelbase in cases:
        current = next(t for t in trials if t["front_weight_share"] == share
                       and t["wheelbase_m"] == wheelbase
                       and t["representation"] == "captured-pre-change-centered-boxes")
        prototype = next(t for t in trials if t["front_weight_share"] == share
                         and t["wheelbase_m"] == wheelbase
                         and t["representation"] == "prototype-cg-projected-boxes")
        comparisons.append({
            "front_weight_share": share,
            "wheelbase_m": wheelbase,
            "captured_pre_change_shape_count": len(current["shapes"]),
            "prototype_shape_count": len(prototype["shapes"]),
            "captured_pre_change_first_impact": current["first_positive_impulse"],
            "prototype_first_impact": prototype["first_positive_impulse"],
            "first_pitch_delta_pre_change_minus_prototype_deg": (
                current["first_positive_impulse"]["hpr_deg"][1]
                - prototype["first_positive_impulse"]["hpr_deg"][1]),
            "captured_pre_change_peak_abs_pitch_deg": current["peak_abs_pitch_deg"],
            "prototype_peak_abs_pitch_deg": prototype["peak_abs_pitch_deg"],
            "captured_pre_change_geometry_audit": current["geometry_audit"],
            "prototype_geometry_audit": prototype["geometry_audit"],
        })
    summary = {
        "purpose": "evidence-only prototype comparison; does not modify production collision or claim T2/production repair",
        "fixture": "same detached reference-car rigid body, infinite horizontal plane, gravity -9.81m/s^2, initial CG (0,0,2.5)m, 240 fixed steps",
        "partition_rule": {
            "x_bounds": "body_center.x +/- collision_half_width; insert local CG projection x=0 only when low < 0 < high",
            "y_bounds": "body_center.y +/- collision_half_length; insert local CG projection y=0 only when low < 0 < high",
            "interval_shape": "half=(high-low)/2; center=(high+low)/2; center<0 => sign=-1 else +1",
            "orientation_and_margin": "Mat4 diag(-sx,-sy,sx*sy), translation to each interval center at body_center.z, BulletBoxShape margin=0",
            "inertia": "read original whole-Box inertia before replacing shapes; preserve explicit REFERENCE_CAR.body_inertia",
            "motion": "no geometric clamping or post-step pose correction; only native Bullet contacts and rigid-body solve",
        },
        "geometry_precision_note": (
            "Intervals are mathematically disjoint. Read-back TransformState matrices show tiny float-quaternion seam deviations: "
            "maximum SAT positive penetration 4.59e-8m, conservative AABB intersection candidate volume 4.75e-7m^3, "
            "maximum overall-AABB error 1.91e-7m, and maximum summed-volume error 8.76e-7m^3. "
            "These are below the existing 2e-5m geometry tolerance; the evidence does not claim exact zero overlap after float transform round-trip."
        ),
        "prototype_script_sha256": file_sha256(Path(__file__).resolve()),
        "source_sha256_before": before,
        "source_sha256_after": after,
        "source_stable": before == after,
        "captured_pre_change_collision_source_sha256": CAPTURED_CENTERED_COLLISION_SHA256,
        "reconstruction_note": (
            "This is a rerun/reconstruction from the previously recorded centered-four-Box formula and SHA, "
            "not recovery of the overwritten first-run raw summary. The original pre-change comparison summary "
            "was replaced by a later run after the shared production source had changed to CG projection."
        ),
        "default_half_share_exact_native_match": {
            "same_shape_count": len(default_current["shapes"]) == len(default_prototype["shapes"]),
            "same_shape_type_half_margin_and_exact_matrix":
                exact_shape_signature(default_current) == exact_shape_signature(default_prototype),
            "same_final_body_inertia":
                default_current["final_body_inertia_kgm2"] == default_prototype["final_body_inertia_kgm2"],
            "current_signature": exact_shape_signature(default_current),
            "prototype_signature": exact_shape_signature(default_prototype),
        },
        "comparison_summary": comparisons,
        "trials": trials,
    }
    output = OUT / "summary.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                      encoding="utf-8")
    for comparison in comparisons:
        print(json.dumps({k: v for k, v in comparison.items()
                          if k not in ("captured_pre_change_geometry_audit", "prototype_geometry_audit")},
                         ensure_ascii=False))
    print(f"source_stable={summary['source_stable']} default_exact="
          f"{summary['default_half_share_exact_native_match']['same_shape_type_half_margin_and_exact_matrix']} ")
    print(output)


if __name__ == "__main__":
    main()
