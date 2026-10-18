"""短课题可重复的验证驾驶员；仅输出正常驾驶请求，不修改车辆状态。"""

import math

from driver_assist import steering_limit
from simulation import Control
from slalom_lesson import ENTRY_DISTANCE, GATES


def path_x(distance):
    old_y, old_x = ENTRY_DISTANCE, 0.
    for y, x in GATES:
        if distance <= y:
            fraction = max(0., min(1., (distance-old_y)/(y-old_y)))
            return old_x+(x-old_x)*.5*(1-math.cos(math.pi*fraction))
        old_y, old_x = y, x
    return 0.


class SlalomDriver:
    def __init__(self, speed_kph, config, *, origin=8., binary=True, straight=False):
        self.speed, self.config = speed_kph/3.6, config
        self.origin, self.binary, self.straight = origin, binary, straight

    def sample(self, state, dt):
        car = state.player
        x, y = car.position[:2]
        look = 5+abs(car.speed)*.45
        dx, dy = (0. if self.straight else path_x(y-self.origin+look))-x, look
        error = math.atan2(-dx, dy)-math.radians(car.heading)
        angle = math.degrees(math.atan2(5.4*math.sin(error), math.hypot(dx, dy)))
        steer = max(-1., min(1., -angle/steering_limit(car.speed, self.config)))
        speed_error = self.speed-car.speed
        if self.binary:
            steer = 0. if abs(steer) < .08 else math.copysign(1., steer)
            return Control(steering=steer, throttle=float(speed_error > -.25), brake=float(speed_error < -1.))
        return Control(steering=steer, throttle=max(0., min(1., .18+.4*speed_error)),
                       brake=max(0., min(1., -.3*speed_error)) if speed_error < -.5 else 0.)


def apply_keys(keyboard, control):
    desired = {key for key, enabled in (("w", control.throttle > 0), ("s", control.brake > 0),
                ("a", control.steering < 0), ("d", control.steering > 0)) if enabled}
    for key in ("w", "s", "a", "d"):
        keyboard.press(key) if key in desired else keyboard.release(key)
