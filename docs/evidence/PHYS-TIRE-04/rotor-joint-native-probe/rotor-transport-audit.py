"""真实无地面车辆的转子轴向输运核对；只记录现状，不修改物理状态。"""

import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.bullet import BulletWorld
from panda3d.core import Vec3

from driving_modes import REFERENCE_CAR
from vehicle import Vehicle
from vehicle_state import FIXED_DT

OUT = Path(__file__).with_name("rotor-transport-audit")


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "tests", "tools") for p in sorted((ROOT/folder).rglob("*.py"))}


def record(car, tick):
    body = car._chassis
    orientation = body.getTransform().getQuat()
    inverse = orientation.conjugate()
    angular = body.getAngularVelocity()
    local_angular = inverse.xform(angular)
    inertia = body.getInertia()
    chassis_momentum = orientation.xform(Vec3(*(inertia[a]*local_angular[a] for a in range(3))))
    axis = orientation.getRight()
    rotor_momentum = axis*(-car.config.wheel_inertia*sum(car.tires.omega))
    momentum = chassis_momentum+rotor_momentum
    kinetic = .5*sum(inertia[a]*local_angular[a]**2 for a in range(3))
    kinetic += .5*car.config.wheel_inertia*sum(omega**2 for omega in car.tires.omega)
    return {"tick": tick, "hpr": list(body.getTransform().getHpr()), "angular_velocity": list(angular),
            "wheel_omega": car.tires.omega.copy(), "wheel_axis_world": list(axis),
            "chassis_angular_momentum_nms": list(chassis_momentum),
            "rotor_angular_momentum_nms": list(rotor_momentum),
            "total_angular_momentum_nms": list(momentum), "kinetic_energy_j": kinetic}


def trial(spin):
    config = replace(REFERENCE_CAR, angular_damping=0.)
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, 0))
    car = Vehicle(world, lambda _x, _y: True, (0, 0, 10), config=config)
    try:
        # 试验初值；没有地面、外力、驾驶或制动请求。
        car.tires.initialize_rolling(spin*config.wheel_radius)
        car._chassis.setAngularVelocity(Vec3(0, 0, .2))
        rows = [record(car, 0)]
        for tick in range(120):
            car.tires.advance(car._chassis, (), (0., 0.), 0., 0., (0.,)*4, tick, FIXED_DT)
            world.doPhysics(FIXED_DT, 0, FIXED_DT)
            rows.append(record(car, tick+1))
        initial = Vec3(*rows[0]["total_angular_momentum_nms"])
        final = Vec3(*rows[-1]["total_angular_momentum_nms"])
        return {"config": asdict(config), "initial_spin_radps": spin,
                "total_momentum_change_nms": (final-initial).length(),
                "energy_change_j": rows[-1]["kinetic_energy_j"]-rows[0]["kinetic_energy_j"], "rows": rows}
    finally:
        car.close()


if __name__ == "__main__":
    before = hashes()
    trials = [trial(spin) for spin in (0., 60.)]
    after = hashes()
    OUT.mkdir(exist_ok=True)
    report = {"claim": "current production audit of four-wheel spin-axis transport; not a correction or acceptance",
              "fixture": {"gravity": [0, 0, 0], "angular_damping": 0,
                          "ground": False, "steering": 0, "drive_or_brake": 0,
                          "initial_yaw_rate_radps": .2, "ticks": 120, "dt_s": FIXED_DT},
              "source_stable": before == after, "source_sha256_before": before, "source_sha256_after": after,
              "trials": trials}
    (OUT/"summary.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps([{k: t[k] for k in ("initial_spin_radps", "total_momentum_change_nms", "energy_change_j")}
                      for t in trials]))
