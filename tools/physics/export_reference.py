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
from vehicle_state import FIXED_DT, VehicleCommand

# 单位和计算职责独立列出，新增配置字段时必须同步其含义。
VEHICLE_FIELDS = {
    "mass": ("kg", "Bullet车身质量；轮胎标称载荷与道路载荷"),
    "torque_curve": ("rpm,N·m", "曲轴转矩节点线性插值；game为raw非零节点×1.055"),
    "gear_ratios": ("1", "五个自动前进挡传动比"),
    "final_drive": ("1", "主减速比"),
    "drivetrain_efficiency": ("1", "传动双向功流效率；旧分支为驱动转矩乘率"),
    "idle_rpm": ("rpm", "实际曲轴怠速控制目标；不钳末转速"),
    "shift_time": ("s", "八维旧分支选择等待/驱动衰减时长；实体轴以真实速差决定同步完成"),
    "torque_response": ("s", "实际节气门一阶响应时间常数；旧分支为轮端转矩响应"),
    "engine_braking": ("N·m", "闭节气门近似曲轴损失转矩；怠速以下连续趋零，隐式同末速度耗散"),
    "finite_drivetrain": ("bool", "真实曲轴/有限离合/双向损失与开放差速器共同末状态"),
    "front_drive_share": ("1", "前轴驱动份额；0后驱、1前驱、中间值为固定几何开放中差"),
    "differential_damping": ("N·m·s/rad", "前轴/后轴/中差末状态速差的粘性耦合系数，设计值"),
    "differential_capacity": ("N·m", "对应限滑转矩上限；有限粘性容量，不是静摩擦锁死"),
    "engine_inertia": ("kg·m²", "曲轴独立轴向惯量，通用设计值"),
    "engine_axis": ("单位向量", "车身局部曲轴正转方向"),
    "input_shaft_enabled": ("bool", "实体输入轴/有限同步；false冻结八维传动A/B"),
    "input_shaft_inertia": ("kg·m²", "输入轴独立轴向惯量，游戏.005/参考.04设计值，非实测"),
    "input_shaft_axis": ("单位向量", "壳体局部输入轴正转方向"),
    "synchronizer_capacity": ("N·m", "输入轴侧有限同步摩擦锥容量，设计值"),
    "downstream_inertia_enabled": ("bool", "实体轴分支的输出/前/后驱动轴储能与反力；false为机制A/B"),
    "downstream_inertias": ("kg·m²", "输出/前/后轴实体设计惯量；非驱动轴不安装对应转子，非实测"),
    "downstream_axes": ("单位向量", "车身局部三轴正转方向；当前通用模型为纵置轴系"),
    "engine_idle_response": ("s", "实际相对曲轴速度反馈的怠速控制响应"),
    "engine_idle_torque_limit": ("N·m", "怠速控制正转矩容量"),
    "engine_redline_rpm": ("rpm", "请求转矩切断阈值；不钳积分末RPM"),
    "clutch_capacity": ("N·m", "完全结合干式离合容量"),
    "clutch_release_time": ("s", "离合由完全结合至分离的行程时间"),
    "clutch_engage_time": ("s", "离合由分离至完全结合的行程时间"),
    "clutch_launch_response": ("s", "自动起步离合实际曲轴速度反馈时域"),
    "max_speed": ("m/s", "game前进驱动转矩渐退速度；160/3.6"),
    "reverse_speed": ("m/s", "game倒车驱动转矩渐退速度；22/3.6"),
    "reverse_force": ("N", "game倒车轮端力上限，按半径换算转矩"),
    "reverse_gear_ratio": ("1", "倒挡机械传动比"),
    "game_speed_limits": ("bool", "启用游戏速度渐退/倒车力上限；不是车身速度钳制"),
    "brake_torque": ("N·m", "四轮制动总容量"),
    "front_brake_share": ("1", "前轴制动容量份额"),
    "braking": ("配置对象", "四轮液压响应与独立ABS压力反馈；详见brake_fields"),
    "stability": ("配置对象", "横摆参考与分轮制动ESC；详见stability_fields"),
    "traction": ("配置对象", "驱动请求削减及必要的单轮制动TCS；详见traction_fields"),
    "steering_degrees": ("°", "虚拟前轴中心角机械限位"),
    "steering_rate": ("°/s", "齿条角速度限位"),
    "steering_response": ("s⁻¹", "齿条输入临界阻尼响应系数"),
    "steering_return": ("s⁻¹", "齿条回正临界阻尼响应系数"),
    "wheel_radius": ("m", "原生射线轮半径、独立轮速/滑移/力臂"),
    "wheel_inertia": ("kg·m²", "独立单轮轴向转动惯量"),
    "tire_compliance": ("bool", "启用隐式接触胎体弹性与阻尼"),
    "wheel_rotor_transport": ("bool", "机械轮轴/有效滚动力臂与同末状态轴承反力；false冻结旧机制"),
    "tire_contact_stiffness": ("N/m", "接触胎体纵横弹性刚度"),
    "tire_contact_damping": ("N·s/m", "接触胎体纵横耗散阻尼"),
    "tire_peak_load_exponent": ("1", "峰值能力轮荷指数pD；D∝Fn^pD，标称轮荷能力保持μFn0"),
    "longitudinal_load_exponent": ("1", "纵向滑移刚度轮荷指数pX；Cx∝Fn^pX，标称刚度保持Cx0"),
    "lateral_load_exponent": ("1", "侧偏刚度轮荷指数pY；Cy∝Fn^pY，标称刚度保持Cy0"),
    "longitudinal_stiffness": ("N/κ", "标称单轮载荷下纵向滑移刚度"),
    "lateral_stiffness": ("N/rad", "标称载荷下前轮侧偏刚度"),
    "rear_lateral_stiffness": ("N/rad", "标称载荷下后轮侧偏刚度"),
    "tire_shape": ("1", "简化联合Magic Formula形状"),
    "tire_curvature": ("1", "简化联合Magic Formula曲率"),
    "slip_speed": ("m/s", "低速滑移分母尺度"),
    "static_contact_speed": ("m/s", "低速静摩擦约束尝试尺度"),
    "tire_substeps": ("次/tick", "轮胎车体耦合子步数"),
    "suspension_si_enabled": ("bool", "按SI硬件换算原生参数；false沿用旧归一化硬件"),
    "suspension_coupled_enabled": ("bool", "SI法向弹簧/轴向阻尼/防倾共同末状态；false原生SI对照"),
    "suspension_antiroll_rates": ("N/m", "前/后防倾杆行程差刚度；设计值，非实车标定"),
    "suspension_stop_rates": ("N/m", "四轮行程边界外渐进止挡刚度；设计值"),
    "suspension_spring_rates": ("N/m", "四轮真实弹簧设计值；质量变化时不自动改变硬件"),
    "suspension_compression_damping": ("N·s/m", "四轮轴向压缩阻尼；关闭共同求解时为原生法向/射线速率系数"),
    "suspension_extension_damping": ("N·s/m", "四轮轴向伸张阻尼；非实车标定"),
    "suspension_stiffness": ("s⁻²", "si_enabled=false的旧归一化刚度；平路k=mass×值"),
    "suspension_compression": ("s⁻¹", "si_enabled=false的旧归一化压缩阻尼"),
    "suspension_relaxation": ("s⁻¹", "si_enabled=false的旧归一化伸张阻尼"),
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
    "centered_collision_support": ("bool", "沿CG投影切分零margin原生Box，完整覆盖名义外廓；默认四块；false为历史Box"),
    "body_center_height": ("m", "设计地面基准下碰撞盒中心高度"),
    "wheel_connection_height": ("m", "设计地面基准下射线悬架连接点高度"),
    "center_of_mass_height": ("m", "真实几何相对CG偏移与轴荷诊断高度"),
    "front_weight_share": ("1", "通过真实轴连接点相对CG纵向距离实现静态前载份额"),
    "body_inertia": ("kg·m²", "null沿用原Bullet Box生成的惯量；reference显式设计惯量"),
    "angular_damping": ("1", "Bullet刚体角阻尼"),
    "suspension_travel": ("m", "射线悬架最大行程，传API时×100cm"),
    "suspension_force_limit": ("N", "仅原生对照分支的每轮数值力限；SI势能反力不作硬裁剪"),
}
BRAKE_FIELDS = {
    "response_time": ("s", "实际压力一阶响应时间常数；0为理想执行器"),
    "abs_enabled": ("bool", "启用各轮滑移反馈压力调节"),
    "target_slip": ("1", "制动滑移目标"),
    "slip_hysteresis": ("1", "目标两侧压力增减的滑移死区"),
    "minimum_speed": ("m/s", "ABS轮心纵向真值速度介入下限"),
    "release_rate": ("比例/s", "压力请求最大减压速率"),
    "apply_rate": ("比例/s", "压力请求最大增压速率"),
    "slip_rate_gain": ("s⁻¹", "滑移误差到压力请求变化率的比例增益"),
}
TRACTION_FIELDS = {
    "tcs_enabled": ("bool", "启用驱动轮滑转反馈控制"),
    "target_slip": ("1", "驱动滑转目标"),
    "slip_hysteresis": ("1", "滑转达到目标并加该余量后触发介入"),
    "slip_speed": ("m/s", "低速滑转分母尺度"),
    "prediction_time": ("s", "用于抑制驱动滑转增长的预测时域"),
    "release_rate": ("比例/s", "可用驱动比例最大削减速率"),
    "apply_rate": ("比例/s", "可用驱动比例最大恢复速率"),
    "slip_rate_gain": ("s⁻¹", "滑转误差到驱动比例变化率的增益"),
    "brake_gain": ("比例", "单轮TCS制动请求增益"),
    "maximum_brake": ("比例", "单轮TCS制动请求上限"),
}
STABILITY_FIELDS = {
    "esc_enabled": ("bool", "启用横摆稳定控制"),
    "minimum_speed": ("m/s", "稳定控制最低前进速度"),
    "reference_response": ("s", "参考横摆一阶响应时间"),
    "yaw_gain": ("s⁻¹", "横摆率误差到期望横摆加速度增益"),
    "sideslip_gain": ("s⁻²", "侧偏角超限到期望横摆加速度增益"),
    "yaw_threshold": ("rad/s", "横摆率误差介入阈值"),
    "sideslip_threshold": ("rad", "侧偏角介入阈值"),
    "moment_threshold": ("N·m", "制动力矩请求介入阈值"),
    "engine_cut_gain": ("1", "归一化横摆及侧偏误差到发动机削矩比例增益"),
    "continuous_reference": ("bool", "低于ESC介入速度仍跟踪有支撑的参考；关闭用于冻结旧控制A/B"),
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
            previous = car._chassis.getLinearVelocity()
            car.apply_command(VehicleCommand())
            world.doPhysics(FIXED_DT, 0, FIXED_DT)
            car.after_step(previous)
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
            "suspension_state": asdict(car.suspension.state) if car.coupled_suspension else None,
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
                    "vehicle_brakes.py", "vehicle_traction.py", "vehicle_stability.py", "tire_properties.py", "tire_compliance.py", "tire_coupling.py", "vehicle_collision.py", "rotor_dynamics.py", "wheel_geometry.py", "transmission_ports.py", "tire_drivetrain.py", "differential.py", "shaft_transmission.py", "driveline_inertia.py", "suspension.py", "vehicle_suspension.py")
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
        "schema_version": "reference-v17",
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
                        default=ROOT / "logs/physics/reference-v17/parameters.json")
    export(parser.parse_args().output)
