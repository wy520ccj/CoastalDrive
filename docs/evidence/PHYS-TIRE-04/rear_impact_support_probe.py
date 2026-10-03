"""同一追尾初始化下记录原生支撑表示、真实manifold与全过程；不改运动。"""

import gzip
import json
import sys
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.bullet import BulletBoxShape, BulletConvexHullShape, BulletConvexPointCloudShape, BulletMultiSphereShape
from panda3d.core import Vec3

from simulation import Control, Simulation
from vehicle_config import CAR


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "running", "trials": [], "protocol": "same existing rear-end test, geometry replacement before first step only; original inertia, cfg, seed and commands; full 480 impact ticks even after threshold"}
    for variant in ("box", "centers26", "faces14", "bottom9", "pointcloud26", "multisphere26"):
        sim = Simulation(track="highway", config=replace(CAR, centered_collision_support=False))
        peak, first_failed, first_contact = 0.0, None, None
        try:
            if variant != "box":
                for car in (sim.player, *sim.npcs):
                    body = car._chassis
                    original = body.getShape(0)
                    inner, margin = original.getHalfExtentsWithoutMargin(), original.getMargin()
                    transform, inertia = body.getShapeTransform(0), body.getInertia()
                    points = [point for point in product((-1, 0, 1), repeat=3) if point != (0, 0, 0)]
                    if variant == "faces14":
                        points = [point for point in points if sum(v != 0 for v in point) != 2]
                    elif variant == "bottom9":
                        points = [(0, 0, -1), *product((-1, 1), repeat=3)]
                    points.sort(key=lambda point: sum(v != 0 for v in point))
                    vectors = [Vec3(*(inner[a]*point[a] for a in range(3))) for point in points]
                    if variant == "pointcloud26":
                        shape = BulletConvexPointCloudShape(vectors, Vec3(1))
                    elif variant == "multisphere26":
                        shape = BulletMultiSphereShape(vectors, [margin]*len(vectors))
                    else:
                        shape = BulletConvexHullShape()
                        for point in vectors:
                            shape.addPoint(point)
                    shape.setMargin(margin)
                    body.removeShape(original)
                    body.addShape(shape, transform)
                    body.setInertia(inertia)
            target = sim._traffic_bodies[0]
            pos = target.getTransform().getPos()
            sim.reset_player((pos.x, pos.y-12, .55))
            for _ in range(60):
                sim.step(Control())
            sim._chassis.setLinearVelocity(Vec3(0, 30, 0))
            sim.player.tires.initialize_rolling(30)
            with gzip.open(output / f"{variant}.jsonl.gz", "wt", encoding="utf-8") as stream:
                for tick in range(1, 481):
                    sim.step(Control(throttle=1))
                    player = sim.snapshot().player
                    peak = max(peak, abs(player.roll))
                    if abs(player.roll) >= 10 and first_failed is None:
                        first_failed = tick
                    points = []
                    for manifold in sim._world.getManifolds():
                        a, b = manifold.getNode0(), manifold.getNode1()
                        if sim._chassis not in (a, b):
                            continue
                        for point in manifold.getManifoldPoints():
                            if point.getAppliedImpulse() > 0:
                                points.append({"nodes": [a.getName(), b.getName()],
                                    "normal_on_b": tuple(point.getNormalWorldOnB()),
                                    "position_a": tuple(point.getPositionWorldOnA()), "position_b": tuple(point.getPositionWorldOnB()),
                                    "impulse_ns": point.getAppliedImpulse(), "distance_m": point.getDistance()})
                    touching = sim._world.contactTestPair(sim._chassis, target).getNumContacts() > 0
                    if touching and first_contact is None:
                        first_contact = tick
                    stream.write(json.dumps({"impact_tick": tick, "state": asdict(player),
                        "target": asdict(sim.snapshot().traffic[0]), "manifold_positive_impulses": points}, allow_nan=False)+"\n")
            result = {"variant": variant, "peak_abs_roll_deg": peak,
                      "first_roll_gate_failure_impact_tick": first_failed, "first_contact_impact_tick": first_contact,
                      "final_speed_mps": player.speed, "config": asdict(sim.config)}
            report["trials"].append(result)
            (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            print(json.dumps({k: v for k, v in result.items() if k != "config"}), flush=True)
        finally:
            sim.close()
    report["status"] = "completed"
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    run(HERE / "rear-impact-support")
