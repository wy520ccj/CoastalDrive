"""前轮转向齿条的角度与角速度状态。"""

import math

from vehicle_config import CAR


class SteeringRack:
    def __init__(self):
        self.angle = 0.0
        self.velocity = 0.0

    def advance(self, target_degrees, dt):
        target_degrees = max(-CAR.steering_degrees, min(CAR.steering_degrees, target_degrees))
        omega = CAR.steering_return if abs(target_degrees) < abs(self.angle) else CAR.steering_response
        error = self.angle - target_degrees
        transient = self.velocity + omega * error
        decay = math.exp(-omega * dt)
        next_angle = target_degrees + (error + transient * dt) * decay
        self.velocity = (self.velocity - omega * transient * dt) * decay
        self.velocity = max(-CAR.steering_rate, min(CAR.steering_rate, self.velocity))
        rate = CAR.steering_rate
        self.angle += max(-rate * dt, min(rate * dt, next_angle - self.angle))
        return self.angle
