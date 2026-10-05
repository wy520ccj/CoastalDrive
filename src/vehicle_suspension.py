"""同一Bullet世界中的SI悬架射线、共轭法向冲量与施力阶段观测。"""

from dataclasses import replace

from panda3d.core import Vec3

from suspension import (
    SuspensionInput,
    SuspensionState,
    advance_suspension,
    contact_gradient,
    dot,
    elastic_terms,
)
from suspension_contacts import suspension_rays
from vehicle_state import WheelContactState


class Suspension:
    def __init__(self, config, hubs):
        self.config = config
        self.hubs = hubs
        self.compression = (0.,) * 4
        self.state = SuspensionState()

    def prepare(self, world, chassis, wheels):
        """只读取当拍接点和材料初值；求解期间不向Bullet提交中间冲量。"""
        config = self.config
        pose = chassis.getTransform()
        origin, orientation = pose.getPos(), pose.getQuat()
        direction = orientation.xform(Vec3(0, 0, -1))
        geometry, gradients, contacts, initial = [], [], [], list(self.compression)
        constraint_compression = list(self.compression)
        lengths = tuple(w.getSuspensionRestLength() + config.suspension_travel + config.wheel_radius for w in wheels)
        # 路径描述轮心；向上退一个半径，保留原查询的压缩行程覆盖范围。
        starts = tuple(pose.getMat().xformPoint(Vec3(*hub)) - direction * config.wheel_radius for hub in self.hubs)
        hits = suspension_rays(world, chassis, tuple((start, start + direction * length) for start, length in zip(starts, lengths)), config.wheel_radius)
        for i, (wheel, ray_length, hit) in enumerate(zip(wheels, lengths, hits)):
            rest = wheel.getSuspensionRestLength()
            point = hit.point if hit else None
            normal = hit.normal if hit else None
            alignment = -dot(normal, tuple(direction)) if hit else None
            # 当前路面是固定刚体；保留动态物体碰撞，射线法向模型不承诺移动支撑。
            eligible = hit is not None and hit.node.isStatic() and alignment > .1
            gradient = (0.,) * 6
            if eligible:
                constraint_compression[i] = rest - (ray_length * hit.fraction - config.wheel_radius)
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
        self.geometry = tuple(geometry)
        return SuspensionInput(tuple(initial), tuple(constraint_compression), tuple(gradients),
                               tuple(contacts), tuple(g[2] for g in geometry), config)

    def advance(self, world, chassis, wheels, on_asphalt, tick, dt,
                external_velocity, external_angular):
        """冻结旧机械对照和独立法向试验；正式有限传动走共同末状态。"""
        system = self.prepare(world, chassis, wheels)
        config = self.config
        gradients = system.gradients
        tensor = chassis.getInvInertiaTensorWorld()
        inverse = tuple(tuple((tensor.getCell(a, b) + tensor.getCell(b, a)) / 2
                              for b in range(3)) for a in range(3))
        velocity = tuple(chassis.getLinearVelocity()[a] + external_velocity[a] for a in range(3))
        angular = tuple(chassis.getAngularVelocity()[a] + external_angular[a] for a in range(3))
        responses = tuple(tuple(g[a] / config.mass for a in range(3))
                          + tuple(dot(row, g[3:]) for row in inverse) for g in gradients)
        mobility = tuple(tuple(dot(a, b) for b in responses) for a in gradients)
        speeds = tuple(dot(g, velocity + angular) for g in gradients)
        step = advance_suspension(system.compression, speeds, mobility, system.touching,
                                  config.suspension_spring_rates, config.suspension_compression_damping,
                                  config.suspension_extension_damping, config.suspension_antiroll_rates,
                                  config.suspension_stop_rates, config.suspension_travel, dt,
                                  geometry=system.geometry)
        self.apply_step(chassis, system, step, dt)
        return self.publish(system, system, ((dt, step),), on_asphalt, tick)

    def apply_step(self, chassis, system, step, dt):
        """共同求解收敛后，仅向唯一车身提交本子步真实法向冲量。"""
        gradients = system.gradients
        linear = tuple(dt * sum(g[a] * force for g, force in zip(gradients, step.axial_force)) for a in range(3))
        angular_impulse = tuple(dt * sum(g[a + 3] * force for g, force in zip(gradients, step.axial_force)) for a in range(3))
        chassis.applyCentralImpulse(Vec3(*linear))
        chassis.applyTorqueImpulse(Vec3(*angular_impulse))

    def contacts(self, system, step, on_asphalt):
        states = []
        for i, (point, normal, alignment, rest) in enumerate(self.geometry):
            supported = system.touching[i] and step.axial_force[i] > 0.
            force = step.axial_force[i] / alignment if supported else 0.
            raw = step.raw_axial_force[i] / alignment if supported else 0.
            states.append(WheelContactState(
                supported, point if supported else None, normal if supported else None, raw, force,
                rest - system.geometry[i] if supported else rest - step.compression[i],
                system.geometry[i] if supported else step.compression[i], None,
                ("asphalt" if on_asphalt(point[0], point[1]) else "grass") if supported else None))
        return tuple(states)

    def candidates(self, system, on_asphalt):
        """候选接点只提供坐标；实际轮荷由共同机械方程决定。"""
        return tuple(WheelContactState(
            eligible, point if eligible else None, normal if eligible else None, 0., 0.,
            rest - compression, compression, None,
            ("asphalt" if on_asphalt(point[0], point[1]) else "grass") if eligible else None)
            for (point, normal, _alignment, rest), eligible, compression in
            zip(self.geometry, system.touching, system.geometry))

    def publish(self, initial_system, final_system, substeps, on_asphalt, tick):
        """损耗/功累加全拍，力与接触标签保留最后实际施力子步；子步明细同时保存。"""
        config = self.config
        initial = initial_system.compression
        step = substeps[-1][1]
        losses = ("damping_dissipation", "elastic_numerical_dissipation", "body_numerical_dissipation",
                  "contact_offset_work", "energy_residual", "body_work")
        step = replace(step, **{name: sum(getattr(part, name) for _dt, part in substeps) for name in losses})
        linear = tuple(sum(dt * sum(g[a] * force for g, force in zip(initial_system.gradients, part.axial_force))
                           for dt, part in substeps) for a in range(3))
        angular_impulse = tuple(sum(dt * sum(g[a + 3] * force for g, force in zip(initial_system.gradients, part.axial_force))
                                    for dt, part in substeps) for a in range(3))
        states = self.contacts(final_system, step, on_asphalt)
        loads = tuple(contact.normal_load for contact in states)
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
        self.state = SuspensionState(step, loads, initial_system.alignment, initial_system.touching,
                                     tuple(initial), geometry_work, linear, angular_impulse, tick,
                                     final_system.geometry, initialization_energy, substeps)
        return states

    def wheel_positions(self, chassis, wheels):
        pose = chassis.getTransform()
        direction = pose.getQuat().xform(Vec3(0, 0, -1))
        return tuple(tuple(pose.getMat().xformPoint(Vec3(*hub))
                           + direction * (wheel.getSuspensionRestLength() - compression))
                     for hub, wheel, compression in zip(self.hubs, wheels, self.compression))
