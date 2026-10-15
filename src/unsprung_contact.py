"""四个簧下自由度的冻结构型法向块；用于全车共同求解的局部线性化。"""

from dataclasses import dataclass

import numpy as np

from suspension import elastic_terms, stiffness_matrix
from suspension_damper import damper_curve
from suspension_installation import installation_curve


def _elastic_material(compression, config):
    """安装预压与松弛共用同一势能；防倾杆和止挡仍作用在原轮心行程。"""
    rates = config.suspension_spring_rates
    spring,bars,stop,force = elastic_terms(tuple(compression),(0.,)*4 if config.suspension_coil_enabled else rates,
        config.suspension_antiroll_rates,config.suspension_stop_rates,config.suspension_travel)
    force = np.asarray(force)
    tangent = rates
    if config.suspension_coil_enabled:
        rates = np.asarray(rates)
        if config.suspension_installation_curves is None:
            position,ratio,gradient = np.asarray(compression),np.ones(4),np.zeros(4)
        else:
            motions = [installation_curve(rows)[0] for rows in config.suspension_installation_curves]
            values = np.array([axis.at(q) for axis,q in zip(motions,compression,strict=True)])
            reference = np.array([axis.reference_ratio for axis in motions])
            position,ratio,gradient = (values/reference[:,None]).T
        shifted = position+np.asarray(config.suspension_spring_preloads)/rates
        active = np.maximum(shifted,0.)
        spring = .5*np.dot(rates,active**2)
        force += rates*active*ratio
        tangent = np.where(shifted>0.,rates*(ratio**2+active*gradient),0.)
    return spring+sum(bars)+stop,force,tangent


def suspension_potential(compression, config):
    potential,force,_ = _elastic_material(compression,config)
    return potential,force


def suspension_damping(compression, relative_velocity, config):
    """活塞速度与反力均经当前运动比映射，保留力速与热的共轭关系。"""
    coefficient = np.where(relative_velocity>=0.,config.suspension_compression_damping,config.suspension_extension_damping)
    derivative = np.zeros(4)
    if config.suspension_installation_curves is not None:
        axes = [installation_curve(rows)[1] for rows in config.suspension_installation_curves]
        values = np.array([axis.at(q)[1:] for axis,q in zip(axes,compression,strict=True)])
        reference = np.array([axis.reference_ratio for axis in axes])
        ratio,gradient = (values/reference[:,None]).T
        derivative = 2*coefficient*ratio*gradient
        coefficient = coefficient*ratio**2
    return coefficient,derivative


def damping_material(compression, relative_velocity, config):
    """返回轮心阻力、速度导数、行程导数；力速表不产生独立储能。"""
    if config.suspension_damper_curves is None:
        coefficient,gradient=suspension_damping(compression,relative_velocity,config)
        return coefficient*relative_velocity,coefficient,gradient*relative_velocity
    ratio,gradient=np.ones(4),np.zeros(4)
    if config.suspension_installation_curves is not None:
        axes=[installation_curve(rows)[1] for rows in config.suspension_installation_curves]
        values=np.array([axis.at(q)[1:] for axis,q in zip(axes,compression,strict=True)])
        ratio,gradient=(values/np.array([axis.reference_ratio for axis in axes])[:,None]).T
    values=np.array([damper_curve(rows).at(r*u) for rows,r,u in
        zip(config.suspension_damper_curves,ratio,relative_velocity,strict=True)])
    force,slope=values.T
    return ratio*force,ratio**2*slope,gradient*(force+ratio*relative_velocity*slope)


@dataclass(frozen=True)
class NormalMaterial:
    suspension_force: np.ndarray
    normal_force: np.ndarray
    suspension_potential: float
    tire_potential: float
    suspension_damping: float
    tire_damping: float
    suspension_tangent: np.ndarray
    radial_tangent: np.ndarray
    spring_force: np.ndarray


def normal_material(compression, relative_velocity, deflection, previous_deflection,
                    dt, config, radial_rates, radial_damping):
    """法向块与传动/轮胎共同求解共用唯一材料方程。"""
    damper,damper_speed,damper_travel = damping_material(compression,relative_velocity,config)
    potential,spring,spring_tangent = _elastic_material(compression,config)
    delta_rate = (np.maximum(deflection,0.)-np.maximum(previous_deflection,0.))/dt
    trial = radial_rates*np.maximum(deflection,0.)+radial_damping*delta_rate
    contact = (deflection>0.) & (trial>0.)
    normal = np.where(contact,trial,0.)
    hessian = np.asarray(stiffness_matrix(spring_tangent,config.suspension_antiroll_rates))
    hessian += np.diag(np.where(np.abs(compression)>config.suspension_travel,config.suspension_stop_rates,0.))
    return NormalMaterial(spring+damper,normal,float(potential),
        float(.5*np.dot(radial_rates,np.maximum(deflection,0.)**2)),
        float(dt*np.dot(damper,relative_velocity)),
        float(dt*np.dot(np.where(contact,radial_damping,0.),delta_rate**2)),
        dt*hessian+np.diag(damper_speed+dt*damper_travel),
        np.where(contact,dt*radial_rates+radial_damping,0.),spring)


