"""完整轮端推进的数值输入/输出；主世界读取与冲量提交留在调用方。"""

from dataclasses import dataclass
from functools import lru_cache

from panda3d.core import Vec3

from powertrain import Powertrain
from suspension import SuspensionState
from vehicle_suspension import Suspension
from vehicle_tires import Tires


@lru_cache(maxsize=32)
def tire_hardware(config):
    """只复用不变的轮端硬件，转速、胎体、悬架和传动状态仍逐步读取。"""
    template = Tires(config)
    return template.hubs, template.rear_config


class TireBodyInput:
    """单个世界子步的只读刚体输入及有序冲量记录，不积分或创建物理世界。"""

    def __init__(self, pose, velocity, angular, inverse_inertia, angular_damping):
        self.pose = pose
        self.velocity = velocity
        self.angular = angular
        self.inverse_inertia = inverse_inertia
        self.angular_damping = angular_damping
        self.impulses = []

    def getTransform(self):
        return self.pose

    def getLinearVelocity(self):
        return Vec3(*self.velocity)

    def getAngularVelocity(self):
        return Vec3(*self.angular)

    def getInvInertiaTensorWorld(self):
        return self.inverse_inertia

    def getAngularDamping(self):
        return self.angular_damping

    def applyCentralImpulse(self, impulse):
        self.impulses.append(('central',tuple(impulse),None))

    def applyTorqueImpulse(self, impulse):
        self.impulses.append(('torque',tuple(impulse),None))

    def applyImpulse(self, impulse, point):
        self.impulses.append(('point',tuple(impulse),tuple(point)))


@dataclass(frozen=True)
class TireAdvanceResult:
    omega: tuple
    rotation: tuple
    deformation: tuple
    states: tuple
    powertrain: dict
    suspension_state: SuspensionState
    compression: tuple
    contacts: tuple
    impulses: tuple
    normal_geometry: tuple

    def commit(self, chassis, tires, powertrain, suspension):
        """保持原中央/轴/轮端冲量次序和Panda单精度转换，最后发布同一数值末状态。"""
        for kind,impulse,point in self.impulses:
            vector = Vec3(*impulse)
            if kind == 'central':
                chassis.applyCentralImpulse(vector)
            elif kind == 'torque':
                chassis.applyTorqueImpulse(vector)
            else:
                chassis.applyImpulse(vector,Vec3(*point))
        tires.omega = list(self.omega)
        tires.rotation = list(self.rotation)
        tires.deformation = list(self.deformation)
        tires.states = self.states
        powertrain.__dict__.update(self.powertrain)
        suspension.state = self.suspension_state
        suspension.compression = self.compression
        suspension.geometry = self.normal_geometry
        return self.contacts


@dataclass(frozen=True)
class TireAdvanceInput:
    config: object
    body: TireBodyInput
    contacts: tuple
    angles: tuple
    request: tuple
    tick: int
    dt: float
    external_velocity: tuple
    external_angular: tuple
    omega: tuple
    rotation: tuple
    deformation: tuple
    states: tuple
    powertrain: dict
    normal_system: object
    normal_geometry: tuple
    compression: tuple
    previous_force_tick: int
    accumulate: bool
    previous_normal_force: tuple
    wheel_inputs: tuple
    world_source: object

    @classmethod
    def read(cls, chassis, tires, powertrain, suspension, normal_system, contacts, angles, request,
             tick, dt, external_velocity, external_angular, accumulate, world_source=None):
        body = TireBodyInput(chassis.getTransform(),tuple(chassis.getLinearVelocity()),
                             tuple(chassis.getAngularVelocity()),chassis.getInvInertiaTensorWorld(),chassis.getAngularDamping())
        wheels = tuple((wheel.getSuspensionRestLength(),wheel.getSteering()) for wheel in world_source[2]) if world_source else ()
        return cls(tires.config,body,contacts,angles,request,tick,dt,external_velocity,external_angular,
            tuple(tires.omega),tuple(tires.rotation),tuple(tires.deformation),tires.states,
            {name:value for name,value in powertrain.__dict__.items() if name!='config'},
            normal_system,suspension.geometry if normal_system is not None else None,
            suspension.compression,suspension.state.force_tick,accumulate,suspension.state.normal_force,wheels,world_source)

    def solve(self, *, static_geometry=None, surface_material=None):
        """仅一个机械子步；原Tires代码计算完整末状态，记录冲量而不操作Bullet。"""
        tires = Tires.__new__(Tires)
        tires.config = self.config
        tires.hubs,tires.rear_config = tire_hardware(self.config)
        body = TireBodyInput(self.body.pose,self.body.velocity,self.body.angular,self.body.inverse_inertia,self.body.angular_damping)
        tires.omega = list(self.omega)
        tires.rotation = list(self.rotation)
        tires.deformation = list(self.deformation)
        tires.states = self.states
        powertrain = Powertrain.__new__(Powertrain)
        powertrain.config = self.config
        powertrain.__dict__.update(self.powertrain)
        # 数值部分只使用悬架材料/接点/上拍压缩，不创建原生扫掠形状或世界。
        suspension = Suspension.__new__(Suspension)
        suspension.config = self.config
        suspension.hubs = tires.hubs
        suspension.envelope = None
        suspension._support_shapes = None
        suspension._candidate_cache = {}
        suspension.geometry = self.normal_geometry
        suspension.compression = self.compression
        suspension.state = SuspensionState(force_tick=self.previous_force_tick,normal_force=self.previous_normal_force)
        normal_system,contacts = self.normal_system,self.contacts
        if normal_system is None:
            if self.world_source is not None:
                world,chassis,wheels,on_asphalt,shapes,suspension.envelope = self.world_source
            else:
                from physics_workers import StaticQueryBoundary

                world,chassis = StaticQueryBoundary(),body
                wheels = tuple(TireWheelInput(*values) for values in self.wheel_inputs)
                on_asphalt,shapes = surface_material,static_geometry
            normal_system = suspension.prepare(world,chassis,wheels,shapes)
            contacts = suspension.candidates(normal_system,on_asphalt)
        else:
            surfaces = {(point[0],point[1]):contact.surface=='asphalt'
                        for (point,_normal,_alignment,_rest),contact in zip(self.normal_geometry,self.contacts)
                        if point is not None}

            def on_asphalt(x, y):
                return surfaces[x,y]

        drive,drag,pressures = self.request
        contacts = tires.advance(body,contacts,self.angles,drive,drag,pressures,self.tick,self.dt,
            self.external_velocity,self.external_angular,powertrain=powertrain,
            suspension=(suspension,normal_system,on_asphalt),substeps=1,accumulate=self.accumulate)
        return TireAdvanceResult(tuple(tires.omega),tuple(tires.rotation),tuple(tires.deformation),tires.states,
            {name:value for name,value in powertrain.__dict__.items() if name!='config'},
            suspension.state,suspension.compression,contacts,tuple(body.impulses),suspension.geometry)


@dataclass(frozen=True)
class TireWheelInput:
    """原生轮的当拍硬件/转向读数，不推进或重建原生车辆。"""
    rest_length: float
    steering: float

    def getSuspensionRestLength(self):
        return self.rest_length

    def getSteering(self):
        return self.steering
