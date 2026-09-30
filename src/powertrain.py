"""发动机转速、自动变速箱与纵向驱动力响应。"""

import math
from itertools import pairwise

from vehicle_config import CAR


def engine_torque(rpm):
    curve = CAR.torque_curve
    if rpm <= curve[0][0]:
        return curve[0][1]
    for (low_rpm, low_torque), (high_rpm, high_torque) in pairwise(curve):
        if rpm <= high_rpm:
            fraction = (rpm - low_rpm) / (high_rpm - low_rpm)
            return low_torque + (high_torque - low_torque) * fraction
    return 0.0


class Powertrain:
    def __init__(self):
        self.rpm = CAR.idle_rpm
        self.gear = 1
        self.shift_remaining = 0.0
        self.shift_cooldown = 0.0
        self.force = 0.0

    def advance(self, speed, pedal, direction, braking, dt):
        if direction < 0 and self.gear != -1:
            self.gear = -1
            self.shift_remaining = 0.0
        elif direction > 0 and self.gear < 0:
            self.gear = 1
            self.shift_remaining = 0.0

        self.shift_remaining = max(0.0, self.shift_remaining - dt)
        self.shift_cooldown = max(0.0, self.shift_cooldown - dt)
        ratio = (3.0 if self.gear < 0 else CAR.gear_ratios[self.gear - 1]) * CAR.final_drive
        wheel_rpm = abs(speed) / (math.tau * CAR.wheel_radius) * 60
        coupled_rpm = wheel_rpm * ratio
        if self.gear > 0 and self.shift_cooldown == 0:
            upshift = 3000 + 2300 * pedal
            new_gear = self.gear
            if coupled_rpm > upshift and self.gear < len(CAR.gear_ratios):
                new_gear += 1
            elif coupled_rpm < 1500 and self.gear > 1:
                new_gear -= 1
            if new_gear != self.gear:
                self.gear = new_gear
                self.shift_remaining = CAR.shift_time
                self.shift_cooldown = 0.8
                ratio = CAR.gear_ratios[self.gear - 1] * CAR.final_drive
                coupled_rpm = wheel_rpm * ratio

        # 起步离合允许发动机转速先高于怠速，再逐渐带动车速。
        launch_rpm = CAR.idle_rpm + 700 * pedal * max(0, 1 - abs(speed) / 6)
        target_rpm = max(launch_rpm, coupled_rpm)
        self.rpm += (target_rpm - self.rpm) * (1 - math.exp(-dt / 0.10))
        torque = engine_torque(self.rpm) * pedal
        force = torque * ratio * CAR.drivetrain_efficiency / CAR.wheel_radius
        if direction < 0:
            force = min(force, CAR.reverse_force)
            force *= min(1, max(0, CAR.reverse_speed - abs(speed)))
        else:
            force *= min(1, max(0, (CAR.max_speed - abs(speed)) / 2))
        if self.shift_remaining > 0:
            force *= 0.15
        target_force = direction * force
        self.force += (target_force - self.force) * (1 - math.exp(-dt / CAR.torque_response))
        if braking:
            self.force = 0.0
        engine_drag = CAR.engine_braking * ratio / CAR.wheel_radius
        engine_drag *= (1 - pedal) * min(abs(speed) / 2, 1)
        if self.shift_remaining > 0:
            engine_drag *= 0.15
        return self.force, engine_drag
