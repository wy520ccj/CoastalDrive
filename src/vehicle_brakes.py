"""四轮制动执行器与ABS反馈；只调节制动请求，不写车辆运动状态。"""

from dataclasses import dataclass

from wheel_contact_kernels import brakes_advance


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
        self.states, pressures = brakes_advance(self.config, self.states, tuple(wheels), tuple(requests), radius, dt)
        return pressures
