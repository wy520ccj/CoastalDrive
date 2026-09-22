"""A presentation-only follow camera with a little lag when the car turns."""

import math

from panda3d.core import Vec3

from simulation import forward


class ChaseCamera:
    def __init__(self):
        self.position = None
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
            self.acceleration = car.acceleration
        dt = min(dt, 0.05)
        angle = (car.heading - self.heading + 180) % 360 - 180
        self.heading += angle * (1 - math.exp(-dt / 0.22))
        self.distance += (distance - self.distance) * (1 - math.exp(-dt / 0.22))
        direction = Vec3(*forward(self.heading))
        desired = position - direction * self.distance + Vec3(0, 0, 4.2)
        self.position += (desired - self.position) * (1 - math.exp(-dt / 0.08))
        look_at = position + direction * 6 + Vec3(0, 0, 0.7)
        target_fov = 68 + 4 * min(abs(car.speed) / 45, 1)
        self.fov += (target_fov - self.fov) * (1 - math.exp(-dt / 0.35))
        self.acceleration += (car.acceleration - self.acceleration) * (1 - math.exp(-dt / 0.15))
        return self.position, look_at
