"""四轮制动执行器与ABS反馈；只调节制动请求，不写车辆运动状态。"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BrakeConfig:
    # 通用参考制动器的设计时间常数；零值仅用于历史理想执行器对照。
    response_time: float = .025
    abs_enabled: bool = True
    target_slip: float = .12
    slip_hysteresis: float = .015
    minimum_speed: float = 1.5
    release_rate: float = 25.0
    apply_rate: float = 5.0
    slip_rate_gain: float = 30.0  # 滑移误差到压力变化率，s⁻¹。


@dataclass(frozen=True)
class BrakeState:
    requested: float = 0.0
    commanded: float = 0.0
    pressure: float = 0.0
    braking_slip: float | None = None
    abs_active: bool = False
    phase: str = "uninitialized"
    feedback_tick: int = 0
    predicted_slip: float | None = None


class Brakes:
    def __init__(self, config):
        self.config = config
        self.states = tuple(BrakeState() for _ in range(4))

    def advance(self, requests, wheels, radius, dt):
        """上一完整步轮速/轮心速度为反馈；首次使用仿真真值观测。"""
        config = self.config
        states = []
        for requested, wheel, previous in zip(requests, wheels, self.states):
            speed = abs(wheel.longitudinal_speed)
            eligible = config.abs_enabled and requested > 0 and wheel.sample_support and speed >= config.minimum_speed
            slip = None
            if wheel.sample_support and speed >= config.minimum_speed:
                direction = math.copysign(1.0, wheel.longitudinal_speed)
                slip = (speed - direction * radius * wheel.omega) / speed
            predicted = slip
            if slip is not None and previous.braking_slip is not None:
                # 用液压响应期内的滑移趋势提前减压，避免等压力落下时车轮已经恢复。
                predicted += config.response_time * (slip - previous.braking_slip) / dt
            active = eligible and (previous.abs_active or predicted > config.target_slip + config.slip_hysteresis)
            command, phase = requested, "normal"
            if active:
                command = min(previous.commanded, requested)
                error = config.target_slip - predicted
                if error < -config.slip_hysteresis:
                    rate = max(-config.release_rate, config.slip_rate_gain * error)
                    command = max(0.0, command + rate * dt)
                    phase = "release"
                elif error > config.slip_hysteresis:
                    rate = min(config.apply_rate, config.slip_rate_gain * error)
                    command = min(requested, command + rate * dt)
                    phase = "apply"
                else:
                    phase = "hold"
            pressure = command if config.response_time == 0 else previous.pressure + (
                command - previous.pressure
            ) * (1 - math.exp(-dt / config.response_time))
            states.append(BrakeState(requested, command, pressure, slip, active, phase,
                                     wheel.sample_tick, predicted))
        self.states = tuple(states)
        return tuple(state.pressure for state in self.states)
