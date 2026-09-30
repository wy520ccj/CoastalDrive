"""驾驶输入的踏板平滑、转向包络与倒车方向辅助。"""

import math

from vehicle_config import CAR
from vehicle_state import VehicleCommand


def approach(value, target, rate, dt):
    return value + max(-rate * dt, min(rate * dt, target - value))


def steering_limit(speed):
    wheelbase = CAR.wheelbase
    safe_angle = math.degrees(
        math.atan(wheelbase * CAR.assisted_lateral_acceleration / (speed * speed + 16))
    )
    return min(CAR.steering_degrees, safe_angle)


class DriverAssist:
    def __init__(self):
        self.throttle = 0.0
        self.brake = 0.0
        self.reverse_wait = 0.0

    def command(self, control, speed, gear, reverse_enabled, dt):
        throttle = control.throttle if control.brake == 0 else 0.0
        rate = CAR.throttle_rise if throttle > self.throttle else CAR.throttle_release
        self.throttle = approach(self.throttle, throttle, rate, dt)
        rate = CAR.brake_rise if control.brake > self.brake else CAR.brake_release
        self.brake = approach(self.brake, control.brake, rate, dt)

        direction = 1 if self.throttle > 0 else 0
        pedal = self.throttle
        brake = self.brake if gear > 0 else 0.0
        if control.brake > 0:
            direction = 0
            if speed > 0.15:
                brake = self.brake
                self.reverse_wait = 0.0
            else:
                self.reverse_wait += dt
                if reverse_enabled and self.reverse_wait >= CAR.reverse_delay:
                    direction = -1
                    pedal = self.brake
                    brake = 0.0
                else:
                    brake = self.brake
        elif control.throttle > 0:
            self.reverse_wait = 0.0
            if speed < -0.15:
                direction = 0
                brake = self.throttle
        else:
            self.reverse_wait = 0.0

        return VehicleCommand(
            steering=control.steering * steering_limit(speed),
            throttle=pedal,
            brake=brake,
            direction=direction,
        )