@dataclass(frozen=True)
class UnsprungNormalStep:
    velocity: np.ndarray
    compression: np.ndarray
    tire_deflection: np.ndarray
    suspension_force: np.ndarray
    normal_force: np.ndarray
    generalized_impulse: np.ndarray
    suspension_energy: float
    tire_energy: float
    suspension_damping_loss: float
    tire_damping_loss: float
    elastic_numerical_loss: float
    kinetic_numerical_loss: float
    known_work: float
    road_work: float
    energy_error: float
    impulse_residual: float
    iterations: int


def normal_block(mechanics, velocity, compression, tire_deflection, normals,
                 radial_rates, radial_damping, known_force, road_delta, dt, config):
    """同一十维末速度解弹簧/止挡/非对称阻尼/非负径向力。

    质量、导向和接触法线在本块冻结；真实旋转/接点与惯性偏置由外层联立刷新。
    这里没有创建世界，也不能把本块能量误差当作有限姿态全车积分误差。
    """
    velocity, q0, delta0 = np.asarray(velocity),np.asarray(compression),np.asarray(tire_deflection)
    known, road_delta = np.asarray(known_force),np.asarray(road_delta)
    rates, damping = np.asarray(radial_rates),np.asarray(radial_damping)
    normal_gradient = np.einsum('iaj,ia->ij',mechanics.wheel_jacobians,normals)
    spring_gradient = np.zeros((4,10))
    spring_gradient[:,6:] = np.eye(4)
    mass = mechanics.mass_matrix
    def elastic(q):
        return suspension_potential(q,config)

    def evaluate(end):
        relative = end[6:]
        q = q0+dt*relative
        delta = delta0+road_delta-dt*(normal_gradient@end)
        material = normal_material(q,relative,delta,delta0,dt,config,rates,damping)
        suspension,normal = material.suspension_force,material.normal_force
        residual = mass@(end-velocity)-dt*known+dt*spring_gradient.T@suspension-dt*normal_gradient.T@normal
        jacobian = mass+dt*spring_gradient.T@material.suspension_tangent@spring_gradient
        jacobian += dt*normal_gradient.T@np.diag(material.radial_tangent)@normal_gradient
        return residual,jacobian,q,delta,suspension,normal,material

    end = velocity.copy()
    for iteration in range(20):
        details = evaluate(end)
        residual,jacobian = details[:2]
        error = float(np.max(np.abs(residual)))
        if error<1e-10:
            break
        step = np.linalg.solve(jacobian,residual)
        for attempt in range(12):
            candidate = end-2.**-attempt*step
            if np.linalg.norm(evaluate(candidate)[0])<np.linalg.norm(residual):
                end = candidate
                break
        else:
            raise ArithmeticError(f"簧下法向块线搜索不下降：{error:.9g} N·s")
    else:
        raise ArithmeticError(f"簧下法向块超过20轮：{error:.9g} N·s")
    _residual,_jacobian,q,delta,suspension,normal,material = details
    potential,tire_potential = material.suspension_potential,material.tire_potential
    original_potential,_ = elastic(q0)
    original_tire = .5*np.dot(rates,np.maximum(delta0,0.)**2)
    material_loss,tire_material = material.suspension_damping,material.tire_damping
    elastic_numeric = np.dot(material.spring_force,q-q0)-(potential-original_potential)
    elastic_numeric += np.dot(normal,delta-delta0)-(tire_potential-original_tire)-tire_material
    velocity_delta = end-velocity
    kinetic_numeric = .5*velocity_delta@mass@velocity_delta
    work, road_work = dt*np.dot(end,known),np.dot(normal,road_delta)
    kinetic_delta = .5*(end@mass@end-velocity@mass@velocity)
    energy_error = kinetic_delta+potential-original_potential+tire_potential-original_tire
    energy_error += material_loss+tire_material+elastic_numeric+kinetic_numeric-work-road_work
    impulse = dt*(-spring_gradient.T@suspension+normal_gradient.T@normal)
    return UnsprungNormalStep(end,q,delta,suspension,normal,impulse,potential,float(tire_potential),
                             float(material_loss),float(tire_material),float(elastic_numeric),
                             float(kinetic_numeric),float(work),float(road_work),float(energy_error),error,iteration+1)
