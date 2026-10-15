"""真实轮心车辆的子步准备、共同求解提交与完成步观测。"""

import math
from dataclasses import dataclass, replace

import numpy as np
from panda3d.core import Vec3

from radial_geometry import RadialRoads
from tire_aligning import brush_trail
from tire_compliance import project_deformation, world_deformation
from tire_drivetrain import DrivetrainStep
from tire_properties import tire_grip, tire_stiffness
from unsprung_body import NativeWheelGuides, SprungBodyFrame, apply_joint_forces
from unsprung_contact_geometry import FiniteRadialContact
from unsprung_drivetrain import drivetrain_ports, tire_ports
from unsprung_dynamics import assemble_unsprung, partition_vehicle
from unsprung_geometry import read_unsprung_geometry
from unsprung_joint import solve_unsprung_joint
from unsprung_motion import FiniteSuspensionMotion
from unsprung_state import UnsprungState
from vehicle_config import wheel_hubs
from vehicle_dynamics import aerodynamic_load
from vehicle_state import WheelContactState, WheelDynamicsState
from wheel_geometry import mechanical_axis


def body_partition(config):
    """锁止名义轮心构型固定于车型创建；当前行程不重新分解整车惯量。"""
    centers = np.asarray(wheel_hubs(config))
    centers[:,2] = config.wheel_radius-config.center_of_mass_height
    return partition_vehicle(config.mass,np.diag(config.body_inertia),config.unsprung_masses,centers)


def install_body(chassis, config, pose):
    frame = SprungBodyFrame.from_partition(body_partition(config))
    frame.install(chassis,config,pose)
    return frame


def install_guides(car):
    wheels = car._vehicle.getWheels()
    nominal = np.asarray(car._sprung_frame.partition.wheel_arms)+car._sprung_frame.partition.center
    reference = nominal[:,2]-(np.asarray(car.hubs)[:,2]-np.array([w.getSuspensionRestLength() for w in wheels]))
    car._unsprung_reference = reference
    car._wheel_guides = NativeWheelGuides(car._world,car._chassis,car._sprung_frame,-reference)
    car._unsprung_pending = None
    car._unsprung_observation = None


def read_mechanics(car, angles):
    position,rotation = car._sprung_frame.read(car._chassis)
    centers,speeds,q,u,transverse = car._wheel_guides.read()
    velocity = np.r_[tuple(car._chassis.getLinearVelocity()),tuple(car._chassis.getAngularVelocity()),u,
                     car.powertrain.engine_omega,car.powertrain.shaft_omega,car.tires.omega]
    mechanical = assemble_unsprung(car._sprung_frame.partition,rotation,q,((0.,0.,1.),)*4,velocity[:10])
    axes = np.array([mechanical_axis(rotation[:,0],rotation[:,1],a if i<2 else 0.) for i,a in enumerate((*angles,0.,0.))])
    hardware = drivetrain_ports(mechanical,axes,rotation@car.config.engine_axis,rotation@car.config.input_shaft_axis,
                                np.asarray(car.config.downstream_axes)@rotation.T,car.powertrain.mechanical_ratio,car.config)
    return position,rotation,centers,speeds,q,u,transverse,velocity,hardware


