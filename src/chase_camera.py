"""仅用于表现的跟车相机；连续目标积分不随绘制间隔改变跟车距离。"""

import math

from panda3d.core import Vec3

from simulation import forward


class ChaseCamera:
    def __init__(self, base_fov=68.0, dynamic_fov=True):
        self.position = None
        self.target_position = None
        self.heading = 0.0
        self.distance = 11.0
        self.base_fov = float(base_fov)
        self.dynamic_fov = bool(dynamic_fov)
        self.fov = self.base_fov
        self.acceleration = 0.0

    def configure(self, *, base_fov=None, dynamic_fov=None):
        if base_fov is not None:
            self.base_fov = float(base_fov)
        if dynamic_fov is not None:
            self.dynamic_fov = bool(dynamic_fov)
        if self.position is None:
            self.fov = self.base_fov

    def update(self, car, distance, dt, *, snap=False, road_grade=0., road_heading=0.):
        position = Vec3(*car.position)
        reset = self.position is None or snap
        if reset:
            self.heading = car.heading
            self.distance = distance
            self.acceleration = car.acceleration
        angle = (car.heading - self.heading + 180) % 360 - 180
        self.heading += angle * (1 - math.exp(-dt / 0.22))
        self.distance += (distance - self.distance) * (1 - math.exp(-dt / 0.22))
        direction = Vec3(*forward(self.heading))
        # 沿道路纵坡取景，悬架俯仰仍完整可见；倒车/横穿时按镜头朝向投影坡度。
        direction.z = math.tan(math.radians(road_grade))*math.cos(math.radians(self.heading-road_heading))
        # 略低的追车位露出后轮下缘，避免车顶和车尾暗部压成悬浮轮廓。
        desired = position - direction * self.distance + Vec3(0, 0, 3.2)
        if reset:
            self.position = Vec3(desired)
            self.target_position = Vec3(desired)
        if dt > 0:
            # 目标在两次真实显示状态间线性移动；精确积分保留原0.08s跟随时间常数。
            response = -math.expm1(-dt / 0.08)
            self.position += ((self.target_position-self.position)*response
                              +(desired-self.target_position)*(1-0.08*response/dt))
        self.target_position = Vec3(desired)
        look_at = position + direction * 6 + Vec3(0, 0, 0.7)
        boost = 4 * min(abs(car.speed) / 45, 1) if self.dynamic_fov else 0.0
        target_fov = self.base_fov + boost
        self.fov += (target_fov - self.fov) * (1 - math.exp(-dt / 0.35))
        self.acceleration += (car.acceleration - self.acceleration) * (1 - math.exp(-dt / 0.15))
        return self.position, look_at

    def shift_origin(self, offset):
        if self.position is not None:
            self.position.y -= offset
            self.target_position.y -= offset
