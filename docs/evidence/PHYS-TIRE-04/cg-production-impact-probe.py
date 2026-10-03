"""冻结生产实现的CG扩展撞击，保存完整配置与原生接点；不覆盖原型证据。"""

import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import TransformState, Vec3

from driving_modes import DrivingMode
from vehicle_collision import install_chassis_shape
from vehicle_state import FIXED_DT


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "tests", "tools") for p in sorted((ROOT/folder).rglob("*.py"))}


def trial(mode, share, wheelbase):
    config = replace(mode.vehicle_config, front_weight_share=share, wheelbase=wheelbase)
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("ground")
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
    body = BulletRigidBodyNode("body")
    body.setMass(config.mass)
    body.setDeactivationEnabled(False)
    install_chassis_shape(body, config)
    body.setTransform(TransformState.makePos(Vec3(0, 0, 2.5)))
    world.attachRigidBody(ground)
    world.attachRigidBody(body)
    rows = []
    for tick in range(240):
        world.doPhysics(FIXED_DT, 0, FIXED_DT)
        contacts = []
        for manifold in world.getManifolds():
            for point in manifold.getManifoldPoints():
                if point.getAppliedImpulse() > 0:
                    position = (point.getPositionWorldOnA() if manifold.getNode0() == body
                                else point.getPositionWorldOnB())
                    contacts.append({"position": list(position), "impulse_ns": point.getAppliedImpulse()})
        rows.append({"tick": tick+1, "position": list(body.getTransform().getPos()),
                     "hpr": list(body.getTransform().getHpr()),
                     "angular": list(body.getAngularVelocity()), "contacts": contacts})
    return {"mode": mode.value, "config": asdict(config), "shape_count": body.getNumShapes(),
            "native_inertia": list(body.getInertia()),
            "first_impulse": next(row for row in rows if row["contacts"]),
            "peak_pitch_deg": max(abs(row["hpr"][1]) for row in rows),
            "peak_roll_deg": max(abs(row["hpr"][2]) for row in rows), "rows": rows}


if __name__ == "__main__":
    before = source_hashes()
    trials = [trial(mode, share, wheelbase) for mode in DrivingMode
              for share, wheelbase in ((.4, 2.2), (.5, 2.2), (.6, 2.2), (.9, 6))]
    after = source_hashes()
    report = {"fixture": {"ticks": 240, "fixed_dt": FIXED_DT, "gravity": [0, 0, -9.81],
                          "initial_position": [0, 0, 2.5], "tires_or_driver": False},
              "source_sha256_before": before, "source_sha256_after": after,
              "source_stable": before == after, "trials": trials}
    out = Path(__file__).with_name("cg-production-impact")
    out.mkdir(exist_ok=True)
    (out/"summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n",
                                   encoding="utf-8")
    for item in trials:
        print(json.dumps({key: item[key] for key in ("mode", "shape_count", "peak_pitch_deg", "peak_roll_deg")}
                         | {"front_share": item["config"]["front_weight_share"],
                            "first_contact": item["first_impulse"]["contacts"][0],
                            "first_angular": item["first_impulse"]["angular"]}))
