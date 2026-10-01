"""后驱轮滑转反馈TCS；发动机削矩与制动请求均由实际执行器落实。"""

from dataclasses import dataclass


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
    def __init__(self, config):
        self.config = config
        self.state = TractionState()

    def advance(self, pedal, direction, braking, wheels, radius, dt):
        """反馈取上一完整步真值；离地轮不用于路面滑转调节。"""
        config, previous = self.config, self.state
        slips = tuple(
            direction * (radius * wheel.omega - wheel.longitudinal_speed)
            / max(abs(wheel.longitudinal_speed), config.slip_speed)
            if wheel.sample_support else None
            for wheel in wheels
        )
        requests = [0.0] * 4
        scale, active = 1.0, False
        eligible = config.tcs_enabled and pedal > 0 and direction != 0 and not braking
        driven = [slips[index] for index in (2, 3) if slips[index] is not None]
        if eligible and driven:
            predicted = []
            for index in (2, 3):
                slip = slips[index]
                if slip is None:
                    continue
                trend = 0.0
                if previous.wheel_slips[index] is not None:
                    trend = (slip - previous.wheel_slips[index]) / dt
                predicted.append(slip + config.prediction_time * trend)
                # 分轮制动消耗已积累的转动能，不把等分传动冒充差速器。
                requests[index] = min(config.maximum_brake,
                                      config.brake_gain * max(0.0, slip - config.target_slip))
            worst = max(predicted)
            active = previous.active or worst > config.target_slip + config.slip_hysteresis
            if active:
                error = config.target_slip - worst
                rate = max(-config.release_rate, min(config.apply_rate, config.slip_rate_gain * error))
                scale = max(0.0, min(1.0, previous.torque_scale + rate * dt))
                active = scale < 1.0 or any(requests)
            else:
                requests = [0.0] * 4
        self.state = TractionState(pedal, scale, active, slips, tuple(requests),
                                   tuple(wheel.sample_tick for wheel in wheels))
        return self.state
