"""A single Bullet vehicle, detached from world and traffic management."""

import math

from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode, BulletVehicle, ZUp
from panda3d.core import BitMask32, TransformState, Vec3

from vehicle_config import CAR, WHEEL_HUBS
from vehicle_dynamics import DynamicsState, aerodynamic_force, axle_loads
from vehicle_response import VehicleResponse
from vehicle_state import FIXED_DT, CarState, Control, WheelState, forward


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
    ):
        self._world = world
        self.on_asphalt = on_asphalt
        self.spawn = tuple(spawn)
        self.wind = Vec3(*wind)
        self.reverse_enabled = reverse_enabled
        self.name = name
        self._chassis = None
        self._vehicle = None
        self.closed = False
        self._reverse_wait = 0.0
        self.response = VehicleResponse()
        self._drive_pedal = 0.0
        self._brake_pedal = 0.0
        self._acceleration = 0.0
        self._lateral_acceleration = 0.0
        self._load_acceleration = 0.0
        self.dynamics = DynamicsState()
        self._build_physics(heading, pitch)

    def _build_physics(self, heading, pitch):
        chassis = BulletRigidBodyNode(self.name)
        chassis.setIntoCollideMask(BitMask32.bit(1))
        chassis.setMass(CAR.mass)
        chassis.setDeactivationEnabled(False)
        chassis.setAngularDamping(0.2)
        chassis.addShape(
            BulletBoxShape(Vec3(0.78, 2.05, 0.42)), TransformState.makePos(Vec3(0, 0, 0.42))
        )
        chassis.setTransform(TransformState.makePosHpr(Vec3(*self.spawn), Vec3(heading, pitch, 0)))
        chassis.setCcdMotionThreshold(0.5)
        chassis.setCcdSweptSphereRadius(0.35)
        self._world.attachRigidBody(chassis)

        vehicle = BulletVehicle(self._world, chassis)
        vehicle.setCoordinateSystem(ZUp)
        self._world.attachVehicle(vehicle)
        for x, y, z in WHEEL_HUBS:
            wheel = vehicle.createWheel()
            wheel.setChassisConnectionPointCs(Vec3(x, y, z))
            wheel.setWheelDirectionCs(Vec3(0, 0, -1))
            wheel.setWheelAxleCs(Vec3(1, 0, 0))
            wheel.setWheelRadius(CAR.wheel_radius)
            wheel.setFrontWheel(y > 0)
            wheel.setMaxSuspensionTravelCm(20)
            wheel.setSuspensionStiffness(CAR.suspension_stiffness)
            wheel.setWheelsDampingRelaxation(CAR.suspension_relaxation)
            wheel.setWheelsDampingCompression(CAR.suspension_compression)
            wheel.setFrictionSlip(CAR.road_grip)
            wheel.setRollInfluence(0.1)

        self._chassis = chassis
        self._vehicle = vehicle
        self._initialize_wheel_poses()

    def _initialize_wheel_poses(self):
        pose = self._chassis.getTransform()
        for wheel, hub in zip(self._vehicle.getWheels(), WHEEL_HUBS):
            position = pose.getMat().xformPoint(Vec3(*hub) - Vec3(0, 0, 0.4))
            wheel.setWorldTransform(TransformState.makePosHpr(position, pose.getHpr()).getMat())

    def reset(self, position, heading=0, pitch=0):
        self._chassis.setTransform(
            TransformState.makePosHpr(Vec3(*position), Vec3(heading, pitch, 0))
        )
        self._chassis.setLinearVelocity(Vec3(0, 0, 0))
        self._chassis.setAngularVelocity(Vec3(0, 0, 0))
        self._chassis.clearForces()
        self._chassis.setActive(True)
        self._vehicle.resetSuspension()
        self._reverse_wait = 0.0
        self.response = VehicleResponse()
        self._drive_pedal = 0.0
        self._brake_pedal = 0.0
        self._acceleration = 0.0
        self._lateral_acceleration = 0.0
        self._load_acceleration = 0.0
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

    def apply_control(self, control: Control):
        speed = self.signed_speed()
        response = self.response
        response.pedals_and_steering(control, speed, FIXED_DT)
        for wheel_index in (0, 1):
            self._vehicle.setSteeringValue(-response.steering, wheel_index)

        direction = 1 if response.throttle > 0 else 0
        pedal = response.throttle
        brake = response.brake if response.gear > 0 else 0.0
        if control.brake > 0:
            direction = 0
            if speed > 0.15:
                brake = response.brake
                self._reverse_wait = 0.0
            else:
                self._reverse_wait += FIXED_DT
                if self.reverse_enabled and self._reverse_wait >= CAR.reverse_delay:
                    direction = -1
                    pedal = response.brake
                    brake = 0.0
                else:
                    brake = response.brake
        elif control.throttle > 0:
            self._reverse_wait = 0.0
            if speed < -0.15:
                direction = 0
                brake = response.throttle
        else:
            self._reverse_wait = 0.0

        self._drive_pedal = pedal if direction != 0 and brake == 0 else 0.0
        self._brake_pedal = brake
        engine_force, engine_drag = response.drivetrain(
            speed, pedal, direction, brake > 0, FIXED_DT
        )
        pose = self._chassis.getTransform()
        position = pose.getPos()
        road = self.on_asphalt(position.x, position.y)
        front_load, rear_load = axle_loads(self._load_acceleration, pose.getHpr().y)
        traction_limited = False
        for index, wheel in enumerate(self._vehicle.getWheels()):
            contact = wheel.getRaycastInfo()
            point = contact.getContactPointWs()
            wheel_road = self.on_asphalt(point.x, point.y)
            wheel.setFrictionSlip(CAR.road_grip if wheel_road else CAR.grass_grip)
            mu = CAR.road_friction if wheel_road else CAR.grass_friction
            load = (front_load if index < 2 else rear_load) / 2 if contact.isInContact() else 0
            requested = engine_force / 2 if index >= 2 else 0
            applied = max(-mu * load, min(mu * load, requested))
            traction_limited |= abs(applied - requested) > 1
            self._vehicle.applyEngineForce(applied, index)
            share = CAR.front_brake_share if index < 2 else 1 - CAR.front_brake_share
            braking_force = min(CAR.brake_torque * share / 2 / CAR.wheel_radius, mu * load)
            self._vehicle.setBrake(braking_force * brake * FIXED_DT, index)
        velocity = self._chassis.getLinearVelocity()
        horizontal = Vec3(velocity.x, velocity.y, 0)
        air_velocity = horizontal - self.wind
        air_speed = air_velocity.length()
        aero = aerodynamic_force(air_speed)
        if air_speed > 0.01:
            self._chassis.applyCentralForce(-air_velocity * (aero / air_speed))
        rolling = 0.0
        if horizontal.length() > 0.01 and any(
            w.getRaycastInfo().isInContact() for w in self._vehicle.getWheels()
        ):
            coefficient = CAR.rolling_coefficient if road else CAR.grass_rolling_coefficient
            rolling = coefficient * (front_load + rear_load) * min(horizontal.length(), 1)
            self._chassis.applyCentralForce(-horizontal * (rolling / horizontal.length()))
            self._chassis.applyCentralForce(
                -Vec3(*forward(pose.getHpr().x)) * math.copysign(engine_drag, speed)
            )
        local = pose.getQuat().conjugate().xform(velocity)
        sideslip = math.degrees(math.atan2(local.x, abs(local.y))) if horizontal.length() > 1 else 0
        self.dynamics = DynamicsState(
            aero,
            rolling,
            CAR.mass * 9.81 * math.sin(math.radians(pose.getHpr().y)),
            front_load,
            rear_load,
            self._chassis.getAngularVelocity().z,
            sideslip,
            traction_limited,
        )

    def after_step(self, previous_velocity):
        velocity = self._chassis.getLinearVelocity()
        acceleration = (velocity - Vec3(previous_velocity)) / FIXED_DT
        axes = self._chassis.getTransform().getQuat()
        self._acceleration = acceleration.dot(axes.getForward())
        self._lateral_acceleration = acceleration.dot(axes.getRight())
        self._load_acceleration += (
            max(-12, min(12, self._acceleration)) - self._load_acceleration
        ) * (1 - math.exp(-FIXED_DT / 0.15))

    def snapshot(self):
        transform = self._chassis.getTransform()
        position = transform.getPos()
        wheels = []
        for wheel in self._vehicle.getWheels():
            pose = TransformState.makeMat(wheel.getWorldTransform())
            wheels.append(WheelState(tuple(pose.getPos()), tuple(pose.getQuat())))
        return CarState(
            (float(position.x), float(position.y), float(position.z)),
            float(transform.getHpr().x),
            float(self.signed_speed()),
            float(transform.getHpr().y),
            float(transform.getHpr().z),
            tuple(wheels),
            "asphalt" if self.on_asphalt(position.x, position.y) else "grass",
            self.response.steering,
            self._drive_pedal,
            self._brake_pedal,
            self.response.rpm,
            self.response.gear,
            self._acceleration,
            self._lateral_acceleration,
            self.dynamics,
            velocity=tuple(self._chassis.getLinearVelocity()),
        )

    def close(self):
        if self.closed:
            return
        self._world.removeVehicle(self._vehicle)
        self._vehicle = None
        self._chassis = None
        self.closed = True
