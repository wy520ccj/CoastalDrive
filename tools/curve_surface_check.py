"""Headless Bullet support checks for the curved highway mesh."""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panda3d.bullet import (
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import BitMask32, TransformState, Vec3

from curve_mesh import anchor, markings, surfaces, trees
from highway_curve import HighwayCurve
from highway_segments import SEGMENT_LENGTH

MASK = BitMask32.bit(0)
INDICES = (-6, -5, -2, -1, 0, 1, 2, 4, 5, 6)


def _world_vertex(curve, index, vertex):
    ax, ay, az = anchor(curve, index)
    return (vertex[0] + ax, vertex[1] + ay, vertex[2] + az)


def _body(world, name, vertices, triangles, index, curve):
    mesh = BulletTriangleMesh()
    for a, b, c in triangles:
        mesh.addTriangle(*(Vec3(*vertices[i]) for i in (a, b, c)))
    shape = BulletTriangleMeshShape(mesh, dynamic=False)
    shape.setMargin(0.01)
    body = BulletRigidBodyNode(name)
    body.addShape(shape)
    body.setTransform(TransformState.makePos(Vec3(*anchor(curve, index))))
    body.setIntoCollideMask(MASK)
    world.attachRigidBody(body)
    return body


def _ray(world, x, y, z):
    hit = world.rayTestClosest(Vec3(x, y, z + 2.0), Vec3(x, y, z - 2.0), MASK)
    if not hit.hasHit():
        raise AssertionError(f"no Bullet support at ({x:.4f}, {y:.4f})")
    return hit.getHitPos().z


def run(seed, hills):
    curve = HighwayCurve(seed, hills=hills)
    world = BulletWorld()
    marking_world = BulletWorld()
    built = {}
    for index in INDICES:
        for name, (vertices, triangles) in surfaces(curve, index).items():
            built[(index, name)] = (vertices, triangles)
            _body(world, name, vertices, triangles, index, curve)
        for number, (vertices, triangles) in enumerate(markings(curve, index)):
            _body(marking_world, f"marking-{index}-{number}", vertices, triangles, index, curve)

    max_error = 0.0
    max_marking_error = 0.0
    min_tree_clearance = float("inf")
    max_join_gap = 0.0
    min_winding_z = float("inf")
    for index in INDICES:
        for name in ("road", "shoulder-left", "shoulder-right"):
            vertices, triangles = built[(index, name)]
            for a, b, c in triangles:
                va, vb, vc = (Vec3(*_world_vertex(curve, index, vertices[i])) for i in (a, b, c))
                normal = (vb - va).cross(vc - va)
                min_winding_z = min(min_winding_z, normal.getZ())
                if normal.getZ() <= 0:
                    raise AssertionError(f"{name} triangle winding is downward")
        for s in tuple(i + 2.5 for i in range(0, SEGMENT_LENGTH, 5)) + (
            0.001,
            SEGMENT_LENGTH - 0.001,
        ):
            for lateral in (-7.5, -7.0, -5.34, -3.66, -0.84, 0.84, 3.66, 5.34, 7.0, 7.5):
                expected = curve.sample(index * SEGMENT_LENGTH + s, lateral).z
                p = curve.sample(index * SEGMENT_LENGTH + s, lateral)
                actual = _ray(world, p.x, p.y, p.z)
                max_error = max(max_error, abs(actual - expected))
        for number, (vertices, _triangles) in enumerate(markings(curve, index)):
            # Each marking strip is four metres long; its centre is unambiguous above road mesh.
            lateral = (-2.25, 2.25)[number // (SEGMENT_LENGTH // 8)]
            s = (number % (SEGMENT_LENGTH // 8)) * 8 + 2.0
            p = curve.sample(index * SEGMENT_LENGTH + s, lateral)
            error = abs(_ray(marking_world, p.x, p.y, p.z + 0.035) - (p.z + 0.035))
            max_marking_error = max(max_marking_error, error)
        for local, _scale, _heading in trees(curve, seed, index):
            p = _world_vertex(curve, index, local)
            _distance, projected_lateral = curve.project(p)
            min_tree_clearance = min(min_tree_clearance, abs(projected_lateral))
    join_comparisons = 0
    index_set = set(INDICES)
    for index in INDICES:
        if index + 1 not in index_set:
            continue
        for name, (vertices, _triangles) in surfaces(curve, index).items():
            next_vertices, _ = surfaces(curve, index + 1)[name]
            width = 4 if name.startswith("rail-") else 2
            end = vertices[-width:]
            start = next_vertices[:width]
            for left, right in zip(end, start):
                join_comparisons += 1
                max_join_gap = max(max_join_gap, math.dist(_world_vertex(curve, index, left), _world_vertex(curve, index + 1, right)))
    if join_comparisons == 0:
        raise AssertionError("no adjacent segment vertices were compared")
    if min_tree_clearance < 20.0:
        raise AssertionError(f"tree clearance is {min_tree_clearance:.6f} m")
    return {
        "seed": seed,
        "hills": hills,
        "max_error_m": max_error,
        "max_marking_error_m": max_marking_error,
        "min_tree_clearance_m": min_tree_clearance,
        "max_join_gap_m": max_join_gap,
        "join_comparisons": join_comparisons,
        "min_winding_z": min_winding_z,
        "passed": max_error <= 0.015 and max_marking_error <= 0.015 and max_join_gap <= 1e-8,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("logs/h4b/curves/surface.json"))
    args = parser.parse_args()
    results = [run(seed, hills) for seed in range(10) for hills in (False, True)]
    report = {"checks": results, "max_error_m": max(item["max_error_m"] for item in results), "passed": all(item["passed"] for item in results)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
