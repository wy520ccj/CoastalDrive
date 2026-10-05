"""同一Bullet世界中的SI悬架射线、共轭法向冲量与施力阶段观测。"""

from panda3d.core import Vec3

from suspension import SuspensionState, advance_suspension, contact_gradient, dot, elastic_terms
from vehicle_state import WheelContactState


class Suspension:
    def __init__(self, config, hubs):
        self.config = config
        self.hubs = hubs
        self.compression = (0.,) * 4
        self.state = SuspensionState()

    def advance(self, world, chassis, wheels, on_asphalt, tick, dt,
                external_velocity, external_angular):
        """在既有轮胎施力前提交一次法向冲量；原生车辆此分支不再叠加弹簧力。"""
        config = self.config
        pose = chassis.getTransform()
        origin, orientation = pose.getPos(), pose.getQuat()
        direction = orientation.xform(Vec3(0, 0, -1))
        tensor = chassis.getInvInertiaTensorWorld()
        inverse = tuple(tuple((tensor.getCell(a, b) + tensor.getCell(b, a)) / 2
                              for b in range(3)) for a in range(3))
        velocity = tuple(chassis.getLinearVelocity()[a] + external_velocity[a] for a in range(3))
        angular = tuple(chassis.getAngularVelocity()[a] + external_angular[a] for a in range(3))
        geometry, gradients, contacts, initial = [], [], [], list(self.compression)
        constraint_compression = list(self.compression)
        for i, (wheel, hub) in enumerate(zip(wheels, self.hubs)):
            start = pose.getMat().xformPoint(Vec3(*hub))
            rest = wheel.getSuspensionRestLength()
            ray_length = rest + config.suspension_travel + config.wheel_radius
            hits = world.rayTestAll(start, start + direction * ray_length).getHits()
            hits = sorted((hit for hit in hits if hit.getNode() != chassis), key=lambda h: h.getHitFraction())
            hit = hits[0] if hits else None
            point = tuple(hit.getHitPos()) if hit else None
            normal = tuple(hit.getHitNormal()) if hit else None
            alignment = -dot(normal, tuple(direction)) if hit else None
            # 当前路面是固定刚体；保留动态物体碰撞，射线法向模型不承诺移动支撑。
            eligible = hit is not None and hit.getNode().isStatic() and alignment > .1
            gradient = (0.,) * 6
            if eligible:
                constraint_compression[i] = rest - (ray_length * hit.getHitFraction() - config.wheel_radius)
                if self.state.force_tick == 0:
                    # 初始姿态可以带真实预压；候选射线中的离地间隙不是弹簧伸长。
                    initial[i] = max(0., constraint_compression[i])
                elif self.state.normal_force[i] > 0.:
                    initial[i] = constraint_compression[i]
                arm = tuple(point[a] - origin[a] for a in range(3))
                gradient = contact_gradient(normal, tuple(direction), arm)
            geometry.append((point, normal, alignment, rest))
            gradients.append(gradient)
            contacts.append(eligible)
        responses = tuple(tuple(g[a] / config.mass for a in range(3))
                          + tuple(dot(row, g[3:]) for row in inverse) for g in gradients)
        mobility = tuple(tuple(dot(a, b) for b in responses) for a in gradients)
        speeds = tuple(dot(g, velocity + angular) for g in gradients)
        step = advance_suspension(tuple(initial), speeds, mobility, tuple(contacts),
                                  config.suspension_spring_rates, config.suspension_compression_damping,
                                  config.suspension_extension_damping, config.suspension_antiroll_rates,
                                  config.suspension_stop_rates, config.suspension_travel, dt,
                                  geometry=tuple(constraint_compression))
        linear = tuple(dt * sum(g[a] * force for g, force in zip(gradients, step.axial_force)) for a in range(3))
        angular_impulse = tuple(dt * sum(g[a + 3] * force for g, force in zip(gradients, step.axial_force)) for a in range(3))
        chassis.applyCentralImpulse(Vec3(*linear))
        chassis.applyTorqueImpulse(Vec3(*angular_impulse))
        loads, states = [], []
        for i, (point, normal, alignment, rest) in enumerate(geometry):
            supported = contacts[i] and step.axial_force[i] > 0.
            force = step.axial_force[i] / alignment if supported else 0.
            raw = step.raw_axial_force[i] / alignment if supported else 0.
            loads.append(force)
            states.append(WheelContactState(
                supported, point if supported else None, normal if supported else None, raw, force,
                rest - constraint_compression[i] if supported else rest - step.compression[i],
                constraint_compression[i] if supported else step.compression[i], None,
                ("asphalt" if on_asphalt(point[0], point[1]) else "grass") if supported else None))
        old_energy = elastic_terms(self.compression, config.suspension_spring_rates,
                                  config.suspension_antiroll_rates, config.suspension_stop_rates,
                                  config.suspension_travel)
        initial_energy = elastic_terms(initial, config.suspension_spring_rates,
                                      config.suspension_antiroll_rates, config.suspension_stop_rates,
                                      config.suspension_travel)
        geometry_work = initial_energy[0] + sum(initial_energy[1]) + initial_energy[2] - old_energy[0] - sum(old_energy[1]) - old_energy[2]
        initialization_energy = initial_energy[0] + sum(initial_energy[1]) + initial_energy[2] if self.state.force_tick == 0 else 0.
        geometry_work -= initialization_energy
        self.compression = step.compression
        self.state = SuspensionState(step, tuple(loads), tuple(g[2] for g in geometry), tuple(contacts),
                                     tuple(initial), geometry_work, linear, angular_impulse, tick,
                                     tuple(constraint_compression), initialization_energy)
        return tuple(states)

    def wheel_positions(self, chassis, wheels):
        pose = chassis.getTransform()
        direction = pose.getQuat().xform(Vec3(0, 0, -1))
        return tuple(tuple(pose.getMat().xformPoint(Vec3(*hub))
                           + direction * (wheel.getSuspensionRestLength() - compression))
                     for hub, wheel, compression in zip(self.hubs, wheels, self.compression))