@dataclass(frozen=True)
class UnsprungAdvanceInput:
    config: object
    hardware: object
    contacts: object
    geometry: object
    velocity: np.ndarray
    wheel_velocity: np.ndarray
    downstream: np.ndarray
    compression: np.ndarray
    deformation: np.ndarray
    initial_force: np.ndarray
    known_force: np.ndarray
    friction: np.ndarray
    rolling: np.ndarray
    engine_torque: float
    engine_drag: float
    clutch_capacity: float
    brake_capacity: np.ndarray
    ratio: float
    synchronizing: bool
    steering_torque: np.ndarray
    steering_angular: np.ndarray
    trails: np.ndarray
    angles: tuple
    tick: int
    dt: float
    accumulate: bool
    frame_loss: np.ndarray
    air_velocity: tuple
    air_force: tuple
    finite_contact: object | None = None
    guide_velocity_bias: np.ndarray | None = None
    wheel_known_force: np.ndarray | None = None
    native_body_gyro: bool = False
    body_external_torque: np.ndarray | None = None
    finite_motion: object | None = None

    @classmethod
    def read(cls, car, pressures, angles, tick, dt, accumulate, static_shapes):
        config,body = car.config,car._chassis
        position,rotation,centers,speeds,q,_u,_transverse,v,hardware = read_mechanics(car,angles)
        guide_bias = car._wheel_guides.velocity_bias(dt)
        motion = FiniteSuspensionMotion(position,rotation,centers,q+car._unsprung_reference,
                                        hardware.mechanical,guide_bias,dt)
        roads = RadialRoads(car._world,body,config,static_shapes)
        geometry = roads.query(centers,rotation[:,2],hardware.axes)
        friction = np.array([config.road_friction if hit is None or car.on_asphalt(*hit.point[:2])
                             else config.grass_friction for hit in geometry.hits])
        rolling = np.array([config.rolling_coefficient if hit is None or car.on_asphalt(*hit.point[:2])
                            else config.grass_rolling_coefficient for hit in geometry.hits]) if config.wheel_rolling_resistance else np.zeros(4)
        steer = np.array([-math.radians((angles[i] if i<2 else 0.)-old.steering)/dt*rotation[:,2]
                          for i,old in enumerate(car.tires.states)])
        trails,local_deformation,frame_loss = [],[],[]
        for i,old in enumerate(car.tires.states):
            load = old.normal_load if old.road_support and geometry.hits[i] is not None else 0.
            tire = config if i<2 else car.tires.rear_config
            cx,cy = tire_stiffness(load,tire)
            trails.append(brush_trail(config.tire_contact_half_length,
                0. if old.force_patch_kappa is None else old.force_patch_kappa,
                0. if old.force_patch_alpha is None else old.force_patch_alpha,
                tire_grip(load,friction[i],tire),cx,cy,old.longitudinal_speed,config.static_contact_speed)
                if config.tire_aligning_enabled else 0.)
            basis = tuple(map(tuple,(geometry.tangents[i],geometry.laterals[i],geometry.normals[i])))
            projected,loss = project_deformation(car.tires.deformation[i],basis,config.tire_contact_stiffness)
            local_deformation.append(projected)
            frame_loss.append(loss)
        contacts = tire_ports(hardware,geometry.offsets,geometry.tangents,geometry.laterals,geometry.normals,steer,trails,
                              normal_offsets=geometry.normal_offsets,wheel_velocity_bias=guide_bias)
        old_axes = np.array([mechanical_axis(rotation[:,0],rotation[:,1],old.steering) for old in car.tires.states])
        finite = FiniteRadialContact(roads,hardware,centers,rotation,old_axes,car.tires.deformation,
                                    steer,np.asarray(trails),dt,config,car.on_asphalt,guide_bias,motion)
        steering_torque = config.wheel_inertia*np.asarray(car.tires.omega)[:,None]*np.cross(steer,hardware.axes)
        air_velocity,air_force = aerodynamic_load(tuple(body.getLinearVelocity()),tuple(car.wind),config)
        body.applyCentralForce(Vec3(*air_force))
        mechanical = hardware.mechanical
        # 原生冻结导向已通过旧实际轮心动量和本步约束行承接几何惯性；不再叠加连续J点偏置。
        wheel_known = np.asarray([tuple(p.getTotalForce()) for p in car._wheel_guides.points])
        wheel_known += mechanical.wheel_masses[:,None]*np.asarray([tuple(p.getGravity()) for p in car._wheel_guides.points])
        known = np.r_[mechanical.wheel_forces(wheel_known),np.zeros(6)]
        known[:3] += mechanical.sprung_mass*np.asarray(tuple(body.getGravity()))
        known[:3] += np.asarray(tuple(body.getTotalForce()))
        known[3:6] += np.asarray(tuple(body.getTotalTorque()))+np.sum(steering_torque,axis=0)
        capacities = np.array([config.brake_torque*(config.front_brake_share if i<2 else 1-config.front_brake_share)/2*p
                               for i,p in enumerate(pressures)])
        return cls(config,hardware,contacts,geometry,v,speeds,np.asarray(car.powertrain.downstream_omega),
            q+car._unsprung_reference,np.asarray(local_deformation),np.array([(s.fx,s.fy) for s in car.tires.states]),
            known,friction,rolling,car.powertrain.engine_torque_request,car.powertrain.engine_drag_coefficient,
            car.powertrain.capacity,capacities,car.powertrain.mechanical_ratio,car.powertrain.synchronizing,
            steering_torque,steer,np.asarray(trails),tuple(angles),tick,dt,accumulate,np.asarray(frame_loss),
            air_velocity,air_force,finite,guide_bias,wheel_known,True,np.asarray(tuple(body.getTotalTorque())),motion)

    def solve(self, *, query_lock=None):
        """纯数值子步；真实世界查询已在read阶段完成。"""
        eligible = np.array([hit is not None for hit in self.geometry.hits]) if self.finite_contact is None else np.ones(4)
        deflection = self.geometry.deflection if self.finite_contact is None else self.finite_contact.initial.deflection
        return solve_unsprung_joint(self.hardware,self.contacts,self.velocity,self.downstream,self.compression,
            deflection,self.deformation,self.initial_force,self.known_force,np.zeros(4),
            np.asarray(self.config.tire_radial_stiffness)*eligible,np.asarray(self.config.tire_radial_damping)*eligible,self.friction,self.rolling,
            self.engine_torque,self.engine_drag,self.clutch_capacity,self.brake_capacity,self.ratio,self.synchronizing,
            self.dt,self.config,wheel_initial_velocity=self.wheel_velocity,finite_contact=self.finite_contact,
            wheel_velocity_bias=self.guide_velocity_bias,wheel_known_force=self.wheel_known_force,
            native_body_gyro=self.native_body_gyro,body_external_torque=self.body_external_torque,finite_motion=self.finite_motion)

    def resolved_source(self, result):
        source = self
        if result.contact_geometry is not None:
            contact = result.contact_geometry
            source = replace(self,contacts=contact.contacts,geometry=contact.geometry,deformation=contact.deformation,
                             frame_loss=contact.frame_loss,friction=contact.friction,rolling=contact.rolling)
        return source

    def commit(self, car, result):
        source = self.resolved_source(result)
        apply_joint_forces(car._chassis,car._wheel_guides,source.hardware,source.contacts,result,
            source.engine_torque,source.engine_drag,source.downstream,np.sum(source.steering_torque,axis=0),source.dt,source.config)
        car.powertrain.accept_step(powertrain_result(source,result),source.dt)
        publish_tires(car,source,result)
        car._unsprung_pending = source,result
        car._wheel_contacts = wheel_contacts(car,source.geometry,result.normal.normal_force,result.compression,result.normal.suspension_force)


