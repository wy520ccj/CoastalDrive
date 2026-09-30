"""读取已完成物理步的轮胎接触诊断，不参与驾驶控制。"""

from dataclasses import replace

from vehicle_state import WheelContactState


def road_support(normal):
    """模型将朝上且坡度不超过60°的单位法线定义为可用路面支撑。"""
    return normal[2] >= 0.5


def read_wheel_contacts(bullet_vehicle, on_asphalt):
    """仅在物理积分后调用；初建和重置后的原生缓存尚未有效。"""
    contacts = []
    for wheel in bullet_vehicle.getWheels():
        ray = wheel.getRaycastInfo()
        touching = ray.isInContact()
        length = float(ray.getSuspensionLength())
        force = float(wheel.getWheelsSuspensionForce()) if touching else 0.0
        point = tuple(ray.getContactPointWs()) if touching else None
        contacts.append(WheelContactState(
            in_contact=touching,
            contact_point=point,
            contact_normal=tuple(ray.getContactNormalWs()) if touching else None,
            suspension_force=force,
            normal_load=min(force, float(wheel.getMaxSuspensionForce())) if touching else 0.0,
            suspension_length=length,
            compression=float(wheel.getSuspensionRestLength()) - length,
            skid=float(wheel.getSkidInfo()) if touching else None,
            surface=("asphalt" if on_asphalt(point[0], point[1]) else "grass")
            if touching else None,
        ))
    return tuple(contacts)


def shift_contacts(contacts, amount):
    """坐标原点重定位只平移有效接触点，保留该物理步的其他量。"""
    return tuple(
        replace(contact, contact_point=(
            contact.contact_point[0], contact.contact_point[1] - amount,
            contact.contact_point[2],
        )) if contact.contact_point is not None else contact
        for contact in contacts
    )
