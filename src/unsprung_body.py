"""簧上主轴刚体与四个原生轮心导向；变换只读真实世界，不保存第二套姿态。"""

from dataclasses import dataclass
from itertools import permutations

import numpy as np
from panda3d.bullet import BulletGenericConstraint, BulletRigidBodyNode, BulletSphereShape
from panda3d.core import BitMask32, Mat3, Quat, TransformState, Vec3

from vehicle_collision import chassis_shapes


def rigid_transform(rotation, position=(0.,0.,0.)):
    """列向量物理矩阵转换为Panda行向量约定，只在原生边界变成单精度。"""
    quaternion = Quat()
    quaternion.setFromMatrix(Mat3(*np.asarray(rotation).T.ravel()))
    # matrix定义会被Panda全局缓存按almost_equal合并，不能用于变化的物理连接点。
    return TransformState.makePosQuatScale(Vec3(*position),quaternion,Vec3(1))


def rigid_matrix_pose(matrix):
    """纯刚体矩阵转成显式位置/四元数，保持原生边界精度与独立复算。"""
    quaternion = Quat()
    quaternion.setFromMatrix(Mat3(*(matrix.getCell(a,b) for a in range(3) for b in range(3))))
    return TransformState.makePosQuatScale(matrix.getRow3(3),quaternion,Vec3(1))