def powertrain_result(source, step):
    """把同一解的有限端口账交给既有执行器；不再次推进任何轴。"""
    g,z,h = source.hardware,step.velocity,source.dt
    speeds = np.vstack((g.clutch,g.gear,g.output,g.brakes,g.differential))@z
    tc,tg,loss = step.port_torques[:3]
    differential = step.port_torques[7:]
    down_torque = g.downstream_inertias*(step.downstream_omega-source.downstream)/h
    down_wheels = -g.downstream[:,12:].T@down_torque
    down_spin = np.sum((g.downstream_inertias*step.downstream_omega)[:,None]*g.downstream_axes,axis=0)
    engine_body = (-source.engine_torque+source.engine_drag*np.dot(g.engine,z)+tc)*g.engine_axis
    engine_body -= np.cross(z[3:6],source.config.engine_inertia*z[10]*g.engine_axis)
    shaft_body = (-tc+tg)*g.shaft_axis-np.cross(z[3:6],source.config.input_shaft_inertia*z[11]*g.shaft_axis)
    return DrivetrainStep(wheels=step.wheels,velocity=tuple(z[:3]),angular=tuple(z[3:6]),engine_omega=z[10],
        engine_relative_omega=np.dot(g.engine,z),drive_torque=step.drive_torque,clutch_torque=tc,clutch_slip=speeds[0],
        gear_loss_torque=loss,gear_input_speed=speeds[2],engine_body_torque=tuple(engine_body),
        engine_work=step.engine_work,engine_drag_heat=step.engine_heat,clutch_heat=step.port_heat[0],
        gear_heat=step.port_heat[2],sweeps=step.iterations,
        wheel_drive_torques=tuple(step.drive_torque*np.asarray(source.config.drive_weights)-g.differential[:,12:].T@differential+down_wheels),
        differential_torques=tuple(differential),differential_slips=tuple(speeds[7:]),differential_heat=tuple(step.port_heat[7:]),
        shaft_omega=z[11],shaft_relative_omega=np.dot(g.shaft,z),gear_reaction=tg,
        synchronizer_slip=speeds[1] if source.synchronizing else 0.,synchronizer_heat=step.port_heat[1] if source.synchronizing else 0.,
        shaft_body_torque=tuple(shaft_body),downstream_omega=tuple(np.where(g.downstream_inertias>0.,step.downstream_omega,0.)),
        downstream_body_torque=tuple(-down_torque@g.downstream_axes-np.cross(z[3:6],down_spin)),
        downstream_wheel_torques=tuple(down_wheels),downstream_kinetic_energy=tuple(.5*g.downstream_inertias*step.downstream_omega**2),
        downstream_numerical_dissipation=tuple(.5*g.downstream_inertias*(step.downstream_omega-source.downstream)**2))


