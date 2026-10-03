"""联合轮胎/转子原型在实际Bullet世界的无外力时间离散核对。"""

import importlib.util
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
from panda3d.bullet import BulletWorld
from panda3d.core import Vec3

HERE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load_module("transport", HERE / "rotor-transport-audit.py")
joint = load_module("joint", HERE / "rotor-coupled-prototype.py")

from tire_coupling import ContactFrame, cross, dot
from wheel_dynamics import Mobility

OUT = HERE / "rotor-joint-native-probe"


def trial(spin, gyro, h):
    config = replace(audit.REFERENCE_CAR, angular_damping=0.)
    joint.CONFIG = config
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, 0))
    car = audit.Vehicle(world, lambda _x, _y: True, (0, 0, 10), config=config)
    try:
        car.tires.initialize_rolling(spin * config.wheel_radius)
        car._chassis.setAngularVelocity(Vec3(0, 0, .2))
        rows = [audit.record(car, 0)]
        increments = []
        for tick in range(round(1 / h)):
            body = car._chassis
            orientation = body.getTransform().getQuat()
            inv_native = body.getInvInertiaTensorWorld()
            tensor = tuple(tuple(.5 * (inv_native.getCell(a, b) + inv_native.getCell(b, a))
                                 for b in range(3)) for a in range(3))
            tangent, axle, normal = (tuple(orientation.xform(Vec3(*v))) for v in (
                (0, 1, 0), (1, 0, 0), (0, 0, 1)))
            frames = []
            for hub_local in car.tires.hubs:
                hub = tuple(orientation.xform(Vec3(*hub_local)))
                point = tuple(hub[a] - normal[a] * config.wheel_radius for a in range(3))
                mx, my = cross(hub, tangent), cross(point, axle)
                rx, ry, rt = (tuple(dot(row, v) for row in tensor) for v in (mx, my, axle))
                mobility = Mobility(1 / config.mass + dot(mx, rx), dot(mx, ry), dot(mx, rt),
                                    1 / config.mass + dot(my, ry), dot(my, rt), dot(axle, rt))
                frames.append(ContactFrame(0., False, 0., config.road_friction, tangent, axle,
                                           point, hub, mobility, None, rx, ry, rt))
            velocity, angular = tuple(body.getLinearVelocity()), tuple(body.getAngularVelocity())
            result = joint.joint_step(velocity, angular, car.tires.omega, frames, ((0., 0.),) * 4,
                                      (0.,) * 4, (0.,) * 4, h, gyro, tensor)
            steps, end_v, end_a, spin_end, gyro_torque, force, torque, iterations = result
            # 同一联合结果提交一次真实冲量；不调用旧advance重复施力，也不设置末速度/姿态。
            body.applyCentralImpulse(Vec3(*(h * v for v in force)))
            body.applyTorqueImpulse(Vec3(*(h * (torque[a] + gyro_torque[a]) for a in range(3))))
            car.tires.omega = [s.omega for s in steps]
            world.doPhysics(h, 0, h)
            rows.append(audit.record(car, tick + 1))
            increments.append({"tick": tick, "gyro_torque_nm": gyro_torque, "end_angular_before_bullet": end_a,
                               "end_velocity_before_bullet": end_v, "spin_momentum_before_bullet": spin_end,
                               "force_residual_n": max(s.residual for s in steps), "iterations": iterations})
        initial = np.array(rows[0]["total_angular_momentum_nms"])
        final = np.array(rows[-1]["total_angular_momentum_nms"])
        return {"config": asdict(config), "spin_radps": spin, "gyro": gyro, "h_s": h,
                "total_momentum_change_nms": float(np.linalg.norm(final - initial)),
                "energy_change_j": rows[-1]["kinetic_energy_j"] - rows[0]["kinetic_energy_j"],
                "rows": rows, "increments": increments}
    finally:
        car.close()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=False)
    for source in (Path(__file__), HERE / "rotor-coupled-prototype.py", HERE / "rotor-transport-audit.py"):
        (OUT / source.name).write_bytes(source.read_bytes())
    before = audit.hashes()
    trials = []
    for spin, gyro in ((0., False), (60., False), (60., True)):
        for h in (1 / 120, 1 / 240, 1 / 480, 1 / 960):
            result = trial(spin, gyro, h)
            (OUT / f"spin-{spin:g}-gyro-{int(gyro)}-h-{round(1/h)}.json").write_text(
                json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            trials.append(result)
            print(json.dumps({k: result[k] for k in (
                "spin_radps", "gyro", "h_s", "total_momentum_change_nms", "energy_change_j")}), flush=True)
    after = audit.hashes()
    assert before == after
    (OUT / "summary.json").write_text(json.dumps({
        "claim": "native free-flight joint rotor/tire prototype with world-tensor refresh; not source acceptance",
        "source_sha256_before": before, "source_sha256_after": after, "source_stable": before == after,
        "trials": trials, "incomplete": ["general supported road geometry", "steering actuator work",
                                         "full production A/B and lifecycle"]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
