"""固定120Hz世界推进；SI机械子步与唯一Bullet世界逐步对齐。"""

from panda3d.core import BitMask32, Vec3

from suspension_contacts import static_support_shapes
from vehicle_state import FIXED_DT, VehicleCommand
from vehicle_steering import wheel_angles


def physical_substeps(config):
    """正式SI/有限传动使用已有子步数；冻结原生机制保持单次世界推进。"""
    return config.tire_substeps if config.suspension_si_enabled and config.suspension_coupled_enabled and config.finite_drivetrain else 1


def advance_world(world, cars, *, substeps, observe=None, static_cache=None, packet_cache=None, workers=None, material=None, query_lock=None,
                  recover=None):
    """请求准备一次，子步依次施力/推进；控制、传感采样与快照只结算一个120Hz拍。"""
    velocities = [Vec3(car._chassis.getLinearVelocity()) for car, _action in cars]
    prepared = []
    if substeps > 1:
        for car, action in cars:
            chassis = car._chassis
            force, torque = Vec3(chassis.getTotalForce()), Vec3(chassis.getTotalTorque())
            has_external = force.lengthSquared() != 0.0 or torque.lengthSquared() != 0.0
            needs_angles = car.coupled_suspension or car.config.unsprung_enabled or not car._native_action
            initial = tuple(state.steering for state in car.tires.states[:2]) if needs_angles else None
            request = car.prepare_command(action) if isinstance(action, VehicleCommand) else car.prepare_control(action)
            target = wheel_angles(car.steering.angle, car.config) if needs_angles else None
            prepared.append((request, initial, target, force, torque, has_external))
    dt = FIXED_DT / substeps
    # 本120Hz拍只积分动态刚体；道路流送/重定位在本函数之外完成。
    # 静态支撑几何在两个机械子步间保持不变，车辆姿态和接点仍逐子步重读。
    static_shapes = (static_support_shapes(world, None, BitMask32.bit(0), cache=static_cache, packet_cache=packet_cache)
                     if any(car.coupled_suspension and car.config.finite_drivetrain for car, _action in cars) else None)
    parallel = (workers is not None and len(cars) > 1 and substeps > 1
                and not any(car.config.unsprung_enabled for car, _action in cars))
    for index in range(substeps):
        skip_distant = recover is not None and index > 0
        if observe is not None or skip_distant:
            player_pos = cars[0][0]._chassis.getTransform().getPos()
        if observe is not None:
            player_chassis = cars[0][0]._chassis
            before = {
                player_chassis: (
                    Vec3(player_chassis.getLinearVelocity()),
                    Vec3(player_chassis.getAngularVelocity()),
                    Vec3(player_pos),
                )
            }
            # 单个机械子步仅 2-8ms，仅预存距玩家 25m 内动态车的步前速度，避免远距 NPC 重复读取。
            for car, _action in cars[1:]:
                body = car._chassis
                pos = body.getTransform().getPos()
                if (pos - player_pos).lengthSquared() <= 625.0:
                    before[body] = (
                        Vec3(body.getLinearVelocity()),
                        Vec3(body.getAngularVelocity()),
                        Vec3(pos),
                    )
        else:
            before = None
        try:
            numerical = []
            pending = []
            committed = set()
            step_num = index + 1
            for i, (car, action) in enumerate(cars):
                if substeps == 1:
                    # 非耦合模型仍可有内部轮胎细分，沿用原串行入口的多次请求/提交。
                    if car.config.tire_substeps != 1:
                        if isinstance(action, VehicleCommand):
                            car.apply_command(action, static_shapes=static_shapes)
                        else:
                            car.apply_control(action, static_shapes=static_shapes)
                        continue
                    request = car.prepare_command(action) if isinstance(action, VehicleCommand) else car.prepare_control(action)
                    stages = car.physics_stages(request, dt, static_shapes=static_shapes)
                    inputs = next(stages, None)
                    if inputs is not None:
                        numerical.append((car, stages, inputs))
                else:
                    request, initial, target, force, torque, has_external = prepared[i]
                    if index and has_external:
                        # Bullet每次推进后清空持续力；保留调用方本拍施加的真实外力/力矩。
                        car._chassis.applyCentralForce(force)
                        car._chassis.applyTorque(torque)
                    if (skip_distant and i and initial is None
                            and (car._chassis.getTransform().getPos() - player_pos).lengthSquared() > 1600.):
                        # Bullet保留轮端执行器值，气动力沿用本拍首个子步的读数。
                        car._chassis.applyCentralForce(Vec3(*car.dynamics.aerodynamic_force_vector))
                        continue
                    if initial is not None:
                        angles = (initial[0] + (target[0] - initial[0]) * step_num / substeps,
                                  initial[1] + (target[1] - initial[1]) * step_num / substeps)
                        stages = car.physics_stages(request, dt, tire_substeps=1, angles=angles,
                                                    accumulate=index > 0, static_shapes=static_shapes, complete_tires=parallel)
                        inputs = next(stages, None)
                        if inputs is not None:
                            numerical.append((car, stages, inputs))
                            if parallel:
                                pending.append(workers.submit(inputs, static_shapes, material))
                    else:
                        car.physics_stages(request, dt)
            # 各车读完本子步后求末状态，再按原车辆/轮端顺序提交；Bullet仍只推进一次。
            requests = [inputs for _car, _stages, inputs in numerical]
            results = (workers.results(requests, pending, query_lock) if parallel
                       else [inputs.solve(query_lock=query_lock) if query_lock is not None else inputs.solve()
                             for inputs in requests])
            solved = zip(((car, stages) for car, stages, _inputs in numerical), results)
            # 独立时钟在输入读取/提交/世界推进期间持锁；纯数值等待不占用相机查询。
            unlocked = parallel and query_lock is not None
            if unlocked:
                query_lock.release()
            try:
                for (car, stages), result in solved:
                    if unlocked:
                        query_lock.acquire()
                    try:
                        try:
                            stages.send(result)
                        except StopIteration:
                            committed.add(car)
                        else:
                            raise RuntimeError("世界子步只允许一次轮端机械求解")
                    finally:
                        if unlocked:
                            query_lock.release()
            finally:
                if unlocked:
                    query_lock.acquire()
        except ArithmeticError as error:
            if parallel and pending:
                workers.drain(pending)
            for _car, stages, _inputs in numerical:
                stages.close()
            if recover is None:
                raise
            uncommitted = [car for car, _stages, _inputs in numerical if car not in committed]
            recover(dt, error, uncommitted or [cars[0][0]])
        world.doPhysics(dt, 0, dt)
        if observe is not None:
            observe(before, index == substeps - 1)
    for (car, _action), velocity in zip(cars, velocities):
        car.after_step(velocity)