def wheel_contacts(car, geometry, loads, compression, axial_force):
    return tuple(WheelContactState(bool(hit is not None and load>0.),hit.point if hit is not None else None,
        hit.normal if hit is not None else None,float(axial_force[i]),float(load),
        car._vehicle.getWheel(i).getSuspensionRestLength()-float(compression[i]),float(compression[i]),None,
        ("asphalt" if car.on_asphalt(*hit.point[:2]) else "grass") if hit is not None and load>0. else None)
        for i,(hit,load) in enumerate(zip(geometry.hits,loads)))


def publish_tires(car, source, result):
    """施力阶段量与累积冲量来自同一个解，完成步采样在原生推进之后。"""
    states = []
    drive = powertrain_result(source,result).wheel_drive_torques
    for i,(old,wheel) in enumerate(zip(car.tires.states,result.wheels)):
        prior = old if source.accumulate else WheelDynamicsState()
        supported = bool(source.geometry.hits[i] is not None and result.normal.normal_force[i]>0.)
        car.tires.omega[i] = wheel.omega
        car.tires.rotation[i] += wheel.relative_omega*source.dt
        basis = tuple(map(tuple,(source.geometry.tangents[i],source.geometry.laterals[i],source.geometry.normals[i])))
        car.tires.deformation[i] = world_deformation((wheel.deformation_x,wheel.deformation_y),basis)
        axis = source.hardware.axes[i]
        gyro = source.config.wheel_inertia*wheel.omega*np.cross(result.velocity[3:6],axis)
        steering = source.steering_torque[i]
        states.append(WheelDynamicsState(omega=wheel.omega,rotation=car.tires.rotation[i],relative_omega=wheel.relative_omega,
            longitudinal_speed=wheel.vx,lateral_speed=wheel.vy,kappa=wheel.kappa if supported else None,
            alpha=wheel.alpha if supported else None,fx=wheel.fx,fy=wheel.fy,drive_torque=drive[i],
            brake_capacity=source.brake_capacity[i],brake_torque=wheel.brake_torque,normal_load=result.normal.normal_force[i],
            road_support=supported,steering=source.angles[i] if i<2 else 0.,force_contact_tick=source.tick,
            force_residual=result.force_error,force_kappa=wheel.kappa if supported else None,force_alpha=wheel.alpha if supported else None,
            force_mode=wheel.mode,longitudinal_impulse=prior.longitudinal_impulse+source.dt*wheel.fx,
            lateral_impulse=prior.lateral_impulse+source.dt*wheel.fy,brake_angular_impulse=prior.brake_angular_impulse+source.dt*wheel.brake_torque,
            force_grip=result.force_parameters[i,0],force_longitudinal_stiffness=result.force_parameters[i,1],force_lateral_stiffness=result.force_parameters[i,2],
            deformation_x=wheel.deformation_x,deformation_y=wheel.deformation_y,force_patch_kappa=wheel.patch_kappa if supported else None,
            force_patch_alpha=wheel.patch_alpha if supported else None,pneumatic_trail=source.trails[i],aligning_moment=source.trails[i]*wheel.fy,
            aligning_angular_impulse=tuple(np.asarray(prior.aligning_angular_impulse)+source.dt*source.trails[i]*wheel.fy*source.geometry.normals[i]),
            contact_steering_work=prior.contact_steering_work-source.dt*(wheel.fx*source.contacts.steering_velocity[i,0]
                +wheel.fy*source.contacts.steering_velocity[i,1]+result.normal.normal_force[i]*source.contacts.steering_velocity[i,2]),
            steering_lateral_velocity=source.contacts.steering_velocity[i,1],elastic_energy=wheel.elastic_energy,
            material_dissipation=prior.material_dissipation+wheel.material_dissipation,road_dissipation=prior.road_dissipation+wheel.road_dissipation,
            elastic_numerical_dissipation=prior.elastic_numerical_dissipation+wheel.elastic_numerical_dissipation,
            frame_dissipation=prior.frame_dissipation+source.frame_loss[i],deformation_rate_x=wheel.deformation_rate_x,deformation_rate_y=wheel.deformation_rate_y,
            mechanical_axis=tuple(axis),rolling_radius=source.contacts.radii[i],
            gyro_angular_impulse=tuple(np.asarray(prior.gyro_angular_impulse)+source.dt*gyro),
            steering_angular_impulse=tuple(np.asarray(prior.steering_angular_impulse)+source.dt*steering),
            steering_work=prior.steering_work+source.dt*np.dot(steering,result.velocity[3:6]),
            longitudinal_angular_impulse=tuple(np.asarray(prior.longitudinal_angular_impulse)+source.dt*wheel.fx*source.contacts.longitudinal[i,3:6]),
            lateral_angular_impulse=tuple(np.asarray(prior.lateral_angular_impulse)+source.dt*wheel.fy*source.contacts.lateral[i,3:6]),
            rolling_torque=wheel.rolling_torque,rolling_angular_impulse=prior.rolling_angular_impulse+source.dt*wheel.rolling_torque,
            rolling_dissipation=prior.rolling_dissipation+wheel.rolling_dissipation,force_rolling_radius=source.contacts.radii[i]))
    car.tires.states = tuple(states)


