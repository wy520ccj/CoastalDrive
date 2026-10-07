"""A single Bullet vehicle, detached from world and traffic management."""

import math
from dataclasses import replace

from panda3d.bullet import BulletRigidBodyNode, BulletVehicle, ZUp
from panda3d.core import BitMask32, TransformState, Vec3

from driver_assist import GAME_INPUT, DriverAssist
from powertrain import Powertrain
from suspension import native_coefficients
from vehicle_brakes import Brakes
from vehicle_collision import install_chassis_shape
from vehicle_config import CAR, wheel_hubs
from vehicle_contacts import read_wheel_contacts, road_support, shift_contacts
from vehicle_dynamics import DynamicsState, aerodynamic_load, axle_loads, contact_grade
from vehicle_stability import StabilityControl
from vehicle_state import FIXED_DT, CarState, Control, VehicleCommand, forward
from vehicle_steering import SteeringRack, wheel_angles
from vehicle_suspension import Suspension
from vehicle_tires import Tires
from vehicle_traction import TractionControl


class Vehicle:
    def __init__(
        self,
        world,
        on_asphalt,
        spawn,
        *,
        name="player-chassis",
        wind=(0, 0, 0),
        heading=0,
        pitch=0,
        reverse_enabled=True,
        config=CAR,
        input_config=GAME_INPUT,
    ):
        self.config = config
        self.input_config = input_config
        self.hubs = wheel_hubs(config)
        self._world = world
        self.on_asphalt = on_asphalt
        self.spawn = tuple(spawn)
        self.wind = Vec3(*wind)
        self.reverse_enabled = reverse_enabled
        self.name = name
        self._chassis = None
        self._vehicle = None
        self.closed = False
        self.assist = DriverAssist(self.config, self.input_config)
        self.powertrain = Powertrain(self.config)
        self.steering = SteeringRack(self.config)
        self.tires = Tires(self.config)
        self.suspension = Suspension(self.config, self.hubs)
        self.brakes = Brakes(self.config.braking)
        self.traction = TractionControl(self.config.traction, self.config.driven_wheels)
        self.stability = StabilityControl(self.config)
        self._drive_pedal = 0.0
        self._brake_pedal = 0.0
        self._acceleration = 0.0
        self._lateral_acceleration = 0.0
        self._load_acceleration = 0.0
        self._contact_ready = False
        self._wheel_contacts = ()
        self._contact_tick = 0
        self.dynamics = DynamicsState()
        self._build_physics(heading, pitch)

    def _build_physics(self, heading, pitch):
        chassis = BulletRigidBodyNode(self.name)
        chassis.setIntoCollideMask(BitMask32.bit(1))
        chassis.setMass(self.config.mass)
        chassis.setDeactivationEnabled(False)
        chassis.setAngularDamping(self.config.angular_damping)
        install_chassis_shape(chassis, self.config)
        chassis.setTransform(TransformState.makePosHpr(Vec3(*self.spawn), Vec3(heading, pitch, 0)))
        chassis.setCcdMotionThreshold(0.5)
        chassis.setCcdSweptSphereRadius(0.35)
        self._world.attachRigidBody(chassis)

        vehicle = BulletVehicle(self._world, chassis)
        vehicle.setCoordinateSystem(ZUp)
        self._world.attachVehicle(vehicle)
        for index, (x, y, z) in enumerate(self.hubs):
            wheel = vehicle.createWheel()
            wheel.setChassisConnectionPointCs(Vec3(x, y, z))
            wheel.setWheelDirectionCs(Vec3(0, 0, -1))
            wheel.setWheelAxleCs(Vec3(1, 0, 0))
            wheel.setWheelRadius(self.config.wheel_radius)
            wheel.setFrontWheel(y > 0)
            wheel.setMaxSuspensionTravelCm(self.config.suspension_travel * 100)
            wheel.setMaxSuspensionForce(self.config.suspension_force_limit)
            stiffness, compression, extension = native_coefficients(self.config, index, chassis.getMass())
            if self.coupled_suspension:
                stiffness = compression = extension = 0.
            wheel.setSuspensionStiffness(stiffness)
            wheel.setWheelsDampingRelaxation(extension)
            wheel.setWheelsDampingCompression(compression)
            wheel.setFrictionSlip(0)
            wheel.setRollInfluence(0.1)

        self._chassis = chassis
        self._vehicle = vehicle
        self._initialize_wheel_poses()

    def _initialize_wheel_poses(self):
        pose = self._chassis.getTransform()
        for wheel, hub in zip(self._vehicle.getWheels(), self.hubs):
            position = pose.getMat().xformPoint(Vec3(*hub) - Vec3(0, 0, 0.4))
            wheel.setWorldTransform(TransformState.makePosHpr(position, pose.getHpr()).getMat())

    @property
    def coupled_suspension(self):
        return self.config.suspension_si_enabled and self.config.suspension_coupled_enabled

    def reset(self, position, heading=0, pitch=0, *, speed=0.0):
        self._chassis.setTransform(
            TransformState.makePosHpr(Vec3(*position), Vec3(heading, pitch, 0))
        )
        self._chassis.setLinearVelocity(Vec3(*forward(heading)) * speed)
        self._chassis.setAngularVelocity(Vec3(0, 0, 0))
        self._chassis.clearForces()
        self._chassis.setActive(True)
        self._vehicle.resetSuspension()
        self.assist = DriverAssist(self.config, self.input_config)
        self.powertrain = Powertrain(self.config)
        self.steering = SteeringRack(self.config)
        self.tires = Tires(self.config)
        self.suspension = Suspension(self.config, self.hubs)
        self.brakes = Brakes(self.config.braking)
        self.traction = TractionControl(self.config.traction, self.config.driven_wheels)
        self.stability = StabilityControl(self.config)
        self.tires.initialize_rolling(speed)
        self.powertrain.initialize_rolling(speed)
        self._drive_pedal = 0.0
        self._brake_pedal = 0.0
        self._acceleration = 0.0
        self._lateral_acceleration = 0.0
        self._load_acceleration = 0.0
        self._contact_ready = False
        self._wheel_contacts = ()
        self._contact_tick = 0
        self.dynamics = DynamicsState()
        for index, wheel in enumerate(self._vehicle.getWheels()):
            self._vehicle.applyEngineForce(0, index)
            self._vehicle.setBrake(0, index)
            self._vehicle.setSteeringValue(0, index)
            wheel.setRotation(0)
            wheel.setDeltaRotation(0)
        self._initialize_wheel_poses()

    def signed_speed(self):
        velocity = self._chassis.getLinearVelocity()
        heading = self._chassis.getTransform().getHpr().x
        return velocity.dot(Vec3(*forward(heading)))

    def shift(self, amount):
        """Move the coordinate frame without resetting suspension or drivetrain."""
        pose = self._chassis.getTransform()
        self._chassis.setTransform(
            TransformState.makePosHpr(pose.getPos() - Vec3(0, amount, 0), pose.getHpr())
        )
        for wheel in self._vehicle.getWheels():
            pose = TransformState.makeMat(wheel.getWorldTransform())
            wheel.setWorldTransform(
                TransformState.makePosQuatScale(
                    pose.getPos() - Vec3(0, amount, 0), pose.getQuat(), Vec3(1)
                ).getMat()
            )
        self._wheel_contacts = shift_contacts(self._wheel_contacts, amount)

    def apply_control(self, control: Control, *, static_shapes=None):
        self.advance_physics(self.prepare_control(control), FIXED_DT, static_shapes=static_shapes)

    def prepare_control(self, control: Control):
        """120Hz采样驾驶请求；机械子步不重复积分输入辅助。"""
        command = self.assist.command(
            control, self.signed_speed(), self.powertrain.gear, self.reverse_enabled, FIXED_DT
        )
        # 玩家制动优先形成零油门请求；显式研究请求仍允许同时油门/制动。
        # 历史传动在advance内执行此优先级，冻结分支保留其原请求口径。
        if self.config.finite_drivetrain and command.brake > 0:
            command = replace(command, throttle=0.)
        return self.prepare_command(command)

    def apply_command(self, command: VehicleCommand, *, static_shapes=None):
        """驾驶辅助和研究控制共用同一执行器与轮胎受力路径。"""
        self.advance_physics(self.prepare_command(command), FIXED_DT, static_shapes=static_shapes)

    def prepare_command(self, command: VehicleCommand):
        """转向、电子控制及执行器只按固定120Hz准备一次。"""
        pose = self._chassis.getTransform()
        hpr = pose.getHpr()
        velocity = self._chassis.getLinearVelocity()
        speed = velocity.dot(Vec3(*forward(hpr.x)))
        self.steering.advance(command.steering, FIXED_DT)
        for wheel_index, angle in enumerate(wheel_angles(self.steering.angle, self.config)):
            self._vehicle.setSteeringValue(-angle, wheel_index)

        pedal, brake, direction = command.throttle, command.brake, command.direction
        self._drive_pedal = (pedal if self.config.finite_drivetrain
                             else pedal if direction != 0 and brake == 0 else 0.0)
        self._brake_pedal = brake
        requests = ((brake,) * 4 if command.wheel_brakes is None else command.wheel_brakes)
        traction_direction = direction
        if self.config.finite_drivetrain:
            # TCS读取上一完整机械步的实际挡位；方向只请求换挡，空挡没有驱动资格。
            traction_direction = (self.powertrain.gear > 0) - (self.powertrain.gear < 0)
        traction = self.traction.advance(
            pedal, traction_direction, brake > 0 or any(requests), self.tires.states,
            self.config.wheel_radius, FIXED_DT,
        )
        requests = tuple(max(driver, electronic) for driver, electronic in
                         zip(requests, traction.brake_requests))
        stability = self.stability.advance(
            self._chassis, self.tires.states, self._wheel_contacts, requests,
            self.steering.angle, FIXED_DT,
        )
        if self.config.finite_drivetrain:
            self.powertrain.observe(self._chassis)
            self.powertrain.prepare(speed, self.tires.driven_omega(
                self._chassis, wheel_angles(self.steering.angle, self.config)), pedal, direction,
                brake > 0, FIXED_DT, drive_scale=min(traction.torque_scale, stability.torque_scale),
                gear=command.gear, clutch=command.clutch)
            drive_torque = engine_drag = 0.
        else:
            drive_torque, engine_drag = self.powertrain.advance(
                speed, self.tires.driven_omega(self._chassis), pedal, direction, brake > 0, FIXED_DT,
                drive_scale=min(traction.torque_scale, stability.torque_scale),
            )
        requests = stability.brake_requests
        pressures = self.brakes.advance(requests, self.tires.states, self.config.wheel_radius, FIXED_DT)
        return drive_torque, engine_drag, pressures

    def advance_physics(self, request, dt, *, tire_substeps=None, angles=None, accumulate=False, static_shapes=None):
        """从当前真实Bullet姿态读取接点，完成一个机械/世界共用的积分子步。"""
        drive_torque, engine_drag, pressures = request
        pose = self._chassis.getTransform()
        hpr = pose.getHpr()
        velocity = self._chassis.getLinearVelocity()
        angles = wheel_angles(self.steering.angle, self.config) if angles is None else angles
        position = pose.getPos()
        road = self.on_asphalt(position.x, position.y)
        grade = self._road_grade(hpr.x)
        front_load, rear_load = (
            axle_loads(self._load_acceleration, grade, self.config) if grade is not None else (0.0, 0.0)
        )
        # 自定义轮胎独占切向受力；原生车辆只保留射线悬架和轮心位置。
        for index, wheel in enumerate(self._vehicle.getWheels()):
            wheel.setFrictionSlip(0)
            self._vehicle.applyEngineForce(0, index)
            self._vehicle.setBrake(0, index)
        normal_load = sum(
            contact.normal_load for contact in self._wheel_contacts
            if contact.in_contact and road_support(contact.contact_normal)
        )
        horizontal = Vec3(velocity.x, velocity.y, 0)
        horizontal_speed = horizontal.length()
        air_velocity, air_force = aerodynamic_load(tuple(velocity), tuple(self.wind), self.config)
        aero = math.sqrt(sum(x*x for x in air_force))
        self._chassis.applyCentralForce(Vec3(*air_force))
        rolling = 0.0
        wheel_rolling = self.config.finite_drivetrain and self.config.wheel_rolling_resistance
        if not wheel_rolling and horizontal_speed > 0.01 and normal_load > 0:
            coefficient = self.config.rolling_coefficient if road else self.config.grass_rolling_coefficient
            rolling = coefficient * normal_load * min(horizontal_speed, 1)
            self._chassis.applyCentralForce(-horizontal * (rolling / horizontal_speed))
        external_velocity = (
            self._chassis.getGravity() + self._chassis.getTotalForce() / self.config.mass
        ) * dt
        external_angular = self._chassis.getInvInertiaTensorWorld().xform(
            self._chassis.getTotalTorque()
        ) * dt
        tire_contact_tick = self._contact_tick
        suspension = None
        previous_suspension = self.suspension.state
        if self.coupled_suspension:
            tire_contact_tick += 1
            if self.config.finite_drivetrain:
                system = self.suspension.prepare(self._world, self._chassis, self._vehicle.getWheels(), static_shapes)
                self._wheel_contacts = self.suspension.candidates(system, self.on_asphalt)
                suspension = self.suspension, system, self.on_asphalt
            else:
                self._wheel_contacts = self.suspension.advance(
                    self._world, self._chassis, self._vehicle.getWheels(), self.on_asphalt,
                    tire_contact_tick, dt, tuple(external_velocity), tuple(external_angular))
        coupled_contacts = self.tires.advance(
            self._chassis, self._wheel_contacts, angles,
            drive_torque, engine_drag, pressures, tire_contact_tick, dt,
            tuple(external_velocity), tuple(external_angular),
            powertrain=self.powertrain if self.config.finite_drivetrain else None,
            suspension=suspension,
            substeps=tire_substeps, accumulate=accumulate,
        )
        if suspension is not None:
            self._wheel_contacts = coupled_contacts
            if accumulate:
                self.suspension.accumulate(previous_suspension)
        if wheel_rolling:
            rolling = sum(abs(state.rolling_torque) / state.force_rolling_radius
                          for state in self.tires.states
                          if state.road_support)
        traction_limited = any(
            state.kappa is not None and abs(state.kappa) > 0.1 for state in self.tires.states
        )
        local = pose.getQuat().conjugate().xform(velocity)
        sideslip = math.degrees(math.atan2(local.x, abs(local.y))) if horizontal_speed > 1 else 0
        self.dynamics = DynamicsState(
            aero,
            rolling,
            self.config.mass * 9.81 * math.sin(math.radians(grade)) if grade is not None else 0.0,
            front_load,
            rear_load,
            self._chassis.getAngularVelocity().z,
            sideslip,
            traction_limited,
            grade,
            air_velocity,
            air_force,
            sum(f*v for f,v in zip(air_force,velocity)),
        )

    def _road_grade(self, heading):
        if self.coupled_suspension:
            return contact_grade(heading, [contact.contact_normal for contact in self._wheel_contacts
                                          if contact.in_contact and road_support(contact.contact_normal)])
        normals = []
        if self._contact_ready:
            for wheel in self._vehicle.getWheels():
                contact = wheel.getRaycastInfo()
                if contact.isInContact() and road_support(tuple(contact.getContactNormalWs())):
                    normals.append(tuple(contact.getContactNormalWs()))
        return contact_grade(heading, normals)

    def after_step(self, previous_velocity):
        self._contact_ready = True
        self._contact_tick += 1
        if not self.coupled_suspension:
            self._wheel_contacts = read_wheel_contacts(self._vehicle, self.on_asphalt)
        self.tires.observe(self._chassis, self._wheel_contacts, self._contact_tick)
        if self.config.finite_drivetrain:
            self.powertrain.observe(self._chassis)
        velocity = self._chassis.getLinearVelocity()
        acceleration = (velocity - Vec3(previous_velocity)) / FIXED_DT
        axes = self._chassis.getTransform().getQuat()
        self._acceleration = acceleration.dot(axes.getForward())
        self._lateral_acceleration = acceleration.dot(axes.getRight())
        grade = self._road_grade(self._chassis.getTransform().getHpr().x)
        road_acceleration = 0.0
        if grade is not None:
            angle = math.radians(grade)
            direction = Vec3(*forward(self._chassis.getTransform().getHpr().x))
            tangent = direction * math.cos(angle) + Vec3(0, 0, math.sin(angle))
            road_acceleration = acceleration.dot(tangent)
        self._load_acceleration += (
            max(-12, min(12, road_acceleration)) - self._load_acceleration
        ) * (1 - math.exp(-FIXED_DT / 0.15))

    def snapshot(self, *, include_wheels=True):
        transform = self._chassis.getTransform()
        position = transform.getPos()
        hpr = transform.getHpr()
        velocity = self._chassis.getLinearVelocity()
        # 交通感知只读取车身状态；四轮姿态仍完整提供给正式Snapshot。
        wheels = self.tires.wheel_poses(self._chassis, self._vehicle) if include_wheels else ()
        if include_wheels and self.coupled_suspension:
            positions = self.suspension.wheel_positions(self._chassis, self._vehicle.getWheels())
            wheels = tuple(replace(wheel, position=position) for wheel, position in zip(wheels, positions))
        return CarState(
            (float(position.x), float(position.y), float(position.z)),
            float(hpr.x),
            float(velocity.dot(Vec3(*forward(hpr.x)))),
            float(hpr.y),
            float(hpr.z),
            tuple(wheels),
            "asphalt" if self.on_asphalt(position.x, position.y) else "grass",
            self.steering.angle,
            self._drive_pedal,
            self._brake_pedal,
            self.powertrain.rpm,
            self.powertrain.gear,
            self._acceleration,
            self._lateral_acceleration,
            self.dynamics,
            velocity=tuple(velocity),
            orientation=tuple(transform.getQuat()),
            wheel_contacts=self._wheel_contacts if include_wheels else (),
            contact_tick=self._contact_tick if include_wheels else 0,
            wheel_dynamics=self.tires.states if include_wheels else (),
            brake_states=self.brakes.states if include_wheels else (),
            abs_enabled=self.config.braking.abs_enabled,
            tcs_enabled=self.config.traction.tcs_enabled,
            traction_state=self.traction.state,
            esc_enabled=self.config.stability.esc_enabled,
            stability_state=self.stability.state,
            powertrain_state=self.powertrain.snapshot() if self.config.finite_drivetrain else None,
            suspension_state=self.suspension.state if self.coupled_suspension and include_wheels else None,
        )

    def close(self):
        if self.closed:
            return
        self._world.removeVehicle(self._vehicle)
        self._vehicle = None
        self._chassis = None
        self.closed = True
