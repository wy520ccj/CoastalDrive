"""正常模式交通车：同一Bullet世界的原生悬架、轮胎和车身碰撞。"""

import math
from dataclasses import replace

from panda3d.core import Quat, Vec3

from vehicle import Vehicle, aerodynamic_load
from vehicle_dynamics import DynamicsState
from vehicle_state import FIXED_DT, CarState, WheelState
from vehicle_steering import wheel_angles


class TrafficVehicle(Vehicle):
    def __init__(self, *args, **kwargs):
        config = kwargs['config']
        kwargs['config'] = replace(config, finite_drivetrain=False, native_tire_forces=True, suspension_coupled_enabled=False,
                                   wheel_rotor_transport=False, tire_compliance=False,unsprung_enabled=False,
                                   tire_aligning_enabled=False, suspension_coil_enabled=False,
                                   suspension_spring_preloads=(0.,)*4,
                                   suspension_installation_curves=None, suspension_damper_curves=None,
                                   axle_torque_bias_ratios=(1., 1.),
                                   differential_damping=(0., 0., 0.), differential_capacity=(0., 0., 0.),
                                   braking=replace(config.braking, abs_enabled=False),
                                   traction=replace(config.traction, tcs_enabled=False),
                                   stability=replace(config.stability, esc_enabled=False))
        super().__init__(*args, **kwargs)
        # 完整车原生切向力为零；启用原生轮胎后使用真实接点力臂，避免停车时持续俯仰漂移。
        for wheel in self._vehicle.getWheels():
            wheel.setRollInfluence(1.)
        self.native_dt = 1 / 240
        self._native_request = None
        self._native_mu = None
        self._drive_weights = self.config.drive_weights
        self._park_pose = self._chassis.getTransform()
        self._park_quiet = 0
        self._chassis.setDeactivationEnabled(True)

    def reset(self, position, heading=0, pitch=0, *, speed=0.):
        super().reset(position, heading, pitch, speed=speed)
        self._native_request = None
        self._park_pose = self._chassis.getTransform()
        self._park_quiet = 0

    def prepare_command(self, command, *, input_config=None):
        """原输入辅助/转向执行器与油门响应保留，NPC不执行完整轮端电子控制。"""
        self.steering.advance(command.steering, FIXED_DT)
        for index, angle in enumerate(wheel_angles(self.steering.angle, self.config)):
            self._vehicle.setSteeringValue(-angle, index)
        direction = command.direction
        if command.gear is not None:
            direction = (command.gear > 0) - (command.gear < 0)
        self._drive_pedal = command.throttle if direction and command.brake == 0 else 0.
        self._brake_pedal = command.brake
        if command.throttle > 0 or command.brake < .99 or (
                command.wheel_brakes is not None and min(command.wheel_brakes) < .99):
            self._chassis.setActive(True)
            self._park_quiet = 0
        drive, drag = self.powertrain.advance(self.signed_speed(), self.tires.driven_omega(self._chassis),
            self._drive_pedal, direction, command.brake > 0, FIXED_DT)
        requests = (command.brake,) * 4 if command.wheel_brakes is None else command.wheel_brakes
        pressures = self.brakes.advance(requests, self.tires.states, self.config.wheel_radius, FIXED_DT)
        return drive, drag if direction else 0., pressures

    def physics_stages(self, request, dt, **options):
        drive, drag, pressures = request
        previous_dt = self.native_dt
        self.native_dt = dt
        velocity = self._chassis.getLinearVelocity()
        position = self._chassis.getTransform().getPos()
        road = self.on_asphalt(position.x, position.y)
        mu = self.config.road_friction if road else self.config.grass_friction
        air_velocity, air_force = aerodynamic_load(tuple(velocity), tuple(self.wind), self.config)
        self._chassis.applyCentralForce(Vec3(*air_force))
        radius = self.config.wheel_radius
        # 同一120Hz请求的两个子步保留轮端执行器值；材质/子步长变化时仍立即重写。
        if request is not self._native_request or dt != previous_dt or mu != self._native_mu:
            for i, wheel in enumerate(self._vehicle.getWheels()):
                wheel.setFrictionSlip(mu)
                self._vehicle.applyEngineForce(drive * self._drive_weights[i] / radius, i)
                share = self.config.front_brake_share if i < 2 else 1 - self.config.front_brake_share
                torque = self.config.brake_torque * pressures[i] * share / 2 + drag * self._drive_weights[i]
                # Bullet原生制动上限是每世界子步的冲量。
                self._vehicle.setBrake(torque * dt / radius, i)
            self._native_request, self._native_mu = request, mu
        self.dynamics = DynamicsState(air_relative_velocity=air_velocity, aerodynamic_force_vector=air_force,
            aerodynamic_power=sum(force * speed for force, speed in zip(air_force, velocity)))
        return iter(())

    def after_step(self, previous_velocity):
        pose = self._chassis.getTransform()
        orientation = pose.getQuat()
        body_spin = self._chassis.getAngularVelocity().dot(orientation.getRight())
        wheels = self._vehicle.getWheels()
        self.tires.omega = [wheel.getDeltaRotation() / self.native_dt - body_spin for wheel in wheels]
        self.tires.rotation = [wheel.getRotation() for wheel in wheels]
        acceleration = (self._chassis.getLinearVelocity() - previous_velocity) / FIXED_DT
        self._acceleration = acceleration.dot(orientation.getForward())
        self._lateral_acceleration = acceleration.dot(orientation.getRight())
        self._contact_ready = True
        self._contact_tick += 1
        previous_pose, self._park_pose = self._park_pose, pose
        parking = (self._drive_pedal == 0 and self._brake_pedal >= .99
                   and min(state.pressure for state in self.brakes.states) >= .99)
        if not parking:
            self._park_quiet = 0
            return
        motion = (pose.getPos() - previous_pose.getPos()).length() / FIXED_DT
        rotation = pose.getQuat() * previous_pose.getQuat().conjugate()
        angular = 2 * math.atan2(math.sqrt(sum(rotation[i] ** 2 for i in (1, 2, 3))), abs(rotation[0])) / FIXED_DT
        grounded = all(wheel.getRaycastInfo().isInContact() for wheel in wheels)
        # 原生轮胎按一遍顺序冲量求解；制动停车的厘米/秒以下漂移进入可被碰撞唤醒的原生休眠。
        self._park_quiet = self._park_quiet + 1 if parking and grounded and motion <= .01 and angular <= .001 else 0
        if self._park_quiet >= 24:
            self._chassis.setActive(False)

    def snapshot(self, *, include_wheels=True, active=True, generation=0, signal=0, hazards=False):
        pose = self._chassis.getTransform()
        position = pose.getPos()
        hpr = pose.getHpr()
        velocity = self._chassis.getLinearVelocity()
        wheels = ()
        if include_wheels:
            poses = []
            for wheel in self._vehicle.getWheels():
                matrix = wheel.getWorldTransform()
                orientation = Quat()
                orientation.setFromMatrix(matrix.getUpper3())
                poses.append(WheelState(tuple(matrix.getRow3(3)), tuple(orientation)))
            wheels = tuple(poses)
        return CarState(tuple(position), hpr.x, velocity.dot(pose.getQuat().getForward()),
            pitch=hpr.y, roll=hpr.z, wheels=wheels, steering=self.steering.angle,
            throttle=self._drive_pedal, brake=self._brake_pedal,
            rpm=self.powertrain.rpm, gear=self.powertrain.gear,
            acceleration=self._acceleration, lateral_acceleration=self._lateral_acceleration,
            surface='asphalt' if self.on_asphalt(position.x, position.y) else 'grass',
            dynamics=self.dynamics, traction_state=self.traction.state, stability_state=self.stability.state,
            active=active, generation=generation, signal=signal, hazards=hazards,
            velocity=tuple(velocity), orientation=tuple(pose.getQuat()))
