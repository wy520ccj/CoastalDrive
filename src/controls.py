from typing import Protocol

from driver_assist import GAME_INPUT
from simulation import Control, Snapshot

_INPUT_KEYS = {'w':1, 'arrow_up':1, 's':2, 'arrow_down':2,
               'a':4, 'arrow_left':4, 'd':8, 'arrow_right':8}


class Controller(Protocol):
    def sample(self, state: Snapshot, dt: float) -> Control: ...


class KeyboardController:
    def __init__(self, input_config=GAME_INPUT, *, input_word=None, input_reader=False):
        self.input_config = input_config
        self.input_word = input_word
        self.input_reader = input_reader
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
        self.publish_input()
        return fresh

    def release(self, key):
        self.pressed.discard(key)
        self.publish_input()

    def clear(self):
        self.pressed.clear()
        self.steering = 0.
        self.publish_input()

    def publish_input(self):
        """窗口只发布按键位和挡向；不等待快照/绘制管道，也不发布车辆状态。"""
        if self.input_word is not None and not self.input_reader:
            bits = 16 if self.direction < 0 else 0
            for key in self.pressed:
                if key in _INPUT_KEYS:
                    bits |= _INPUT_KEYS[key]
            self.input_word.value = bits

    def sample(self, state, dt):
        if self.input_reader:
            bits = self.input_word.value
            self.pressed = {key for key, bit in _INPUT_KEYS.items() if bits & bit}
            self.direction = -1 if bits & 16 else 1
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
            # 松键模拟主动回正；响应速率属于键盘接口，不改变机械齿条。
            self.steering += max(-rate*dt,min(rate*dt,target-self.steering))
        return Control(self.steering, float(throttle), float(brake), self.direction)


class ConstantController:
    """Script input for repeatable checks; it uses the same actuator as the keyboard."""

    def __init__(self, control=None):
        self.control = Control() if control is None else control

    def sample(self, state, dt):
        return self.control
