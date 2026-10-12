"""驱动轮滑转反馈TCS；发动机削矩与制动请求均由实际执行器落实。"""

from dataclasses import dataclass

from wheel_contact_kernels import traction_advance


@dataclass(frozen=True)
class TractionConfig:
    tcs_enabled: bool = True
    target_slip: float = .12
    slip_hysteresis: float = .015
    slip_speed: float = 1.0  # 低速滑移分母尺度，m/s。
    prediction_time: float = .12  # 当前发动机执行器响应期，s。
    release_rate: float = 12.0
    apply_rate: float = 1.5
    slip_rate_gain: float = 12.0
    brake_gain: float = .2
    maximum_brake: float = .25


@dataclass(frozen=True)
class TractionState:
    requested_throttle: float = 0.0
    torque_scale: float = 1.0
    active: bool = False
    wheel_slips: tuple[float | None, float | None, float | None, float | None] = (None, None, None, None)
    brake_requests: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    feedback_ticks: tuple[int, int, int, int] = (0, 0, 0, 0)


class TractionControl:
    def __init__(self, config, driven_wheels=(2, 3)):
        self.config = config
        self.driven_wheels = driven_wheels
        self.state = TractionState()

    def advance(self, pedal, direction, braking, wheels, radius, dt):
        """反馈取上一完整步真值；离地轮不用于路面滑转调节。"""
        self.state = traction_advance(self.config, self.state, pedal, direction, braking, tuple(wheels),
                                      self.driven_wheels, radius, dt)
        return self.state