def observe_unsprung(car, tick):
    """只读真实车身/轮心与已积分轴速，采样不修改自由度。"""
    angles = tuple(s.steering for s in car.tires.states[:2])
    position,rotation,centers,speeds,q,u,_xy,v,hardware = read_mechanics(car,angles)
    geometry = read_unsprung_geometry(car._world,car._chassis,centers,rotation[:,2],hardware.axes,car.config)
    pending = car._unsprung_pending
    loads = np.array([s.normal_load for s in car.tires.states]) if pending is None else pending[1].normal.normal_force
    axial = np.array([s.suspension_force for s in car._wheel_contacts]) if pending is None and car._wheel_contacts else (
        np.zeros(4) if pending is None else pending[1].normal.suspension_force)
    car._wheel_contacts = wheel_contacts(car,geometry,loads,q+car._unsprung_reference,axial)
    states = []
    for i,old in enumerate(car.tires.states):
        axis,offset = hardware.axes[i],geometry.offsets[i]-old.pneumatic_trail*geometry.tangents[i]
        relative = car.tires.omega[i]+np.dot(v[3:6],axis)
        steer = np.zeros(3) if pending is None else pending[0].steering_angular[i]
        surface = speeds[i]+np.cross(v[3:6]+steer,offset)-relative*np.cross(axis,offset)
        offset_x = geometry.offsets[i]
        surface_x = speeds[i]+np.cross(v[3:6]+steer,offset_x)-relative*np.cross(axis,offset_x)
        radius = np.dot(axis,np.cross(offset_x,geometry.tangents[i]))
        vx = np.dot(surface_x,geometry.tangents[i])+radius*car.tires.omega[i]
        vy = np.dot(surface,geometry.laterals[i])
        supported = car._wheel_contacts[i].in_contact
        mu = car.config.road_friction if car._wheel_contacts[i].surface=="asphalt" else car.config.grass_friction
        states.append(replace(old,relative_omega=relative,longitudinal_speed=vx,lateral_speed=vy,
            kappa=-np.dot(surface_x,geometry.tangents[i])/max(abs(vx),car.config.slip_speed) if supported else None,
            alpha=math.atan2(vy,max(abs(vx),car.config.slip_speed)) if supported else None,
            sample_support=supported,sample_tick=tick,sample_grip=tire_grip(loads[i],mu,car.config) if supported else 0.,
            mechanical_axis=tuple(axis),rolling_radius=radius))
    car.tires.states = tuple(states)
    partition = car._sprung_frame.partition
    masses = np.asarray(partition.wheel_masses)
    center_position = (partition.mass*position+np.sum(masses[:,None]*centers,axis=0))/car.config.mass
    center_velocity = (partition.mass*v[:3]+np.sum(masses[:,None]*speeds,axis=0))/car.config.mass
    native_energy = (.5*partition.mass*np.dot(v[:3],v[:3])+.5*v[3:6]@hardware.mechanical.world_inertia@v[3:6]
                     +.5*np.sum(masses[:,None]*speeds**2))
    car._unsprung_observation = UnsprungState(partition.mass,partition.center,tuple(position),tuple(v[:3]),partition.wheel_masses,
        tuple(map(tuple,centers)),tuple(map(tuple,speeds)),tuple(q),tuple(u),tuple(geometry.deflection),
        tuple(geometry.deflection if pending is None else pending[1].tire_deflection),tuple(loads),
        tuple(center_position),tuple(center_velocity),float(native_energy),
        (0.,)*10 if pending is None else tuple(v[:10]-pending[1].velocity[:10]),tick)
    return car._unsprung_observation


