"""转子轴向输运预研：在原生世界施加真实轴承陀螺反力，比较时间步。"""

import hashlib
import importlib.util
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
from panda3d.bullet import BulletWorld
from panda3d.core import Vec3

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("transport_audit", HERE/"rotor-transport-audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
OUT = HERE/"rotor-gyro-impulse-prototype"


def skew(vector):
    x, y, z = vector
    return np.array(((0., -z, y), (z, 0., -x), (-y, x, 0.)))


def trial(spin, gyro, h):
    config = replace(audit.REFERENCE_CAR, angular_damping=0.)
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, 0))
    car = audit.Vehicle(world, lambda _x, _y: True, (0, 0, 10), config=config)
    try:
        car.tires.initialize_rolling(spin*config.wheel_radius)
        car._chassis.setAngularVelocity(Vec3(0, 0, .2))
        rows = [audit.record(car, 0)]
        first_torque = None
        for tick in range(round(1/h)):
            body = car._chassis
            car.tires.advance(body, (), (0., 0.), 0., 0., (0.,)*4, tick, h)
            if gyro:
                axes = body.getTransform().getQuat().getRight()
                spin_momentum = np.array(tuple(axes))*(-config.wheel_inertia*sum(car.tires.omega))
                tensor = body.getInvInertiaTensorWorld()
                inverse = np.array([[.5*(tensor.getCell(a, b)+tensor.getCell(b, a))
                                     for b in range(3)] for a in range(3)])
                inertia = np.linalg.inv(inverse)
                angular = np.array(tuple(body.getAngularVelocity()))
                end_angular = np.linalg.solve(inertia-h*skew(spin_momentum), inertia@angular)
                torque = np.cross(spin_momentum, end_angular)
                if first_torque is None:
                    first_torque = torque.tolist()
                # 真实轴承反力冲量，不设置运行姿态或角速度；原生body积分继续负责旋转。
                body.applyTorqueImpulse(Vec3(*(h*torque)))
            world.doPhysics(h, 0, h)
            rows.append(audit.record(car, tick+1))
        initial = Vec3(*rows[0]["total_angular_momentum_nms"])
        final = Vec3(*rows[-1]["total_angular_momentum_nms"])
        return {"config": asdict(config), "spin_radps": spin, "gyro_enabled_in_fixture": gyro,
                "h_s": h, "first_gyro_torque_nm": first_torque,
                "total_momentum_change_nms": (final-initial).length(),
                "energy_change_j": rows[-1]["kinetic_energy_j"]-rows[0]["kinetic_energy_j"], "rows": rows}
    finally:
        car.close()


if __name__ == "__main__":
    before = audit.hashes()
    OUT.mkdir(exist_ok=True)
    trials = []
    for spin, gyro in ((0., False), (60., False), (60., True)):
        for h in (1/120, 1/240, 1/480, 1/960):
            result = trial(spin, gyro, h)
            (OUT/f"spin-{spin:g}-gyro-{int(gyro)}-step-{round(1/h)}.json").write_text(
                json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
            trials.append(result)
            print(json.dumps({k: result[k] for k in ("spin_radps", "gyro_enabled_in_fixture", "h_s",
                                                    "total_momentum_change_nms", "energy_change_j")}))
    after = audit.hashes()
    report = {"claim": "isolated native impulse prototype for free spin-axis transport; not production acceptance",
              "source_stable": before == after, "source_sha256_before": before, "source_sha256_after": after,
              "mechanism": "S=-sum(Iw*omega)*world_right_axis; (I-h[S]x)Omega_end=I*Omega_free; torque=S cross Omega_end",
              "incomplete": ["same-end tire/brake/clutch coupling", "steering axis actuator work",
                             "support/contact mechanical axle definition", "complete source and vehicle A/B gates"],
              "trials": trials}
    (OUT/"summary.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
