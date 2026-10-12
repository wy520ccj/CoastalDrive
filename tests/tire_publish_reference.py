"""b26175c原四轮末状态装配；冻结用于检查原生迁移的数值与Panda边界。"""
from types import SimpleNamespace

from panda3d.core import Vec3
from wheel_contact_kernels import wheel_state_update

from rotor_dynamics import cross, dot
from tire_compliance import world_deformation
from tire_properties import tire_grip, tire_stiffness
from vehicle_state import WheelDynamicsState

_EMPTY_WHEEL_STATE = WheelDynamicsState()


class Impulses:
    def __init__(self):
        self.values = []

    def applyImpulse(self, force, point):
        self.values.append(("point", tuple(force), tuple(point)))

    def applyTorqueImpulse(self, torque):
        self.values.append(("torque", tuple(torque), None))


def reference_publish(config, rear_config, frames, steps, previous, rotation, deformation,
                      drives, capacities, losses, end_angular, sub_dt, tick, accumulate, reverse):
    self = SimpleNamespace(states=previous, omega=[0.]*4, rotation=list(rotation),
                           deformation=list(deformation), rear_config=rear_config)
    chassis = Impulses()
    frame_dissipation = list(losses)
    states = [None]*4
    wheel_frames = frames
    order = range(3, -1, -1) if reverse else range(4)
    longitudinal_impulses = [state.longitudinal_impulse if accumulate else 0. for state in self.states]
    lateral_impulses = [state.lateral_impulse if accumulate else 0. for state in self.states]
    brake_angular_impulses = [state.brake_angular_impulse if accumulate else 0. for state in self.states]
    rolling_angular_impulses = [state.rolling_angular_impulse if accumulate else 0. for state in self.states]
    rolling_dissipation = [state.rolling_dissipation if accumulate else 0. for state in self.states]
    material_dissipation = [state.material_dissipation if accumulate else 0. for state in self.states]
    road_dissipation = [state.road_dissipation if accumulate else 0. for state in self.states]
    elastic_numerical_dissipation = [state.elastic_numerical_dissipation if accumulate else 0. for state in self.states]
    gyro_impulses = [list(state.gyro_angular_impulse) if accumulate else [0.] * 3 for state in self.states]
    steering_impulses = [list(state.steering_angular_impulse) if accumulate else [0.] * 3 for state in self.states]
    steering_work = [state.steering_work if accumulate else 0. for state in self.states]
    longitudinal_angular_impulses = [list(state.longitudinal_angular_impulse) if accumulate else [0.] * 3 for state in self.states]
    lateral_angular_impulses = [list(state.lateral_angular_impulse) if accumulate else [0.] * 3 for state in self.states]
    for index in order:
        frame = wheel_frames[index]
        angle, supported, load, mu = frame.steering, frame.supported, frame.load, frame.mu
        tangent, axle, point = frame.tangent, frame.axle, frame.point
        elastic_frame = frame.elastic_frame
        requested_drive, capacity = drives[index], capacities[index]
        if config.tire_compliance or config.wheel_rotor_transport or config.finite_drivetrain:
            step = steps[index]
            if config.tire_compliance or config.wheel_rotor_transport:
                self.deformation[index] = world_deformation(
                    (step.deformation_x, step.deformation_y), elastic_frame)
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
        states[index] = wheel_state_update(_EMPTY_WHEEL_STATE,
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
    return tuple(self.omega), tuple(self.rotation), tuple(self.deformation), tuple(states), tuple(chassis.values)