def quaternion_rotation(quaternion):
    w,x,y,z = np.asarray(tuple(quaternion))/np.linalg.norm(tuple(quaternion))
    return np.array(((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
                     (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
                     (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y))))


@dataclass(frozen=True)
class SprungBodyFrame:
    partition: object
    principal_axes: np.ndarray
    principal_inertia: np.ndarray

    @classmethod
    def from_partition(cls, partition):
        moments,axes = np.linalg.eigh(partition.inertia)
        order = max(permutations(range(3)),key=lambda p:sum(abs(axes[i,p[i]]) for i in range(3)))
        axes,moments = axes[:,order].copy(),moments[list(order)]
        for i in range(3):
            if axes[i,i]<0.:
                axes[:,i] *= -1.
        if np.linalg.det(axes)<0.:
            axes[:,int(np.argmin(np.abs(np.diag(axes))))] *= -1.
        return cls(partition,axes,moments)

    def body_point(self, reference_point):
        return self.principal_axes.T@(np.asarray(reference_point)-self.partition.center)

    def body_vector(self, reference_vector):
        return self.principal_axes.T@reference_vector

    def physical_pose(self, reference_pose):
        return rigid_matrix_pose(rigid_transform(self.principal_axes,self.partition.center).getMat()*reference_pose.getMat())

    def reference_pose(self, body):
        mapping = rigid_transform(self.principal_axes.T,-self.principal_axes.T@self.partition.center)
        return rigid_matrix_pose(mapping.getMat()*body.getTransform().getMat())

    def sprung_pose(self, body):
        return rigid_matrix_pose(rigid_transform(self.principal_axes.T).getMat()*body.getTransform().getMat())

    def read(self, body):
        """精确静态基变换与原生实时CG，供力学数组使用，不依赖场景显示节点。"""
        pose = body.getTransform()
        rotation = quaternion_rotation(pose.getQuat())@self.principal_axes.T
        return np.asarray(tuple(pose.getPos())),rotation

    def install(self, body, config, reference_pose):
        """创建时安装真实簧上质量/主惯量；保持原碰撞形状完整世界外廓。"""
        if body.getNumShapes()!=0:
            raise ValueError("簧上主轴安装须使用尚未安装形状的新刚体")
        body.setMass(self.partition.mass)
        mapping = rigid_transform(self.principal_axes.T,-self.principal_axes.T@self.partition.center)
        for shape,transform in chassis_shapes(config):
            body.addShape(shape,rigid_matrix_pose(transform.getMat()*mapping.getMat()))
        # 原生增添形状会重算惯量，最后才写入分解后的三主惯量。
        body.setInertia(Vec3(*self.principal_inertia))
        body.setTransform(self.physical_pose(reference_pose))


class NativeWheelGuides:
    """同一Bullet世界中的四个轮心点质量；只持有原生对象及固定几何。"""

    def __init__(self, world, body, frame, displacement=(0.,)*4):
        self.world,self.body,self.frame = world,body,frame
        self.points,self.constraints = [],[]
        self._attached = True
        position,rotation = frame.read(body)
        for i,(mass,arm,offset) in enumerate(zip(frame.partition.wheel_masses,frame.partition.wheel_arms,displacement)):
            point = BulletRigidBodyNode(f"{body.getName()}-wheel-center-{i}")
            # 零半径球是点质量的原生表示；轮胎表面由已有有限胎面接触模型处理。
            shape = BulletSphereShape(0.)
            shape.setMargin(0.)
            point.addShape(shape)
            point.setMass(mass)
            point.setAngularFactor(Vec3(0,0,0))
            point.setDeactivationEnabled(False)
            point.setIntoCollideMask(BitMask32.bit(1))
            arm_world = rotation@(np.asarray(arm)+np.array((0.,0.,offset)))
            point.setTransform(TransformState.makePos(Vec3(*(position+arm_world))))
            point.setLinearVelocity(body.getLinearVelocity()+body.getAngularVelocity().cross(Vec3(*arm_world)))
            world.attachRigidBody(point)
            anchor = rigid_transform(frame.principal_axes.T,
                                     frame.principal_axes.T@(np.asarray(arm)+np.array((0.,0.,offset))))
            guide = BulletGenericConstraint(body,point,anchor,TransformState.makeIdentity(),True)
            guide.setLinearLimit(0,0.,0.)
            guide.setLinearLimit(1,0.,0.)
            guide.setLinearLimit(2,1.,-1.)
            # Bullet旧6DOF在零位置误差时不生成限位行；零目标速度保证首拍也锁止。
            # 无限容量表示理想导向的双边反力，并非新增可调执行器或悬架力。
            motor = guide.getTranslationalLimitMotor()
            motor.setTargetVelocity(Vec3(0,0,0))
            motor.setMaxMotorForce(Vec3(float("inf"),float("inf"),0))
            motor.setMotorEnabled(0,True)
            motor.setMotorEnabled(1,True)
            for axis in range(3):
                guide.setAngularLimit(axis,1.,-1.)
            # 只排除同一车辆内部的父体/轮心重叠，不关闭道路/其他车辆碰撞。
            world.attachConstraint(guide,True)
            self.points.append(point)
            self.constraints.append(guide)

    def refresh_frames(self):
        """导向原点沿自由轴滑到实际轮心；横向约束线不变，反力矩使用真实力臂。"""
        _centers,_speeds,displacement,_relative,_transverse = self.read()
        for constraint,arm,offset in zip(self.constraints,self.frame.partition.wheel_arms,displacement):
            local = np.asarray(arm)+np.array((0.,0.,offset))
            anchor = rigid_transform(self.frame.principal_axes.T,self.frame.principal_axes.T@local)
            constraint.setFrames(anchor,TransformState.makeIdentity())

    def read(self):
        position,rotation = self.frame.read(self.body)
        velocity,angular = np.asarray(tuple(self.body.getLinearVelocity())),np.asarray(tuple(self.body.getAngularVelocity()))
        centers = np.asarray([tuple(point.getTransform().getPos()) for point in self.points])
        speeds = np.asarray([tuple(point.getLinearVelocity()) for point in self.points])
        arms = centers-position
        local = arms@rotation
        displacement = local[:,2]-np.asarray(self.frame.partition.wheel_arms)[:,2]
        relative = (speeds-velocity-np.cross(angular,arms))@rotation[:,2]
        transverse = local[:,:2]-np.asarray(self.frame.partition.wheel_arms)[:,:2]
        return centers,speeds,displacement,relative,transverse

    def close(self):
        self.detach()
        self.constraints.clear()
        self.points.clear()

    def detach(self):
        if not self._attached:
            return
        for constraint in self.constraints:
            self.world.removeConstraint(constraint)
        for point in self.points:
            self.world.removeRigidBody(point)
        self._attached = False

    def attach(self):
        if self._attached:
            return
        for point in self.points:
            self.world.attachRigidBody(point)
        for constraint in self.constraints:
            self.world.attachConstraint(constraint,True)
        self._attached = True


def apply_joint_forces(body, wheel_guides, hardware, contacts, step, engine_torque, engine_drag,
                       old_downstream_omega, steering_torque, dt, config):
    """只提交物理轮端/悬架/转子冲量；导向与刚体gyro交给同一原生世界。"""
    wheel_guides.refresh_frames()
    force = (step.forces[:,0,None]*contacts.longitudinal[:,:3]+step.forces[:,1,None]*contacts.lateral[:,:3]
             +step.normal.normal_force[:,None]*contacts.normal[:,:3])
    spring = step.normal.suspension_force[:,None]*hardware.mechanical.guides
    for point,impulse in zip(wheel_guides.points,(force-spring)*dt):
        point.applyCentralImpulse(Vec3(*impulse))
    body.applyCentralImpulse(Vec3(*(dt*np.sum(spring,axis=0))))
    ports = np.vstack((hardware.clutch,hardware.gear,hardware.output,hardware.brakes,hardware.differential))
    torque = np.sum(np.cross(hardware.mechanical.wheel_arms,spring),axis=0)
    for rows,values in ((contacts.longitudinal,step.forces[:,0]),(contacts.lateral,step.forces[:,1]),
                        (contacts.normal,step.normal.normal_force)):
        remainder = rows[:,3:6]-np.cross(hardware.mechanical.wheel_arms,rows[:,:3])
        torque += remainder.T@values
    torque += engine_torque*hardware.engine[3:6]-engine_drag*np.dot(hardware.engine,step.velocity)*hardware.engine[3:6]
    torque -= ports[:,3:6].T@step.port_torques
    reaction = hardware.downstream_inertias*(step.downstream_omega-old_downstream_omega)/dt
    torque -= hardware.downstream[:,3:6].T@reaction
    torque -= np.cross(step.velocity[3:6],hardware.spin(step.velocity,config))
    torque += steering_torque
    body.applyTorqueImpulse(Vec3(*(dt*torque)))
