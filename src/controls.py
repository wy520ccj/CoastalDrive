from typing import Protocol

from driver_assist import GAME_INPUT
from simulation import Control, Snapshot


class Controller(Protocol):
    def sample(self, state: Snapshot, dt: float) -> Control: ...


class KeyboardController:
    def __init__(self, input_config=GAME_INPUT):
        self.input_config = input_config
        self.pressed = set()
        self.direction = 1
        self.steering = 0.

    def press(self, key):
        fresh = key not in self.pressed
        self.pressed.add(key)
        if key == "q":
            self.direction = -1
        elif key == "e":
            self.direction = 1
        return fresh

    def release(self, key):
        self.pressed.discard(key)

    def clear(self):
        self.pressed.clear()
        self.steering = 0.

    def sample(self, state, dt):
        right = bool(self.pressed & {"d", "arrow_right"})
        left = bool(self.pressed & {"a", "arrow_left"})
        brake = bool(self.pressed & {"s", "arrow_down"})
        throttle = bool(self.pressed & {"w", "arrow_up"}) and not brake
        target = float(right-left)
        rate = self.input_config.keyboard_steering_rate
        if rate is None:
            self.steering = target
        else:
            # 键盘表示持续转动方向盘，不能把一次短按当作直接打满齿条。
            # .4行程/s相当于450°单边方向盘以180°/s转动；松键模拟主动回正。
            self.steering += max(-rate*dt,min(rate*dt,target-self.steering))
        return Control(self.steering, float(throttle), float(brake), self.direction)


class ConstantController:
    """Script input for repeatable checks; it uses the same actuator as the keyboard."""

    def __init__(self, control=None):
        self.control = Control() if control is None else control

    def sample(self, state, dt):
        return self.control
