"""四轮独立转动状态、接地坐标和刚体冲量；原生悬架保持独立。"""

import math
from dataclasses import replace

from panda3d.core import Mat3, Quat, Vec3
from wheel_contact_kernels import rotor_frame_geometry

from suspension_kinematics import advance_contact_geometry
from tire_compliance import deformation_frame, project_deformation, world_deformation
from tire_coupling import ContactFrame, advance_coupled, cross, dot
from tire_drivetrain import DrivetrainInput, solve_drivetrain_stages
from tire_forces import slip_state
from tire_properties import tire_grip, tire_stiffness
from vehicle_config import CAR, wheel_hubs
from vehicle_contacts import road_support
from vehicle_state import WheelDynamicsState, WheelState
from wheel_dynamics import Mobility, advance_wheel
from wheel_geometry import contact_geometry, mechanical_axis


class Tires:
    def __init__(self, config=CAR):
        self.config = config
        self.hubs = wheel_hubs(config)
        self.rear_config = replace(config, lateral_stiffness=config.rear_lateral_stiffness)
        self.omega = [0.0] * 4
        self.rotation = [0.0] * 4
        self.deformation = [(0.0, 0.0, 0.0)] * 4
        self.states = tuple(WheelDynamicsState() for _ in range(4))

    def initialize_rolling(self, speed):
        """仅用于试验初始条件；运行中轮速始终由转矩方程积分。"""
        self.omega = [speed / self.config.wheel_radius] * 4

    def driven_omega(self, chassis, angles=(0., 0.)):
        orientation = chassis.getTransform().getQuat()
        if self.config.front_drive_share == 0:
            return (self.omega[2] + self.omega[3]) / 2 + chassis.getAngularVelocity().dot(orientation.getRight())
        angular = tuple(chassis.getAngularVelocity())
        return sum(weight * (self.omega[i] + dot(angular, mechanical_axis(
            orientation.getRight(), orientation.getForward(), angles[i] if i < 2 else 0.)))
            for i, weight in enumerate(self.config.drive_weights))

    def advance(self, chassis, contacts, angles, drive, engine_drag, pressures, tick, dt,
                external_velocity=(0.0, 0.0, 0.0), external_angular=(0.0, 0.0, 0.0), *, powertrain=None,
                suspension=None, substeps=None, accumulate=False):
        return solve_drivetrain_stages(self.advance_stages(
            chassis, contacts, angles, drive, engine_drag, pressures, tick, dt,
            external_velocity, external_angular, powertrain=powertrain,
            suspension=suspension, substeps=substeps, accumulate=accumulate))

    def advance_stages(self, chassis, contacts, angles, drive, engine_drag, pressures, tick, dt,
                       external_velocity=(0.0, 0.0, 0.0), external_angular=(0.0, 0.0, 0.0), *, powertrain=None,
                       suspension=None, substeps=None, accumulate=False):
        """准备完整机械输入，等待末状态，再按原轮序向唯一车身提交冲量。"""
        pose = chassis.getTransform()
        origin = pose.getPos()
        orientation = pose.getQuat()
        inv_inertia = chassis.getInvInertiaTensorWorld()
        tensor = tuple(tuple((inv_inertia.getCell(a, b) + inv_inertia.getCell(b, a)) / 2
                             for b in range(3)) for a in range(3))
        config = self.config
        envelope_geometry = ({"width": config.wheel_width, "shoulder": config.wheel_shoulder_radius,
                              "crown": config.wheel_crown_height}
                             if config.suspension_si_enabled and config.suspension_coupled_enabled else {})
        normal_steps = []
        normal_impulses = []
        if suspension is not None:
            normal_adapter, normal_system, on_asphalt = suspension
            initial_normal_system = normal_system
        wheel_frames = []
        for index in range(4):
            angle = angles[index] if index < 2 else 0.0
            steering = Quat()
            steering.setHpr(Vec3(-angle, 0, 0))
            heading = orientation.xform(steering.xform(Vec3(0, 1, 0)))
            contact = contacts[index] if contacts else None
            supported = contact is not None and contact.in_contact and road_support(
                contact.contact_normal
            )
            if supported:
                normal = Vec3(*contact.contact_normal)
                tangent = (heading - normal * heading.dot(normal)).normalized()
                axle = tangent.cross(normal)
                point = Vec3(*contact.contact_point) - origin
                load = contact.normal_load
                mu = config.road_friction if contact.surface == "asphalt" else config.grass_friction
            else:
                normal = orientation.getUp()
                tangent = heading
                axle = tangent.cross(normal)
                point = orientation.xform(Vec3(*self.hubs[index])) - normal * config.wheel_radius
                load, mu = 0.0, config.road_friction
            hub = point + normal * config.wheel_radius
            # Fx在接点的力矩减去轮轴的r*Fx反力矩，等效于轮心力与内部驱动反力。
            moment_x = point.cross(tangent) - axle * config.wheel_radius
            moment_y = point.cross(axle)
            response_x = inv_inertia.xform(moment_x)
            response_y = inv_inertia.xform(moment_y)
            response_t = inv_inertia.xform(axle)
            elastic_frame = None
            if config.tire_compliance:
                elastic_frame = deformation_frame(tuple(tangent), tuple(normal))
                tangent, axle, normal = elastic_frame
                point = tuple(point)
                hub = tuple(point[a] + normal[a] * config.wheel_radius for a in range(3))
                moment_x, moment_y = cross(hub, tangent), cross(point, axle)
                # 同一对称惯量与双精度正交基用于所有轮的速度、作用与反作用。
                response_x, response_y, response_t = tuple(
                    tuple(dot(row, vector) for row in tensor) for vector in (moment_x, moment_y, axle))
                mobility = Mobility(
                    1 / config.mass + dot(moment_x, response_x),
                    dot(moment_x, response_y), dot(moment_x, response_t),
                    1 / config.mass + dot(moment_y, response_y),
                    dot(moment_y, response_t), dot(axle, response_t))
            else:
                mobility = Mobility(
                    1 / config.mass + moment_x.dot(response_x),
                    moment_x.dot(response_y), moment_x.dot(response_t),
                    1 / config.mass + moment_y.dot(response_y),
                    moment_y.dot(response_t), axle.dot(response_t))
            wheel_frames.append(ContactFrame(
                angle, supported, load, mu, tangent, axle, point, hub, mobility,
                elastic_frame,
                tuple(response_x), tuple(response_y), tuple(response_t),
            ))

        substeps = config.tire_substeps if substeps is None else substeps
        sub_dt = dt / substeps
        initial_angles = tuple(state.steering for state in self.states)
        base_frames = tuple(wheel_frames)

        def rotor_frames(fraction, previous_fraction):
            frames, torques = [], []
            geometries = rotor_frame_geometry(tuple(orientation.getRight()), tuple(orientation.getForward()),
                initial_angles, tuple(base.steering for base in base_frames),
                tuple(base.elastic_frame[2] if config.tire_compliance else tuple(Vec3(*base.hub) - Vec3(*base.point))
                      for base in base_frames), tuple(tuple(base.point) for base in base_frames), tensor, tuple(self.omega),
                (config.wheel_radius, config.mass, config.wheel_inertia, sub_dt, fraction, previous_fraction,
                 config.wheel_width if envelope_geometry else None, config.wheel_shoulder_radius, config.wheel_crown_height))
            for base, geometry in zip(base_frames, geometries):
                angle, axis, elastic_frame, radius, moment_x, rx, ry, rt, mobility, torque = geometry
                tangent, lateral, _normal = elastic_frame
                frames.append(ContactFrame(angle, base.supported, base.load, base.mu, tangent, lateral,
                    base.point, base.hub, Mobility(*mobility), elastic_frame, rx, ry, rt, axis, radius, moment_x))
                torques.append(torque)
            return frames, tuple(torques)

        states = [None] * 4
        longitudinal_impulses = [state.longitudinal_impulse if accumulate else 0. for state in self.states]
        lateral_impulses = [state.lateral_impulse if accumulate else 0. for state in self.states]
        brake_angular_impulses = [state.brake_angular_impulse if accumulate else 0. for state in self.states]
        rolling_angular_impulses = [state.rolling_angular_impulse if accumulate else 0. for state in self.states]
        rolling_dissipation = [state.rolling_dissipation if accumulate else 0. for state in self.states]
        material_dissipation = [state.material_dissipation if accumulate else 0. for state in self.states]
        road_dissipation = [state.road_dissipation if accumulate else 0. for state in self.states]
        elastic_numerical_dissipation = [state.elastic_numerical_dissipation if accumulate else 0. for state in self.states]
        frame_dissipation = [state.frame_dissipation if accumulate else 0. for state in self.states]
        gyro_impulses = [list(state.gyro_angular_impulse) if accumulate else [0.] * 3 for state in self.states]
        steering_impulses = [list(state.steering_angular_impulse) if accumulate else [0.] * 3 for state in self.states]
        steering_work = [state.steering_work if accumulate else 0. for state in self.states]
        longitudinal_angular_impulses = [list(state.longitudinal_angular_impulse) if accumulate else [0.] * 3 for state in self.states]
        lateral_angular_impulses = [list(state.lateral_angular_impulse) if accumulate else [0.] * 3 for state in self.states]
        drives = (0.0, 0.0, drive / 2, drive / 2)
        capacities = tuple(config.brake_torque * pressures[i] * (
            config.front_brake_share if i < 2 else 1 - config.front_brake_share) / 2
            + (engine_drag / 2 if i >= 2 else 0.0) for i in range(4))
        force_initial = tuple((state.fx, state.fy, state.brake_torque) for state in self.states)
        rolling_coefficients = (tuple(config.rolling_coefficient if c.surface == "asphalt" else config.grass_rolling_coefficient
                                      for c in contacts) if config.finite_drivetrain and config.wheel_rolling_resistance else (0.,) * 4)
        for substep in range(substeps):
            steps = None
            fraction = (substep + 1) / substeps
            torques = ((0.0, 0.0, 0.0),) * 4
            if config.wheel_rotor_transport:
                wheel_frames, torques = rotor_frames(fraction, substep / substeps)
            if config.tire_compliance or config.wheel_rotor_transport or config.finite_drivetrain:
                projected = []
                for i, frame in enumerate(wheel_frames):
                    elastic, loss = (project_deformation(self.deformation[i], frame.elastic_frame,
                                                        config.tire_contact_stiffness)
                                     if config.tire_compliance else ((0.0, 0.0), 0.0))
                    projected.append(elastic)
                    frame_dissipation[i] += loss
                free_velocity = tuple(chassis.getLinearVelocity()[a] + external_velocity[a] * fraction for a in range(3))
                free_angular = tuple(chassis.getAngularVelocity()[a] + external_angular[a] * fraction for a in range(3))
                if config.finite_drivetrain:
                    if suspension is not None:
                        # 固定当拍路面资格，实际离地/再支撑由本子步求出的轮荷决定。
                        wheel_frames = tuple(frame if frame.supported == base.supported else replace(frame, supported=base.supported)
                                             for frame, base in zip(wheel_frames, base_frames))
                    result = yield DrivetrainInput((free_velocity, free_angular, tuple(self.omega), powertrain.engine_omega,
                        wheel_frames, projected, powertrain.engine_torque_request, powertrain.capacity,
                        powertrain.mechanical_ratio, capacities, config, self.rear_config, sub_dt), {
                        "inverse_inertia": tensor, "engine_inertia": config.engine_inertia,
                        "engine_axis": tuple(orientation.xform(Vec3(*config.engine_axis))),
                        "engine_drag": powertrain.engine_drag_coefficient, "efficiency": config.drivetrain_efficiency,
                        "steering_torques": torques,
                        "force_initial": force_initial,
                        "shaft_omega": powertrain.shaft_omega if powertrain.input_shaft_active else None,
                        "shaft_inertia": config.input_shaft_inertia,
                        "shaft_axis": tuple(orientation.xform(Vec3(*config.input_shaft_axis))),
                        "synchronizing": powertrain.synchronizing,
                        "synchronizer_capacity": config.synchronizer_capacity if powertrain.synchronizing else 0.,
                        "downstream_omega": powertrain.downstream_omega if powertrain.downstream_active else (),
                        "downstream_inertias": config.downstream_inertias,
                        "downstream_axes": tuple(tuple(orientation.xform(Vec3(*axis))) for axis in config.downstream_axes)
                            if powertrain.downstream_active else (), "suspension": normal_system if suspension is not None else None,
                        "rolling_coefficients": rolling_coefficients})
                    steps = result.wheels
                    force_initial = tuple((step.fx, step.fy, step.brake_torque) for step in steps)
                    drives = result.wheel_drive_torques
                    end_angular = result.angular
                    if suspension is not None:
                        normal_system = result.suspension_system
                        impulses = normal_adapter.apply_step(chassis, normal_system, result.suspension, sub_dt)
                        normal_impulses.append(impulses)
                        normal_steps.append((sub_dt, result.suspension))
                        actual_contacts = normal_adapter.contacts(normal_system, result.suspension, on_asphalt)
                        wheel_frames = tuple(replace(frame, load=contact.normal_load if base.supported else 0.,
                                                     supported=contact.in_contact and base.supported)
                                             for frame, contact, base in zip(wheel_frames, actual_contacts, base_frames))
                    powertrain.accept_step(result, sub_dt)
                    chassis.applyTorqueImpulse(Vec3(*result.engine_body_torque) * sub_dt)
                    if powertrain.input_shaft_active:
                        chassis.applyTorqueImpulse(Vec3(*result.shaft_body_torque) * sub_dt)
                    if powertrain.downstream_active:
                        chassis.applyTorqueImpulse(Vec3(*result.downstream_body_torque) * sub_dt)
                else:
                    steps = advance_coupled(free_velocity, free_angular, self.omega, wheel_frames,
                                            projected, drives, capacities, config, self.rear_config, sub_dt,
                                            inverse_inertia=tensor, steering_torques=torques)
                if config.wheel_rotor_transport and not config.finite_drivetrain:
                    angular_increment = tuple(sum(
                        frame.response_x[a] * step.fx + frame.response_y[a] * step.fy
                        + frame.response_t[a] * (drives[i] - step.brake_torque)
                        + dot(tensor[a], tuple(step.gyro_torque[b] + step.steering_torque[b] for b in range(3)))
                        for i, (frame, step) in enumerate(zip(wheel_frames, steps))) for a in range(3))
                    end_angular = tuple(free_angular[a] + sub_dt * angular_increment[a] for a in range(3))
            # 正反次序成对，避免固定左轮先积分产生持续偏航偏置。
            order = range(4) if substep % 2 == 0 else range(3, -1, -1)
            for index in order:
                frame = wheel_frames[index]
                angle, supported, load, mu = frame.steering, frame.supported, frame.load, frame.mu
                tangent, axle, point, hub = frame.tangent, frame.axle, frame.point, frame.hub
                mobility, elastic_frame = frame.mobility, frame.elastic_frame
                requested_drive, capacity = drives[index], capacities[index]
                if config.tire_compliance or config.wheel_rotor_transport or config.finite_drivetrain:
                    step = steps[index]
                    if config.tire_compliance or config.wheel_rotor_transport:
                        self.deformation[index] = world_deformation(
                            (step.deformation_x, step.deformation_y), elastic_frame)
                else:
                    # 原刚性分支的外力预报时序保留，用于冻结机械对照。
                    velocity = chassis.getLinearVelocity() + Vec3(*external_velocity)
                    angular = chassis.getAngularVelocity() + Vec3(*external_angular)
                    vx = (velocity + angular.cross(hub)).dot(tangent)
                    vy = (velocity + angular.cross(point)).dot(axle)
                    step = advance_wheel(
                        self.omega[index], float(vx), float(vy), float(angular.dot(axle)),
                        requested_drive, capacity, load, mu, mobility, sub_dt,
                        config if index < 2 else self.rear_config,
                    )
                force = Vec3(*tangent) * step.fx + Vec3(*axle) * step.fy
                chassis.applyImpulse(force * sub_dt, Vec3(*point))
                radius = frame.rolling_radius if config.wheel_rotor_transport else config.wheel_radius
                spin_axis = frame.spin_axis if config.wheel_rotor_transport else axle
                reaction = requested_drive - step.brake_torque - radius * step.fx
                chassis.applyTorqueImpulse(Vec3(*spin_axis) * (sub_dt * reaction))
                if config.wheel_rotor_transport:
                    chassis.applyTorqueImpulse(Vec3(*(sub_dt * (step.gyro_torque[a] + step.steering_torque[a])
                                                     for a in range(3))))
                    for a in range(3):
                        gyro_impulses[index][a] += sub_dt * step.gyro_torque[a]
                        steering_impulses[index][a] += sub_dt * step.steering_torque[a]
                        longitudinal_angular_impulses[index][a] += sub_dt * step.fx * cross(point, tangent)[a]
                        lateral_angular_impulses[index][a] += sub_dt * step.fy * cross(point, axle)[a]
                    steering_work[index] += sub_dt * dot(end_angular, step.steering_torque)
                longitudinal_impulses[index] += sub_dt * step.fx
                lateral_impulses[index] += sub_dt * step.fy
                brake_angular_impulses[index] += sub_dt * step.brake_torque
                rolling_angular_impulses[index] += sub_dt * step.rolling_torque
                rolling_dissipation[index] += step.rolling_dissipation
                material_dissipation[index] += step.material_dissipation
                road_dissipation[index] += step.road_dissipation
                elastic_numerical_dissipation[index] += step.elastic_numerical_dissipation
                self.omega[index] = step.omega
                self.rotation[index] += sub_dt * step.relative_omega
                wheel_config = config if index < 2 else self.rear_config
                cx, cy = tire_stiffness(load, wheel_config)
                states[index] = WheelDynamicsState(
                    omega=step.omega, rotation=self.rotation[index],
                    relative_omega=step.relative_omega,
                    longitudinal_speed=step.vx, lateral_speed=step.vy,
                    kappa=step.kappa if supported else None,
                    alpha=step.alpha if supported else None,
                    fx=step.fx, fy=step.fy, drive_torque=requested_drive,
                    brake_capacity=capacity, brake_torque=step.brake_torque,
                    normal_load=load, road_support=supported, steering=angle,
                    force_contact_tick=tick, force_residual=step.residual,
                    force_kappa=step.kappa if supported else None,
                    force_alpha=step.alpha if supported else None,
                    force_mode=step.mode,
                    longitudinal_impulse=longitudinal_impulses[index],
                    lateral_impulse=lateral_impulses[index],
                    brake_angular_impulse=brake_angular_impulses[index],
                    force_grip=tire_grip(load, mu, config),
                    force_longitudinal_stiffness=cx, force_lateral_stiffness=cy,
                    deformation_x=step.deformation_x, deformation_y=step.deformation_y,
                    force_patch_kappa=step.patch_kappa if supported else None,
                    force_patch_alpha=step.patch_alpha if supported else None,
                    elastic_energy=step.elastic_energy,
                    material_dissipation=material_dissipation[index],
                    road_dissipation=road_dissipation[index],
                    elastic_numerical_dissipation=elastic_numerical_dissipation[index],
                    frame_dissipation=frame_dissipation[index],
                    deformation_rate_x=step.deformation_rate_x, deformation_rate_y=step.deformation_rate_y,
                    mechanical_axis=tuple(spin_axis) if config.wheel_rotor_transport else (0.0, 0.0, 0.0),
                    rolling_radius=radius if config.wheel_rotor_transport else None,
                    gyro_angular_impulse=tuple(gyro_impulses[index]),
                    steering_angular_impulse=tuple(steering_impulses[index]),
                    steering_work=steering_work[index],
                    longitudinal_angular_impulse=tuple(longitudinal_angular_impulses[index]),
                    lateral_angular_impulse=tuple(lateral_angular_impulses[index]),
                    rolling_torque=step.rolling_torque,
                    rolling_angular_impulse=rolling_angular_impulses[index],
                    rolling_dissipation=rolling_dissipation[index],
                    force_rolling_radius=radius,
                )
            if suspension is not None:
                final_normal_system = normal_system
                if substep + 1 < substeps:
                    # 下一轮端子步才需要几何外推；末子步之后由唯一Bullet世界实际推进。
                    normal_system = advance_contact_geometry(normal_system, result.suspension.compression,
                                                             result.velocity, result.angular, sub_dt)
        self.states = tuple(states)
        if suspension is not None:
            return normal_adapter.publish(initial_normal_system, final_normal_system,
                                          tuple(normal_steps), on_asphalt, tick,
                                          tuple(tuple(sum(part[k][a] for part in normal_impulses) for a in range(3)) for k in range(2)))

    def observe(self, chassis, contacts, tick):
        """完成Bullet步后采样当前滑移；保留前一施力阶段的力与求解滑移。"""
        pose = chassis.getTransform()
        velocity, angular = chassis.getLinearVelocity(), chassis.getAngularVelocity()
        states = []
        for index, (state, contact) in enumerate(zip(self.states, contacts)):
            steer = Quat()
            steer.setHpr(Vec3(-state.steering, 0, 0))
            heading = pose.getQuat().xform(steer.xform(Vec3(0, 1, 0)))
            supported = contact.in_contact and road_support(contact.contact_normal)
            if supported:
                normal = Vec3(*contact.contact_normal)
                tangent = (heading - normal * heading.dot(normal)).normalized()
                point = Vec3(*contact.contact_point) - pose.getPos()
            else:
                normal = pose.getQuat().getUp()
                tangent = heading
                point = pose.getQuat().xform(Vec3(*self.hubs[index]))
                point -= normal * self.config.wheel_radius
            axle = tangent.cross(normal)
            hub = point + normal * self.config.wheel_radius
            vx = (velocity + angular.cross(hub)).dot(tangent)
            vy = (velocity + angular.cross(point)).dot(axle)
            radius, spin_axis = self.config.wheel_radius, tuple(axle)
            if self.config.wheel_rotor_transport:
                spin_axis = mechanical_axis(pose.getQuat().getRight(), pose.getQuat().getForward(), state.steering)
                config = self.config
                geometry = ({"width": config.wheel_width, "shoulder": config.wheel_shoulder_radius,
                             "crown": config.wheel_crown_height}
                            if config.suspension_si_enabled and config.suspension_coupled_enabled else {})
                spin_axis, frame, radius, moment_x = contact_geometry(spin_axis, tuple(normal), tuple(point), radius, **geometry)
                tangent, axle, _normal = frame
                vx = dot(velocity, tangent) + dot(angular, moment_x)
                vy = dot(tuple(velocity[a] + cross(angular, point)[a] for a in range(3)), axle)
            kappa, alpha = slip_state(vx, vy, self.omega[index],
                                      radius, self.config)
            mu = self.config.road_friction if contact.surface == "asphalt" else self.config.grass_friction
            states.append(replace(
                state, relative_omega=self.omega[index] + (dot(angular, spin_axis)
                    if self.config.wheel_rotor_transport else angular.dot(axle)),
                longitudinal_speed=float(vx), lateral_speed=float(vy),
                kappa=kappa if supported else None, alpha=alpha if supported else None,
                sample_support=supported, sample_tick=tick,
                sample_grip=tire_grip(contact.normal_load, mu, self.config) if supported else 0.0,
                mechanical_axis=spin_axis if self.config.wheel_rotor_transport else (0.0, 0.0, 0.0),
                rolling_radius=radius if self.config.wheel_rotor_transport else None,
            ))
        self.states = tuple(states)

    def wheel_poses(self, chassis, bullet_vehicle):
        """原生矩阵提供悬架位置；转向和滚动来自真实执行器及独立转角。"""
        chassis_orientation = chassis.getTransform().getQuat()
        wheels = []
        for index, wheel in enumerate(bullet_vehicle.getWheels()):
            steer = Quat()
            steer.setHpr(Vec3(-self.states[index].steering, 0, 0))
            roll = Quat()
            roll.setFromAxisAngle(-math.degrees(self.rotation[index]), Vec3(1, 0, 0))
            rows = [chassis_orientation.xform(steer.xform(roll.xform(axis))) for axis in (
                Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1),
            )]
            orientation = Quat()
            orientation.setFromMatrix(Mat3(*(value for row in rows for value in row)))
            wheels.append(WheelState(tuple(wheel.getWorldTransform().getRow3(3)),
                                     tuple(orientation)))
        return tuple(wheels)