def initialize_rolling(car, speed):
    """仅初始条件：保留实际悬架行程/相对运动，初始化无纵向滑移与实体轴储能。"""
    pose = car.reference_pose()
    _pos,rotation,centers,_speeds,_q,u,_xy,v,hardware = read_mechanics(car,(0.,0.))
    car._chassis.setLinearVelocity(pose.getQuat().getForward()*speed)
    v[:3] = tuple(car._chassis.getLinearVelocity())
    body_position = np.asarray(tuple(car._chassis.getTransform().getPos()))
    point_velocities = v[:3]+np.cross(v[3:6],centers-body_position)+u[:,None]*rotation[:,2]
    for point,velocity in zip(car._wheel_guides.points,point_velocities):
        point.setLinearVelocity(Vec3(*velocity))
    geometry = read_unsprung_geometry(car._world,car._chassis,centers,rotation[:,2],hardware.axes,car.config)
    for i,(axis,offset,tangent) in enumerate(zip(hardware.axes,geometry.offsets,geometry.tangents)):
        radius = np.dot(axis,np.cross(offset,tangent))
        car.tires.omega[i] = np.dot(point_velocities[i]+np.cross(v[3:6],offset),tangent)/radius-np.dot(v[3:6],axis)
    v[12:] = car.tires.omega
    v[11] = np.dot(hardware.output,v)+np.dot(hardware.shaft_axis,v[3:6])
    car.powertrain.shaft_omega = v[11]
    down = np.where(hardware.downstream_inertias>0.,hardware.downstream@v,0.)
    car.powertrain.downstream_omega = tuple(down)
    car.powertrain.downstream_kinetic_energy = tuple(.5*hardware.downstream_inertias*down**2)
    car.powertrain.observe(car._chassis,orientation=pose.getQuat())
    car._unsprung_pending = None
    observe_unsprung(car,car._contact_tick)
