"""固定120Hz世界推进；SI机械子步与唯一Bullet世界逐步对齐。"""

from panda3d.core import BitMask32, Vec3

from suspension_contacts import static_support_shapes
from vehicle_state import FIXED_DT, VehicleCommand
from vehicle_steering import wheel_angles


def physical_substeps(config):
    """正式SI/有限传动使用已有子步数；冻结原生机制保持单次世界推进。"""
    return config.tire_substeps if config.suspension_si_enabled and config.suspension_coupled_enabled and config.finite_drivetrain else 1


def advance_world(world, cars, *, substeps, observe=None, static_cache=None, packet_cache=None):
    """请求准备一次，子步依次施力/推进；控制、传感采样与快照只结算一个120Hz拍。"""
    velocities = [Vec3(car._chassis.getLinearVelocity()) for car, _action in cars]
    prepared = []
    if substeps > 1:
        for car, action in cars:
            force, torque = Vec3(car._chassis.getTotalForce()), Vec3(car._chassis.getTotalTorque())
            initial = tuple(state.steering for state in car.tires.states[:2])
            request = car.prepare_command(action) if isinstance(action, VehicleCommand) else car.prepare_control(action)
            prepared.append((request, initial, wheel_angles(car.steering.angle, car.config), force, torque))
    dt = FIXED_DT / substeps
    for index in range(substeps):
        # 所有车辆共用本物理子步的真实静态几何；下一Bullet推进前重新读取。
        static_shapes = (static_support_shapes(world, None, BitMask32.bit(0), cache=static_cache, packet_cache=packet_cache)
                         if any(car.coupled_suspension and car.config.finite_drivetrain for car, _action in cars) else None)
        before = {car._chassis: (Vec3(car._chassis.getLinearVelocity()),
                                Vec3(car._chassis.getAngularVelocity()),
                                Vec3(car._chassis.getTransform().getPos())) for car, _action in cars}
        numerical = []
        for i, (car, action) in enumerate(cars):
            if substeps == 1:
                if isinstance(action, VehicleCommand):
                    car.apply_command(action, static_shapes=static_shapes)
                else:
                    car.apply_control(action, static_shapes=static_shapes)
            else:
                request, initial, target, force, torque = prepared[i]
                if index:
                    # Bullet每次推进后清空持续力；保留调用方本拍施加的真实外力/力矩。
                    car._chassis.applyCentralForce(force)
                    car._chassis.applyTorque(torque)
                angles = tuple(a + (b - a) * (index + 1) / substeps for a, b in zip(initial, target))
                stages = car.physics_stages(request, dt, tire_substeps=1, angles=angles,
                                            accumulate=index > 0, static_shapes=static_shapes)
                inputs = next(stages, None)
                if inputs is not None:
                    numerical.append((stages, inputs))
        # 各车读完本子步后求末状态，再按原车辆/轮端顺序提交；Bullet仍只推进一次。
        solved = [(stages, inputs.solve()) for stages, inputs in numerical]
        for stages, result in solved:
            try:
                stages.send(result)
            except StopIteration:
                pass
            else:
                raise RuntimeError("世界子步只允许一次轮端机械求解")
        world.doPhysics(dt, 0, dt)
        if observe is not None:
            observe(before, index == substeps - 1)
    for (car, _action), velocity in zip(cars, velocities):
        car.after_step(velocity)
