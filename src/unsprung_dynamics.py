"""簧上刚体与四个导向轮心的真实平动惯量；供完整机械接入使用。"""

from dataclasses import dataclass

import numpy as np
from mechanical_kernels import cross
from wheel_contact_kernels import ordinary_cross_rows, ordinary_small_norm


def small_norm(vector):
    """二/三维实数组的原点积开方；保留NumPy标量类型和低精度运算。"""
    if vector.dtype!=np.float64:
        return np.linalg.norm(vector)
    return np.float64(ordinary_small_norm(vector))


def ordinary_cross(first,second):
    """三个分量或逐行三维叉积；低精度继续原NumPy的类型/舍入规则。"""
    first,second = np.asarray(first),np.asarray(second)
    if first.dtype!=np.float64 or second.dtype!=np.float64:
        return np.cross(first,second)
    vectors = first.ndim==second.ndim==1
    a,b = first.reshape(-1,3),second.reshape(-1,3)
    count = len(b) if len(a)==1 else len(a)
    result = np.empty((count,3))
    ordinary_cross_rows((a,b),(result,),len(a),len(b))
    return result[0] if vectors else result


def cross_matrix(vector):
    x, y, z = vector
    return np.array(((0.,-z,y),(z,0.,-x),(-y,x,0.)))


def point_inertia(mass, position):
    return mass*(np.dot(position,position)*np.eye(3)-np.outer(position,position))


def native_gyro_impulse(inertia, angular, dt):
    """匹配Bullet隐式body gyro的一次Newton增量；返回角动量冲量，不另推进刚体。"""
    momentum = inertia@angular
    jacobian = inertia+dt*(cross_matrix(angular)@inertia-cross_matrix(momentum))
    return -inertia@np.linalg.solve(jacobian,dt*np.asarray(cross(angular,momentum)))


@dataclass(frozen=True)
class SprungPartition:
    mass: float
    center: tuple
    inertia: tuple
    wheel_masses: tuple
    wheel_arms: tuple


def partition_vehicle(total_mass, locked_inertia, wheel_masses, wheel_centers):
    """整车参考原点为锁止参考CG；惯量含轮端平行轴项，不含额外轴向自旋储能。"""
    masses = np.asarray(wheel_masses,dtype=float)
    centers = np.asarray(wheel_centers,dtype=float)
    inertia = np.asarray(locked_inertia,dtype=float)
    if (masses.shape != (4,) or centers.shape != (4,3) or inertia.shape != (3,3)
            or not np.isfinite(total_mass) or not all(np.isfinite(v).all() for v in (masses,centers,inertia))
            or (masses<=0.).any() or total_mass<=masses.sum()):
        raise ValueError("整车质量须大于四轮有限正簧下质量，轮心与惯量须为完整有限矩阵")
    if not np.allclose(inertia,inertia.T,rtol=0.,atol=1e-12):
        raise ValueError("锁止参考惯量须对称")
    sprung_mass = total_mass-float(masses.sum())
    center = -np.sum(masses[:,None]*centers,axis=0)/sprung_mass
    central = inertia-sum(point_inertia(m,r) for m,r in zip(masses,centers))-point_inertia(sprung_mass,center)
    moments = np.linalg.eigvalsh(central)
    if moments[0]<=0. or moments[-1]>moments[0]+moments[1]+1e-10:
        raise ValueError("分解后的簧上惯量不满足正值/主惯量三角关系，请核对CG和质量定义")
    return SprungPartition(sprung_mass,tuple(center),tuple(tuple(row) for row in central),
                          tuple(masses),tuple(tuple(r-center) for r in centers))


