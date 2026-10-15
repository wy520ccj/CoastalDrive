"""e7f75a8完整悬架准备；冻结用于原生迁移对照。"""
from panda3d.core import BitMask32, Vec3

from suspension import SuspensionInput, contact_gradient, dot
from suspension_contacts import cylinder_suspension_rays, static_support_shapes
from suspension_kinematics import SupportPlane
from vehicle_suspension import Suspension, WorldSurface
from wheel_geometry import mechanical_axis


class ReferenceSuspension(Suspension):
    def prepare(self, world, chassis, wheels, static_shapes=None):
        """读取本子步真实接点、切平面和材料初值；求解期间不提交中间冲量。"""
        config = self.config
        pose = chassis.getTransform()
        origin, orientation = pose.getPos(), pose.getQuat()
        direction = orientation.xform(Vec3(0, 0, -1))
        geometry, gradients, contacts, planes, initial = [], [], [], [], list(self.compression)
        constraint_compression = list(self.compression)
        lengths = tuple(w.getSuspensionRestLength() + config.suspension_travel + config.wheel_radius for w in wheels)
        # 路径描述轮心；向上退一个半径，保留原查询的压缩行程覆盖范围。
        hub_arms = tuple(tuple(orientation.xform(Vec3(*hub))) for hub in self.hubs)
        starts = tuple(tuple(origin[a] + hub[a] - direction[a] * config.wheel_radius for a in range(3))
                       for hub in hub_arms)
        axes = tuple(mechanical_axis(orientation.getRight(), orientation.getForward(), -wheel.getSteering()) for wheel in wheels)
        if static_shapes is None:
            static_shapes = static_support_shapes(world, chassis, BitMask32.bit(0))
        # 世界每子步已读实际变换；仅在同一不可变几何包内复用覆盖盒候选。
        if self._support_shapes is not static_shapes:
            self.clear_queries()
            self._support_shapes = static_shapes
        candidates = self._candidate_cache
        hits = cylinder_suspension_rays(world, chassis,
            tuple((start, tuple(start[a] + direction[a] * length for a in range(3))) for start, length in zip(starts, lengths)), axes,
            config.wheel_radius, config.wheel_width, config.wheel_shoulder_radius, config.wheel_crown_height,
            envelope=self.envelope,static_shapes=static_shapes,candidate_cache=candidates)
        for i, (wheel, ray_length, hit) in enumerate(zip(wheels, lengths, hits)):
            rest = wheel.getSuspensionRestLength()
            point = hit.point if hit else None
            normal = hit.normal if hit else None
            alignment = -dot(normal, tuple(direction)) if hit else None
            # 当前路面是固定刚体；保留动态物体碰撞，射线法向模型不承诺移动支撑。
            eligible = hit is not None and hit.node.isStatic() and alignment > 0.
            gradient = (0.,) * 6
            if eligible:
                constraint_compression[i] = rest - (ray_length * hit.fraction - config.wheel_radius)
                if self.state.force_tick == 0:
                    # 初始姿态可以带真实预压；候选射线中的离地间隙不是弹簧伸长。
                    initial[i] = max(0., constraint_compression[i])
                elif self.state.normal_force[i] > 0.:
                    initial[i] = constraint_compression[i]
                arm = tuple(point[a] - origin[a] for a in range(3))
                gradient = contact_gradient(normal, tuple(direction), arm, minimum_alignment=0.)
            surface = (WorldSurface(half=(), radius=0., axes=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),
                                   offset=tuple(origin), wheel_radius=config.wheel_radius,
                                   reach=rest+config.suspension_travel, width=config.wheel_width,
                                   shoulder=config.wheel_shoulder_radius, wheel_axis=axes[i],
                                   crown=config.wheel_crown_height, world=world, chassis=chassis,
                                   envelope=self.envelope,static_shapes=static_shapes) if eligible else None)
            if eligible:
                # 初始四轮覆盖盒已经从同一世界完成筛选；各轮末姿态沿用该真实候选集合。
                surface.candidates.update(candidates)
            planes.append(SupportPlane(hub_arms[i], tuple(direction),
                                       tuple(normal), rest - constraint_compression[i], surface,
                                       arm) if eligible else None)
            geometry.append((point, normal, alignment, rest))
            gradients.append(gradient)
            contacts.append(eligible)
        self.geometry = tuple(geometry)
        return SuspensionInput(tuple(initial), tuple(constraint_compression), tuple(gradients),
                               tuple(contacts), tuple(g[2] for g in geometry), config, tuple(planes), chassis.getAngularDamping())
