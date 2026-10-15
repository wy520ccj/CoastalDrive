"""只读有限旋转悬架端口功展开；不以总能量残差倒推来源。"""

import numpy as np


def leading_work(arms, guide, angular, relative_translation, frozen_rate, spring, damper, dt):
    """沿真实原生位置更新路径的前两阶系数，所有输入均为当前子步物理量。"""
    guide_rate=np.cross(angular,guide)
    guide_acceleration=np.cross(angular,guide_rate)
    first=relative_translation@guide+arms@guide_rate-frozen_rate
    second=relative_translation@guide_rate+.5*arms@guide_acceleration
    return {"rate_drift_work":float(dt*np.dot(spring+damper,first)),
            "rotation_leading_work":float(dt*dt*np.dot(spring+2*damper,second))}


def work_terms(source,step,old):
    velocity=step.velocity
    wheel=source.hardware.mechanical.wheel_jacobians@velocity[:10]+source.guide_velocity_bias
    arms=old["centers"]-old["position"]
    guide=old["rotation"][:,2]
    h=source.dt
    spring=step.normal.spring_force
    damper=step.normal.suspension_force-spring
    delta=step.compression-source.compression
    rate=step.suspension_relative_velocity
    spring_defect=float(np.dot(spring,delta-h*velocity[6:10]))
    damper_defect=float(h*np.dot(damper,rate-velocity[6:10]))
    exact=spring_defect+damper_defect
    if abs(exact-step.suspension_geometry_work)>1e-10:
        raise ArithmeticError("悬架几何功与独立两端口分解不一致")
    terms=leading_work(arms,guide,velocity[3:6],wheel-velocity[:3],velocity[6:10],spring,damper,h)
    return {**terms,"spring_port_defect":spring_defect,"damper_port_defect":damper_defect,
        "suspension_expansion_remainder":exact-terms["rate_drift_work"]-terms["rotation_leading_work"],
        "damper_material_heat":float(h*np.dot(damper,rate)),
        "damper_material_heat_identity_error":float(h*np.dot(damper,rate)-step.normal.suspension_damping)}
