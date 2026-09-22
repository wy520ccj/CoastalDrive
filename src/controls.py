from typing import Protocol

from simulation import Control, Snapshot


class Controller(Protocol):
    def sample(self, state: Snapshot, dt: float) -> Control: ...


class KeyboardController:
    def __init__(self):
        self.pressed = set()

    def press(self, key):
        fresh = key not in self.pressed
        self.pressed.add(key)
        return fresh

    def release(self, key):
        self.pressed.discard(key)

    def clear(self):
        self.pressed.clear()

    def sample(self, state, dt):
        right = bool(self.pressed & {"d", "arrow_right"})
        left = bool(self.pressed & {"a", "arrow_left"})
        brake = bool(self.pressed & {"s", "arrow_down"})
        throttle = bool(self.pressed & {"w", "arrow_up"}) and not brake
        return Control(float(right - left), float(throttle), float(brake))


class ConstantController:
    """Script input for repeatable checks; it uses the same actuator as the keyboard."""

    def __init__(self, control=None):
        self.control = Control() if control is None else control

    def sample(self, state, dt):
        return self.control
