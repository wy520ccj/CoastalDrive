"""前轮转向齿条的角度与角速度状态。"""

import math

from vehicle_config import CAR


def wheel_angles(center_angle, config=CAR):
    """虚拟前轴中心角转为左、右前轮角；正角右转，后轴中心是共同圆心的基准。"""
    if center_angle == 0:
        return 0.0, 0.0
    radius = config.wheelbase / math.tan(math.radians(center_angle))
    return tuple(math.degrees(math.atan(config.wheelbase / (radius + offset)))
                 for offset in (config.wheel_track_widths[0] / 2, -config.wheel_track_widths[0] / 2))


class SteeringRack:
    def __init__(self, config=CAR):
        self.config = config
        self.angle = 0.0
        self.velocity = 0.0

    def advance(self, target_degrees, dt):
        config = self.config
        target_degrees = max(
            -config.steering_degrees, min(config.steering_degrees, target_degrees)
        )
        omega = (
            config.steering_return
            if abs(target_degrees) < abs(self.angle)
            else config.steering_response
        )
        error = self.angle - target_degrees
        transient = self.velocity + omega * error
        decay = math.exp(-omega * dt)
        next_angle = target_degrees + (error + transient * dt) * decay
        self.velocity = (self.velocity - omega * transient * dt) * decay
        self.velocity = max(-config.steering_rate, min(config.steering_rate, self.velocity))
        rate = config.steering_rate
        self.angle += max(-rate * dt, min(rate * dt, next_angle - self.angle))
        return self.angle
