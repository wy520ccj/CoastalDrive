"""发动机转速、自动变速箱与驱动轴轮端转矩。"""

import math
from dataclasses import dataclass
from itertools import pairwise

from vehicle_config import CAR


@dataclass(frozen=True)
class PowertrainState:
    engine_omega: float
    engine_relative_omega: float
    gear: int
    ratio: float
    throttle: float
    engine_torque: float
    engine_drag_coefficient: float
    shift_phase: str
    clutch_position: float
    clutch_capacity: float
    clutch_torque: float
    clutch_slip: float
    drive_torque: float
    gear_loss_torque: float
    gear_input_speed: float
    engine_body_impulse: tuple
    engine_work: float
    engine_drag_heat: float
    clutch_heat: float
    gear_heat: float


def engine_torque(rpm, config=CAR):
    curve = config.torque_curve
    if rpm <= curve[0][0]:
        return curve[0][1]
    for (low_rpm, low_torque), (high_rpm, high_torque) in pairwise(curve):
        if rpm <= high_rpm:
            fraction = (rpm - low_rpm) / (high_rpm - low_rpm)
            return low_torque + (high_torque - low_torque) * fraction
    return 0.0


class Powertrain:
    def __init__(self, config=CAR):
        self.config = config
        self.rpm = self.config.idle_rpm
        self.gear = 1
        self.shift_remaining = 0.0
        self.shift_cooldown = 0.0
        self.drive_torque = 0.0
        self.engine_omega = config.idle_rpm * math.tau / 60
        self.relative_omega = self.engine_omega
        self.throttle = 0.0
        self.clutch_position = 0.0
        self.clutch_torque = 0.0
        self.clutch_slip = 0.0
        self.gear_loss_torque = 0.0
        self.gear_input_speed = 0.0
        self.clutch_heat = self.gear_heat = self.engine_drag_heat = self.engine_work = 0.0
        self.engine_body_impulse = (0., 0., 0.)
        self.shift_phase = "engaged"
        self.pending_gear = 1
        self.engine_torque_request = 0.0
        self.engine_drag_coefficient = 0.0

    @property
    def ratio(self):
        if self.gear == 0:
            return 0.
        config = self.config
        ratio = -config.reverse_gear_ratio if self.gear < 0 else config.gear_ratios[self.gear - 1]
        return ratio * config.final_drive

    @property
    def capacity(self):
        return self.config.clutch_capacity * self.clutch_position

    def observe(self, chassis):
        """真正相对壳体RPM；曲轴绝对轴速只能由共同机械积分更新。"""
        from panda3d.core import Vec3

        axis = chassis.getTransform().getQuat().xform(Vec3(*self.config.engine_axis))
        self.relative_omega = self.engine_omega - chassis.getAngularVelocity().dot(axis)
        self.rpm = self.relative_omega * 60 / math.tau

    def prepare(self, speed, driven_omega, pedal, direction, braking, dt, *,
                drive_scale=1., gear=None, clutch=None):
        """只推进控制和有限执行器，不生成轮速目标或在积分后钳曲轴速度。"""
        config = self.config
        if gear is not None and (not isinstance(gear, int) or not -1 <= gear <= len(config.gear_ratios)):
            raise ValueError("挡位请求超出当前变速箱范围")
        self.shift_cooldown = max(0., self.shift_cooldown - dt)
        self.shift_remaining = max(0., self.shift_remaining - dt)
        requested_gear = self.gear
        if gear is not None:
            requested_gear = gear
        elif direction < 0:
            requested_gear = -1
        elif direction > 0 and (self.gear <= 0 or self.pending_gear <= 0):
            requested_gear = 1
        elif self.gear > 0 and self.shift_phase == "engaged" and self.shift_cooldown == 0:
            if self.rpm > 3000 + 2300 * pedal and abs(self.clutch_slip) < 2. and self.gear < len(config.gear_ratios):
                requested_gear += 1
            elif self.rpm < 1500 and self.gear > 1:
                requested_gear -= 1
        interrupted = self.shift_phase == "releasing" and (
            gear is not None or direction < 0 or direction > 0 and self.pending_gear <= 0)
        if requested_gear != self.gear or interrupted:
            if self.shift_phase != "releasing" or self.pending_gear != requested_gear:
                self.shift_remaining = config.shift_time
            self.pending_gear = requested_gear
            self.shift_phase = "releasing"
        self.throttle += (pedal - self.throttle) * (1 - math.exp(-dt / config.torque_response))
        idle_speed = config.idle_rpm * math.tau / 60
        # engine_braking保留原近似闭节气门转矩；怠速以下连续趋零，系数取上一真实状态。
        drag = config.engine_braking / max(abs(self.relative_omega), idle_speed) * (1 - self.throttle)
        available_torque = engine_torque(self.rpm, config)
        combustion = available_torque * self.throttle
        if self.shift_phase != "engaged":
            # 沿用原换挡15%请求：作用于燃烧转矩，不伪造末轮速或曲轴RPM。
            combustion *= .15
        if config.game_speed_limits:
            # 道路软限制读取实际挡位，仅削驾驶请求；自由曲轴仍由有限怠速补偿克服损失。
            if self.gear < 0:
                combustion = min(combustion, config.reverse_force * config.wheel_radius
                                 / (config.reverse_gear_ratio * config.final_drive * config.drivetrain_efficiency))
                combustion *= min(1., max(0., config.reverse_speed - abs(speed)))
            elif self.gear > 0:
                combustion *= min(1., max(0., (config.max_speed - abs(speed)) / 2))
        # 原曲线是全负荷有效转矩；闭节气门损失随节气门消退，避免全负荷重复扣减。
        idle = max(0., min(config.engine_idle_torque_limit, drag * self.relative_omega
                          + config.engine_inertia * (idle_speed - self.relative_omega) / config.engine_idle_response))
        # 怠速补偿与驾驶请求共享全负荷能力；只能饱和真实主动请求，不能钳机械轴速。
        # 能力内保留小油门净增量，能力不足时怠速应自然下降。
        torque = min(available_torque, combustion + idle)
        if self.rpm >= config.engine_redline_rpm:
            torque = 0.
        self.engine_torque_request = torque * drive_scale
        self.engine_drag_coefficient = drag

        if self.shift_phase == "releasing":
            target = 0.
        elif clutch is not None:
            target = clutch
        elif braking or self.gear == 0:
            target = 0.
        elif pedal > 0:
            # 起步转速目标跟随实际节气门，避免未执行的踏板请求提前占用全部升速预算。
            launch_rpm = config.idle_rpm + 700 * self.throttle * max(0., 1 - abs(speed) / 6)
            target_speed = launch_rpm * math.tau / 60
            available = (self.engine_torque_request - self.engine_drag_coefficient * self.relative_omega
                         + config.engine_inertia * (self.relative_omega - target_speed) / config.clutch_launch_response)
            target = max(0., min(1., available / config.clutch_capacity))
            if self.ratio * driven_omega >= target_speed:
                target = 1.
        else:
            target = 1. if self.ratio * driven_omega > config.idle_rpm * math.tau / 60 else 0.
        rate = 1 / (config.clutch_release_time if target < self.clutch_position else config.clutch_engage_time)
        self.clutch_position += max(-rate * dt, min(rate * dt, target - self.clutch_position))
        if (self.shift_phase == "releasing" and self.clutch_position == 0
                and self.shift_remaining <= config.clutch_engage_time):
            self.gear = self.pending_gear
            self.shift_phase = "engaging"
            self.shift_cooldown = .8
        elif self.shift_phase == "engaging" and self.clutch_position == target:
            self.shift_phase = "engaged"

        self.clutch_heat = self.gear_heat = self.engine_drag_heat = self.engine_work = 0.
        self.engine_body_impulse = (0., 0., 0.)

    def accept_step(self, result, dt):
        """接受共同积分结果，热/功按本120Hz步累加，不另推进曲轴。"""
        self.engine_omega = result.engine_omega
        self.relative_omega = result.engine_relative_omega
        self.rpm = self.relative_omega * 60 / math.tau
        self.drive_torque = result.drive_torque
        self.clutch_torque, self.clutch_slip = result.clutch_torque, result.clutch_slip
        self.gear_loss_torque, self.gear_input_speed = result.gear_loss_torque, result.gear_input_speed
        self.clutch_heat += result.clutch_heat
        self.gear_heat += result.gear_heat
        self.engine_drag_heat += result.engine_drag_heat
        self.engine_work += result.engine_work
        self.engine_body_impulse = tuple(self.engine_body_impulse[a] + dt * result.engine_body_torque[a] for a in range(3))

    def snapshot(self):
        return PowertrainState(self.engine_omega, self.relative_omega, self.gear, self.ratio,
            self.throttle, self.engine_torque_request, self.engine_drag_coefficient, self.shift_phase,
            self.clutch_position, self.capacity, self.clutch_torque, self.clutch_slip, self.drive_torque,
            self.gear_loss_torque, self.gear_input_speed, self.engine_body_impulse, self.engine_work,
            self.engine_drag_heat, self.clutch_heat, self.gear_heat)

    def advance(self, speed, driven_omega, pedal, direction, braking, dt, *, drive_scale=1.0):
        config = self.config
        if direction < 0 and self.gear != -1:
            self.gear = -1
            self.shift_remaining = 0.0
        elif direction > 0 and self.gear < 0:
            self.gear = 1
            self.shift_remaining = 0.0

        self.shift_remaining = max(0.0, self.shift_remaining - dt)
        self.shift_cooldown = max(0.0, self.shift_cooldown - dt)
        ratio = (
            config.reverse_gear_ratio if self.gear < 0 else config.gear_ratios[self.gear - 1]
        ) * config.final_drive
        wheel_rpm = abs(driven_omega) / math.tau * 60
        coupled_rpm = wheel_rpm * ratio
        if self.gear > 0 and self.shift_cooldown == 0:
            upshift = 3000 + 2300 * pedal
            new_gear = self.gear
            if coupled_rpm > upshift and self.gear < len(config.gear_ratios):
                new_gear += 1
            elif coupled_rpm < 1500 and self.gear > 1:
                new_gear -= 1
            if new_gear != self.gear:
                self.gear = new_gear
                self.shift_remaining = config.shift_time
                self.shift_cooldown = 0.8
                ratio = config.gear_ratios[self.gear - 1] * config.final_drive
                coupled_rpm = wheel_rpm * ratio

        # 起步离合允许发动机转速先高于怠速，再逐渐带动车速。
        launch_rpm = config.idle_rpm + 700 * pedal * max(0, 1 - abs(speed) / 6)
        target_rpm = max(launch_rpm, coupled_rpm)
        self.rpm += (target_rpm - self.rpm) * (1 - math.exp(-dt / 0.10))
        torque = engine_torque(self.rpm, config) * pedal
        wheel_torque = torque * ratio * config.drivetrain_efficiency
        if config.game_speed_limits:
            if direction < 0:
                wheel_torque = min(wheel_torque, config.reverse_force * config.wheel_radius)
                wheel_torque *= min(1, max(0, config.reverse_speed - abs(speed)))
            else:
                wheel_torque *= min(1, max(0, (config.max_speed - abs(speed)) / 2))
        if self.shift_remaining > 0:
            wheel_torque *= 0.15
        target_torque = direction * wheel_torque * drive_scale
        self.drive_torque += (target_torque - self.drive_torque) * (
            1 - math.exp(-dt / config.torque_response)
        )
        if braking:
            self.drive_torque = 0.0
        engine_drag = config.engine_braking * ratio
        engine_drag *= (1 - pedal) * min(abs(driven_omega) * config.wheel_radius / 2, 1)
        if self.shift_remaining > 0:
            engine_drag *= 0.15
        return self.drive_torque, engine_drag
