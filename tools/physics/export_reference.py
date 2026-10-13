"""冻结当前两种驾驶模式的设计参数和真实Bullet静置读数。"""
import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from itertools import product
from pathlib import Path

from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld, getBulletVersion
from panda3d.core import PandaSystem, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from driving_modes import DrivingMode
from vehicle import Vehicle
from vehicle_config import body_center, wheel_hubs

# 单位和计算职责独立列出，新增配置字段时必须同步其含义。
from vehicle_parameter_info import (
    BRAKE_FIELDS,
    INPUT_FIELDS,
    STABILITY_FIELDS,
    TRACTION_FIELDS,
    VEHICLE_FIELDS,
)
from vehicle_state import FIXED_DT, VehicleCommand
from world_step import advance_world, physical_substeps


def shape_volume_center(body):
    """读取原生Box体积加权中心，适用于偏置CG造成的不等体积分区。"""
    volumes = [8*body.getShape(i).getHalfExtentsWithMargin().x
               *body.getShape(i).getHalfExtentsWithMargin().y
               *body.getShape(i).getHalfExtentsWithMargin().z for i in range(body.getNumShapes())]
    return Vec3(*(sum(body.getShapeTransform(i).getPos()[axis]*volume
                      for i, volume in enumerate(volumes))/sum(volumes) for axis in range(3)))


def shape_axis_limits(body):
    """从原生Box角点读取整体边界，相对体积中心；不使用迭代射线的近似交点。"""
    center = shape_volume_center(body)
    points = []
    for index in range(body.getNumShapes()):
        half = body.getShape(index).getHalfExtentsWithMargin()
        pose = body.getShapeTransform(index).getMat()
        points.extend(pose.xformPoint(Vec3(*(half[axis]*sign[axis] for axis in range(3))))
                      for sign in product((-1, 1), repeat=3))
    return tuple((min(p[axis] for p in points)-center[axis], max(p[axis] for p in points)-center[axis])
                 for axis in range(3))


def measure(mode):
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("reference-plane")
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda x, y: True, (0, 0, .55),
                  config=mode.vehicle_config, input_config=mode.input_config)
    try:
        for _ in range(240):
            advance_world(world, [(car, VehicleCommand())], substeps=physical_substeps(car.config))
        body = car._chassis
        limits = shape_axis_limits(body)
        shape_center = shape_volume_center(body)
        return {
            "mass": body.getMass(), "inertia": tuple(body.getInertia()),
            "angular_damping": body.getAngularDamping(),
            "shape_half_extents": tuple((high-low)/2 for low, high in limits),
            "shape_axis_limits": limits,
            "shape_type": body.getShape(0).getType().getName(),
            "shape_count": body.getNumShapes(),
            "shape_margin": body.getShape(0).getMargin(),
            "shape_center": tuple(shape_center),
            "shapes": [{"type": body.getShape(i).getType().getName(),
                        "half_extents": tuple(body.getShape(i).getHalfExtentsWithMargin()),
                        "margin": body.getShape(i).getMargin(),
                        "transform": [[body.getShapeTransform(i).getMat().getCell(a, b)
                                       for b in range(4)] for a in range(4)]}
                       for i in range(body.getNumShapes())],
            "position": tuple(body.getTransform().getPos()),
            "suspension_authority": "coupled-SI" if car.coupled_suspension else "native-Bullet",
            "suspension_contact_model": "finite-width-crowned-cylinder" if car.coupled_suspension else "native-point-ray",
            "suspension_velocity_model": "shared-tire-drivetrain-end" if car.coupled_suspension and car.config.finite_drivetrain else "separate-normal-stage",
            "world_substeps": physical_substeps(car.config),
            "world_substep_dt_s": FIXED_DT / physical_substeps(car.config),
            "suspension_state": asdict(car.suspension.state) if car.coupled_suspension else None,
            "aerodynamic_model": "relative-air-3d-scalar-CdA",
            "rolling_model": "shared-wheel-external-torque" if car.config.finite_drivetrain and car.config.wheel_rolling_resistance else "legacy-central-force",
            "wheel_dynamics": [asdict(w) for w in car.snapshot().wheel_dynamics],
            "dynamics": asdict(car.snapshot().dynamics),
            "wheels": [{
                "hub": tuple(w.getChassisConnectionPointCs()), "radius": w.getWheelRadius(),
                "rest_length": w.getSuspensionRestLength(),
                "travel_cm": w.getMaxSuspensionTravelCm(),
                "force_limit": w.getMaxSuspensionForce(),
                "stiffness": w.getSuspensionStiffness(),
                "compression_damping": w.getWheelsDampingCompression(),
                "relaxation_damping": w.getWheelsDampingRelaxation(),
                "roll_influence": w.getRollInfluence(),
                "friction_slip": w.getFrictionSlip(),
                "contact": asdict(c),
            } for w, c in zip(car._vehicle.getWheels(), car.snapshot().wheel_contacts)],
        }
    finally:
        car.close()


