"""驾驶输入的踏板平滑、转向包络与倒车方向辅助。"""

import math
from dataclasses import dataclass

from vehicle_config import CAR
from vehicle_state import VehicleCommand


@dataclass(frozen=True)
class InputConfig:
    progressive_pedals: bool = True
    speed_sensitive_steering: bool = True
    automatic_reverse: bool = True
    throttle_rise: float = 1.6
    throttle_release: float = 5.0
    brake_rise: float = 6.0
    brake_release: float = 10.0
    assisted_lateral_acceleration: float = 7.5
    reverse_delay: float = .4


GAME_INPUT = InputConfig()
SIMULATION_INPUT = InputConfig(
    progressive_pedals=False, speed_sensitive_steering=False, automatic_reverse=False
)


def approach(value, target, rate, dt):
    return value + max(-rate * dt, min(rate * dt, target - value))


def steering_limit(speed, config=CAR, input_config=GAME_INPUT):
    if not input_config.speed_sensitive_steering:
        return config.steering_degrees
    wheelbase = config.wheelbase
    safe_angle = math.degrees(
        math.atan(wheelbase * input_config.assisted_lateral_acceleration / (speed * speed + 16))
    )
    return min(config.steering_degrees, safe_angle)


class DriverAssist:
    def __init__(self, config=CAR, input_config=GAME_INPUT):
        self.config = config
        self.input_config = input_config
        self.throttle = 0.0
        self.brake = 0.0
        self.reverse_wait = 0.0

    def command(self, control, speed, gear, reverse_enabled, dt):
        config = self.input_config
        throttle = control.throttle if control.brake == 0 else 0.0
        if config.progressive_pedals:
            rate = config.throttle_rise if throttle > self.throttle else config.throttle_release
            self.throttle = approach(self.throttle, throttle, rate, dt)
            rate = config.brake_rise if control.brake > self.brake else config.brake_release
            self.brake = approach(self.brake, control.brake, rate, dt)
        else:
            self.throttle, self.brake = throttle, control.brake

        if not config.automatic_reverse:
            return VehicleCommand(
                steering=control.steering * steering_limit(speed, self.config, config),
                throttle=self.throttle, brake=self.brake, direction=control.direction,
            )

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
                if reverse_enabled and self.reverse_wait >= config.reverse_delay:
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
            steering=control.steering * steering_limit(speed, self.config, config),
            throttle=pedal,
            brake=brake,
            direction=direction,
        )
