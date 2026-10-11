"""仅用于表现的跟车相机；连续目标积分不随绘制间隔改变跟车距离。"""

import math

from panda3d.core import Vec3

from simulation import forward


class ChaseCamera:
    def __init__(self):
        self.position = None
        self.target_position = None
        self.heading = 0.0
        self.distance = 11.0
        self.fov = 68.0
        self.acceleration = 0.0

    def update(self, car, distance, dt, *, snap=False):
        position = Vec3(*car.position)
        if self.position is None or snap:
            self.heading = car.heading
            self.distance = distance
            self.position = position - Vec3(*forward(self.heading)) * distance + Vec3(0, 0, 4.2)
            self.target_position = Vec3(self.position)
            self.acceleration = car.acceleration
        angle = (car.heading - self.heading + 180) % 360 - 180
        self.heading += angle * (1 - math.exp(-dt / 0.22))
        self.distance += (distance - self.distance) * (1 - math.exp(-dt / 0.22))
        direction = Vec3(*forward(self.heading))
        desired = position - direction * self.distance + Vec3(0, 0, 4.2)
        if dt > 0:
            # 目标在两次真实显示状态间线性移动；精确积分保留原0.08s跟随时间常数。
            response = -math.expm1(-dt / 0.08)
            self.position += ((self.target_position-self.position)*response
                              +(desired-self.target_position)*(1-0.08*response/dt))
        self.target_position = Vec3(desired)
        look_at = position + direction * 6 + Vec3(0, 0, 0.7)
        target_fov = 68 + 4 * min(abs(car.speed) / 45, 1)
        self.fov += (target_fov - self.fov) * (1 - math.exp(-dt / 0.35))
        self.acceleration += (car.acceleration - self.acceleration) * (1 - math.exp(-dt / 0.15))
        return self.position, look_at

    def shift_origin(self, offset):
        if self.position is not None:
            self.position.y -= offset
            self.target_position.y -= offset