def export(output):
    modes = {}
    for mode in DrivingMode:
        config, inputs = asdict(mode.vehicle_config), asdict(mode.input_config)
        assert set(config) == set(VEHICLE_FIELDS), "VehicleConfig字段表必须完整"
        assert set(config["braking"]) == set(BRAKE_FIELDS), "BrakeConfig字段表必须完整"
        assert set(config["traction"]) == set(TRACTION_FIELDS), "TractionConfig字段表必须完整"
        assert set(config["stability"]) == set(STABILITY_FIELDS), "StabilityConfig字段表必须完整"
        assert set(inputs) == set(INPUT_FIELDS), "InputConfig字段表必须完整"
        modes[mode.value] = {
            "label": mode.label, "vehicle_config": config, "input_config": inputs,
            "geometry_hubs": wheel_hubs(mode.vehicle_config),
            "geometry_body_center": body_center(mode.vehicle_config),
            "native_bullet": measure(mode),
        }
    source_names = ("vehicle_config.py", "driver_assist.py", "driving_modes.py", "vehicle.py",
                    "vehicle_tires.py", "vehicle_traction.py", "powertrain.py", "vehicle_steering.py", "vehicle_dynamics.py",
                    "wheel_dynamics.py", "tire_forces.py", "vehicle_contacts.py", "vehicle_state.py",
                    "vehicle_brakes.py", "vehicle_traction.py", "vehicle_stability.py", "tire_properties.py", "tire_compliance.py", "tire_coupling.py", "vehicle_collision.py", "rotor_dynamics.py", "wheel_geometry.py", "transmission_ports.py", "tire_drivetrain.py", "differential.py", "shaft_transmission.py", "driveline_inertia.py", "suspension.py", "vehicle_suspension.py", "suspension_contacts.py", "suspension_geometry.py", "suspension_kinematics.py", "wheel_envelope.py", "triangle_support.py", "rolling_resistance.py", "simulation.py", "streamed_road.py", "world_step.py")
    hashes = {f"src/{name}": hashlib.sha256((ROOT / "src" / name).read_bytes()).hexdigest()
              for name in source_names}
    hashes["tools/physics/export_reference.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = {
        "claim": "程序设计参数与本机实现读回，不是实车测量或标定",
        "git_head_context_only": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": hashes,
        "panda_version": PandaSystem.getVersionString(), "bullet_version": getBulletVersion(),
        "measurement": {"ticks": 240, "dt": FIXED_DT, "max_substeps": 0,
                        "world_substeps_per_tick": {mode.value: physical_substeps(mode.vehicle_config) for mode in DrivingMode},
                        "native_dt_s": {mode.value: FIXED_DT / physical_substeps(mode.vehicle_config) for mode in DrivingMode},
                        "ground": "水平无限平面", "gravity": [0, 0, -9.81], "input": "VehicleCommand()"},
        "schema_version": "reference-v28",
        "vehicle_fields": VEHICLE_FIELDS, "brake_fields": BRAKE_FIELDS,
        "traction_fields": TRACTION_FIELDS, "stability_fields": STABILITY_FIELDS,
        "input_fields": INPUT_FIELDS, "modes": modes,
        "remaining_constants": {"suspension_rest_length_m": .4, "roll_influence": .1,
                                "ccd_motion_threshold_m": .5, "ccd_swept_sphere_radius_m": .35},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"已导出{len(VEHICLE_FIELDS)}车辆字段、{len(INPUT_FIELDS)}输入字段、两模式真实240tick读数：{output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "logs/physics/reference-v28/parameters.json")
    export(parser.parse_args().output)
