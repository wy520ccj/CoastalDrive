"""只读原生车身垂直撞击；对比几何中心和质心不同的平接触。"""

import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import TransformState, Vec3

from driving_modes import REFERENCE_CAR
from vehicle_collision import install_chassis_shape
from vehicle_state import FIXED_DT


def trial(share, centered):
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("ground")
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
    body = BulletRigidBodyNode("body")
    body.setMass(REFERENCE_CAR.mass)
    body.setDeactivationEnabled(False)
    config = replace(REFERENCE_CAR, front_weight_share=share,
                     centered_collision_support=centered)
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
                    contacts.append({"position": list(position),
                                     "impulse_ns": point.getAppliedImpulse()})
        rows.append({"tick": tick + 1, "position": list(body.getTransform().getPos()),
                     "hpr": list(body.getTransform().getHpr()),
                     "angular": list(body.getAngularVelocity()), "contacts": contacts})
    first = next(row for row in rows if row["contacts"])
    return {"front_weight_share": share, "centered_collision_support": centered,
            "first_impulse": first,
            "peak_pitch_deg": max(abs(row["hpr"][1]) for row in rows),
            "peak_roll_deg": max(abs(row["hpr"][2]) for row in rows), "rows": rows}


out = Path(__file__).with_name("cg-plane-impact")
out.mkdir(exist_ok=True)
trials = [trial(share, centered) for share in (.5, .6) for centered in (False, True)]
(out / "summary.json").write_text(json.dumps(trials, indent=2) + "\n", encoding="utf-8")
for item in trials:
    print(json.dumps({key: value for key, value in item.items() if key != "rows"}))
