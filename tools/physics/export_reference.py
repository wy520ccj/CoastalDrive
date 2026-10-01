"""冻结当前两种驾驶模式的设计参数和真实Bullet静置读数。"""
import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld, getBulletVersion
from panda3d.core import PandaSystem, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from driving_modes import DrivingMode
from vehicle import Vehicle
from vehicle_config import body_center, wheel_hubs
from vehicle_state import FIXED_DT, VehicleCommand

# 单位和计算职责独立列出，新增配置字段时必须同步其含义。
VEHICLE_FIELDS = {
    "mass": ("kg", "Bullet车身质量；轮胎标称载荷与道路载荷"),
    "torque_curve": ("rpm,N·m", "曲轴转矩节点线性插值；game为raw非零节点×1.055"),
    "gear_ratios": ("1", "五个自动前进挡传动比"),
    "final_drive": ("1", "主减速比"),
    "drivetrain_efficiency": ("1", "驱动转矩效率"),
    "idle_rpm": ("rpm", "发动机转速下限"),
    "shift_time": ("s", "换挡驱动转矩衰减时长"),
    "torque_response": ("s", "轮端转矩一阶响应时间常数"),
    "engine_braking": ("N·m", "闭油门曲轴拖曳转矩估计"),
    "max_speed": ("m/s", "game前进驱动转矩渐退速度；160/3.6"),
    "reverse_speed": ("m/s", "game倒车驱动转矩渐退速度；22/3.6"),
    "reverse_force": ("N", "game倒车轮端力上限，按半径换算转矩"),
    "reverse_gear_ratio": ("1", "倒挡机械传动比"),
    "game_speed_limits": ("bool", "启用游戏速度渐退/倒车力上限；不是车身速度钳制"),
    "brake_torque": ("N·m", "四轮制动总容量"),
    "front_brake_share": ("1", "前轴制动容量份额"),
    "steering_degrees": ("°", "虚拟前轴中心角机械限位"),
    "steering_rate": ("°/s", "齿条角速度限位"),
    "steering_response": ("s⁻¹", "齿条输入临界阻尼响应系数"),
    "steering_return": ("s⁻¹", "齿条回正临界阻尼响应系数"),
    "wheel_radius": ("m", "原生射线轮半径、独立轮速/滑移/力臂"),
    "wheel_inertia": ("kg·m²", "独立单轮轴向转动惯量"),
    "longitudinal_stiffness": ("N/κ", "标称单轮载荷下纵向滑移刚度"),
    "lateral_stiffness": ("N/rad", "标称载荷下前轮侧偏刚度"),
    "rear_lateral_stiffness": ("N/rad", "标称载荷下后轮侧偏刚度"),
    "tire_shape": ("1", "简化联合Magic Formula形状"),
    "tire_curvature": ("1", "简化联合Magic Formula曲率"),
    "slip_speed": ("m/s", "低速滑移分母尺度"),
    "static_contact_speed": ("m/s", "低速静摩擦约束尝试尺度"),
    "tire_substeps": ("次/tick", "轮胎车体耦合子步数"),
    "suspension_stiffness": ("s⁻²", "Bullet质量归一化悬架刚度；平路k=mass×值"),
    "suspension_compression": ("s⁻¹", "质量归一化压缩阻尼；平路c=mass×值"),
    "suspension_relaxation": ("s⁻¹", "质量归一化伸张阻尼；平路c=mass×值"),
    "air_density": ("kg/m³", "环境空气密度"),
    "drag_coefficient": ("1", "气动阻力Cd"),
    "frontal_area": ("m²", "迎风面积；保持旧CdA乘积的推导设计值"),
    "rolling_coefficient": ("1", "铺装滚阻160/(1200×9.81)，乘实际Fn及低速线性项"),
    "grass_rolling_coefficient": ("1", "草地滚阻900/(1200×9.81)"),
    "road_friction": ("1", "铺装摩擦预算μFn"),
    "grass_friction": ("1", "草地摩擦预算μFn"),
    "wheelbase": ("m", "轴距、Ackermann和轴荷诊断"),
    "track_width": ("m", "轮距、实际轮连接点横坐标"),
    "collision_half_width": ("m", "真实车身碰撞盒半宽"),
    "collision_half_length": ("m", "真实车身碰撞盒半长"),
    "collision_half_height": ("m", "真实车身碰撞盒半高"),
    "body_center_height": ("m", "设计地面基准下碰撞盒中心高度"),
    "wheel_connection_height": ("m", "设计地面基准下射线悬架连接点高度"),
    "center_of_mass_height": ("m", "真实几何相对CG偏移与轴荷诊断高度"),
    "front_weight_share": ("1", "通过真实轴连接点相对CG纵向距离实现静态前载份额"),
    "body_inertia": ("kg·m²", "null由Bullet碰撞盒生成；reference显式设计惯量"),
    "angular_damping": ("1", "Bullet刚体角阻尼"),
    "suspension_travel": ("m", "射线悬架最大行程，传API时×100cm"),
    "suspension_force_limit": ("N", "每轮实际施加悬架力上限"),
}
INPUT_FIELDS = {
    "progressive_pedals": ("bool", "启用键盘踏板渐变"),
    "speed_sensitive_steering": ("bool", "启用速度相关键盘转向包络"),
    "automatic_reverse": ("bool", "低速S持续制动后辅助切倒挡；false用Q/E显式R/D"),
    "throttle_rise": ("比例/s", "游戏油门上升速率；仿真渐变关闭时不使用"),
    "throttle_release": ("比例/s", "游戏油门释放速率；仿真渐变关闭时不使用"),
    "brake_rise": ("比例/s", "游戏制动上升速率；仿真渐变关闭时不使用"),
    "brake_release": ("比例/s", "游戏制动释放速率；仿真渐变关闭时不使用"),
    "assisted_lateral_acceleration": ("m/s²", "游戏速度转向包络目标；仿真包络关闭时不使用"),
    "reverse_delay": ("s", "游戏辅助倒挡等待；仿真自动倒挡关闭时不使用"),
}


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
            previous = car._chassis.getLinearVelocity()
            car.apply_command(VehicleCommand())
            world.doPhysics(FIXED_DT, 0, FIXED_DT)
            car.after_step(previous)
        body = car._chassis
        return {
            "mass": body.getMass(), "inertia": tuple(body.getInertia()),
            "angular_damping": body.getAngularDamping(),
            "shape_half_extents": tuple(body.getShape(0).getHalfExtentsWithMargin()),
            "shape_center": tuple(body.getShapeTransform(0).getPos()),
            "position": tuple(body.getTransform().getPos()),
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
        assert set(inputs) == set(INPUT_FIELDS), "InputConfig字段表必须完整"
        modes[mode.value] = {
            "label": mode.label, "vehicle_config": config, "input_config": inputs,
            "geometry_hubs": wheel_hubs(mode.vehicle_config),
            "geometry_body_center": body_center(mode.vehicle_config),
            "native_bullet": measure(mode),
        }
    source_names = ("vehicle_config.py", "driver_assist.py", "driving_modes.py", "vehicle.py",
                    "vehicle_tires.py", "powertrain.py", "vehicle_steering.py", "vehicle_dynamics.py",
                    "wheel_dynamics.py", "tire_forces.py", "vehicle_contacts.py", "vehicle_state.py")
    hashes = {f"src/{name}": hashlib.sha256((ROOT / "src" / name).read_bytes()).hexdigest()
              for name in source_names}
    hashes["tools/physics/export_reference.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = {
        "claim": "程序设计参数与本机实现读回，不是实车测量或标定",
        "git_head_context_only": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": hashes,
        "panda_version": PandaSystem.getVersionString(), "bullet_version": getBulletVersion(),
        "measurement": {"ticks": 240, "dt": FIXED_DT, "max_substeps": 0,
                        "ground": "水平无限平面", "gravity": [0, 0, -9.81], "input": "VehicleCommand()"},
        "vehicle_fields": VEHICLE_FIELDS, "input_fields": INPUT_FIELDS, "modes": modes,
        "remaining_constants": {"suspension_rest_length_m": .4, "roll_influence": .1,
                                "ccd_motion_threshold_m": .5, "ccd_swept_sphere_radius_m": .35},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"已导出{len(VEHICLE_FIELDS)}车辆字段、{len(INPUT_FIELDS)}输入字段、两模式真实240tick读数：{output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs/evidence/PHYS-MODES-01/reference-parameters.json")
    export(parser.parse_args().output)
