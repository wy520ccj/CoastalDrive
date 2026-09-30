"""逐物理步记录斜撞护栏；只测量，不改变驾驶参数或碰撞规则。"""

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from panda3d.core import Vec3

from coastal_map import project
from simulation import Control, Simulation
from vehicle_config import CAR


def body_contacts(sim):
    result = []
    for manifold in sim._world.getManifolds():
        a, b = manifold.getNode0(), manifold.getNode1()
        if sim._chassis not in (a, b):
            continue
        for point in manifold.getManifoldPoints():
            normal = point.getNormalWorldOnB()
            # B侧法线朝A，统一到玩家受到的冲量方向。
            direction = normal if a == sim._chassis else -normal
            result.append({
                "other": (b if a == sim._chassis else a).getName(),
                "distance": point.getDistance(), "impulse": point.getAppliedImpulse(),
                "normal_player": tuple(direction),
                "point_a": tuple(point.getPositionWorldOnA()),
                "point_b": tuple(point.getPositionWorldOnB()),
                "lateral_impulses": [point.getAppliedImpulseLateral1(),
                                     point.getAppliedImpulseLateral2()],
                "lateral_directions": [tuple(point.getLateralFrictionDir1()),
                                       tuple(point.getLateralFrictionDir2())],
            })
    return result


def record(sim, sample):
    state = sim.snapshot().player
    pose = sim._chassis.getTransform()
    vertices = []
    for x, y, z in itertools.product(
        (-CAR.collision_half_width, CAR.collision_half_width),
        (-CAR.collision_half_length, CAR.collision_half_length), (0, .84),
    ):
        p = pose.getMat().xformPoint(Vec3(x, y, z))
        ground = project(p.x, p.y)[0].z
        vertices.append([*p, ground, p.z - ground, project(p.x, p.y)[1]])
    height = project(*state.position[:2])[0].z
    contacts = body_contacts(sim)
    return {
        "sample": sample, "tick": sim.snapshot().tick,
        "position": state.position, "velocity": tuple(sim._chassis.getLinearVelocity()),
        "hpr": tuple(pose.getHpr()), "inertia": tuple(sim._chassis.getInertia()),
        "angular_velocity": tuple(sim._chassis.getAngularVelocity()),
        "road_height": height, "body_height_above_rail": state.position[2] - height - .8,
        "lateral": project(*state.position[:2])[1],
        "vertices": vertices,
        "min_vertex_height": min(v[4] for v in vertices),
        "max_vertex_height": max(v[4] for v in vertices),
        "wheel_contacts": [asdict(c) for c in state.wheel_contacts],
        "contact_tick": state.contact_tick, "body_contacts": contacts,
        "collisions": sim.player_collisions,
        "events": sim.snapshot().events,
    }


def run(speed, output):
    sim = Simulation(seed=31, track="coastal")
    try:
        sim.reset_player((95, 0, .55), heading=-15)
        for _ in range(120):
            sim.step(Control())
        sim._chassis.setLinearVelocity(sim._chassis.getTransform().getQuat().getForward()
                                       * speed / 3.6)
        rows = []
        with (output / f"{speed}kmh.jsonl").open("w", encoding="utf-8") as stream:
            for sample in range(360):
                sim.step(Control())
                row = record(sim, sample)
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False,
                                        separators=(",", ":")) + "\n")
                rows.append(row)
        def first(predicate):
            return next((r["sample"] for r in rows if predicate(r)), None)
        return {
            "speed_kmh": speed, "samples": len(rows),
            "first_body_collision": first(lambda r: any(
                c["impulse"] > 0 for c in r["body_contacts"])),
            "first_over_6m": first(lambda r: r["lateral"] >= 6),
            "first_vertex_over_rail": first(lambda r: any(
                v[5] >= 6 and v[4] > .8 for v in r["vertices"])),
            "first_all_vertices_over_rail": first(lambda r: all(
                v[5] >= 6 and v[4] > .8 for v in r["vertices"])),
            "peak_upward_velocity": max(r["velocity"][2] for r in rows),
            "peak_lateral": max(r["lateral"] for r in rows),
            "peak_abs_roll": max(abs(r["hpr"][2]) for r in rows),
            "original_6m_pass": all(r["lateral"] < 6 for r in rows),
            "original_45deg_pass": all(abs(r["hpr"][2]) < 45 for r in rows),
            "collisions": rows[-1]["collisions"],
        }
    finally:
        sim.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--speeds", nargs="+", type=int, choices=(60, 120), default=[60, 120])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    summary = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {
            name: hashlib.sha256((Path(__file__).resolve().parents[2] / "src" / name).read_bytes()).hexdigest()
            for name in ("simulation.py", "coastal_collision.py", "coastal_map.py", "vehicle.py",
                         "vehicle_config.py", "vehicle_dynamics.py", "vehicle_contacts.py")
        },
        "seed": 31, "track": "coastal", "settle_ticks": 120, "dt": 1 / 120,
        "sampling": "Simulation.step后：wheel cache来自after_step；body为真实persistent manifold",
        "vertex_columns": ["x", "y", "z", "road_height", "height_above_road", "lateral"],
        "cases": [run(speed, args.output) for speed in args.speeds],
    }
    text = json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2)
    (args.output / "summary.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