@dataclass(frozen=True)
class UnsprungMechanics:
    mass_matrix: np.ndarray
    inertial_bias: np.ndarray
    wheel_jacobians: np.ndarray
    wheel_arms: np.ndarray
    guides: np.ndarray
    wheel_velocities: np.ndarray
    kinetic_energy: float
    mass_derivative: np.ndarray
    sprung_mass: float
    world_inertia: np.ndarray
    wheel_masses: np.ndarray

    def acceleration(self, generalized_force):
        """只求同一瞬时构型的加速度，调用方负责全车隐式积分/接触约束。"""
        return np.linalg.solve(self.mass_matrix,np.asarray(generalized_force)-self.inertial_bias)

    def wheel_forces(self, forces):
        """四轮外力按同一轮心速度雅可比回传，保留车身力矩和独立行程力。"""
        return np.einsum('iaj,ia->j',self.wheel_jacobians,forces)

    def suspension_forces(self, axial):
        """正轴向力沿导向推轮心；车身相反反力，内部力总平动/角动量为零。"""
        # 力作用于同一导向线上，前六项解析相消；无需先放大再减去浮点反力。
        result = np.zeros(10)
        result[6:] = axial
        return result

    def gravity_forces(self, gravity):
        gravity = np.asarray(gravity)
        result = self.wheel_forces(self.wheel_masses[:,None]*gravity)
        result[:3] += self.sprung_mass*gravity
        return result


def assemble_unsprung(partition, orientation, displacement, guides_local, generalized_velocity):
    """q前六项为簧上CG世界平动/角速度，末四项为轮心相对导向速度。"""
    rotation = np.asarray(orientation)
    displacement = np.asarray(displacement)
    local = np.asarray(guides_local)
    velocity = np.asarray(generalized_velocity)
    if (rotation.shape != (3,3) or displacement.shape != (4,) or local.shape != (4,3)
            or velocity.shape != (10,) or not all(np.isfinite(v).all() for v in (rotation,displacement,local,velocity))
            or not np.allclose(rotation.T@rotation,np.eye(3),rtol=0.,atol=1e-12)
            or not np.isclose(np.linalg.det(rotation),1.,rtol=0.,atol=1e-12)
            or not np.allclose(np.sum(local*local,axis=1),np.ones(4),rtol=0.,atol=1e-12)):
        raise ValueError("轮心构型须为有限SO(3)旋转、单位导向、四行程及十维速度")
    masses = np.asarray(partition.wheel_masses)
    arms = (np.asarray(partition.wheel_arms)+displacement[:,None]*local)@rotation.T
    guides = local@rotation.T
    world_inertia = rotation@np.asarray(partition.inertia)@rotation.T
    matrix, derivative = np.zeros((10,10)),np.zeros((10,10))
    matrix[:3,:3] = partition.mass*np.eye(3)
    matrix[3:6,3:6] = world_inertia
    angular = velocity[3:6]
    angular_skew = cross_matrix(angular)
    derivative[3:6,3:6] = angular_skew@world_inertia-world_inertia@angular_skew
    bias = np.zeros(10)
    bias[3:6] = cross(angular,world_inertia@angular)
    jacobians, wheel_velocities = [],[]
    for i, (mass,arm,guide) in enumerate(zip(masses,arms,guides)):
        jacobian = np.zeros((3,10))
        jacobian[:,:3] = np.eye(3)
        jacobian[:,3:6] = -cross_matrix(arm)
        jacobian[:,6+i] = guide
        arm_rate = cross(angular,arm)+guide*velocity[6+i]
        jacobian_rate = np.zeros((3,10))
        jacobian_rate[:,3:6] = -cross_matrix(arm_rate)
        jacobian_rate[:,6+i] = cross(angular,guide)
        centrifugal = np.asarray(cross(angular,cross(angular,arm)))+2*np.asarray(cross(angular,guide))*velocity[6+i]
        matrix += mass*jacobian.T@jacobian
        derivative += mass*(jacobian_rate.T@jacobian+jacobian.T@jacobian_rate)
        bias += mass*jacobian.T@centrifugal
        jacobians.append(jacobian)
        wheel_velocities.append(jacobian@velocity)
    return UnsprungMechanics(matrix,bias,np.asarray(jacobians),arms,guides,np.asarray(wheel_velocities),
                             float(.5*velocity@matrix@velocity),derivative,partition.mass,world_inertia,masses)
