"""用显式False配置记录当前源码的固定输入Snapshot轨迹。"""
import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, Plane, Vec3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    from vehicle import Vehicle
    from vehicle_config import CAR
    from vehicle_state import FIXED_DT, VehicleCommand

    config = (replace(CAR, finite_drivetrain=False,
                      stability=replace(CAR.stability, continuous_reference=False))
              if args.candidate else CAR)

    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("drive-compat-ground")
    ground.addShape(BulletPlaneShape(Plane(Vec3(0, 0, 1), 0)))
    ground.setIntoCollideMask(BitMask32.bit(0) | BitMask32.bit(1))
    world.attachRigidBody(ground)
    vehicle = Vehicle(world, lambda _x, _y: True, (0, 0, 0.55), config=config)
    cases = {
        "acceleration": lambda _tick: VehicleCommand(throttle=1.0, direction=1),
        "steering": lambda tick: VehicleCommand(
            steering=0.65 if tick >= 12 else 0.0, throttle=0.45, direction=1
        ),
        "reverse": lambda _tick: VehicleCommand(throttle=0.8, direction=-1),
    }
    result = {
        "source": str(args.source.resolve()),
        "fixed_dt": FIXED_DT,
        "ticks": 120,
        "car_config": asdict(config),
        "wheel_rotor_transport": config.wheel_rotor_transport,
        "finite_drivetrain": False,
        "cases": {},
    }
    try:
        for name, command_at in cases.items():
            vehicle.reset((0, 0, 0.55))
            rows = [asdict(vehicle.snapshot())]
            for tick in range(120):
                previous = vehicle._chassis.getLinearVelocity()
                vehicle.apply_command(command_at(tick))
                world.doPhysics(FIXED_DT, 0, FIXED_DT)
                vehicle.after_step(previous)
                rows.append(asdict(vehicle.snapshot()))
            result["cases"][name] = rows
    finally:
        vehicle.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
