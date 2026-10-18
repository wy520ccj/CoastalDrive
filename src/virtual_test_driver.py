"""固定能力的闭环试车策略；只输出Control，由Simulation消费。"""

import math

from driver_assist import steering_limit
from slalom_lesson import ENTRY_DISTANCE, GATES
from vehicle_state import Control

POLICY = {"id": "coastal-slalom-pursuit-v1", "decision_hz": 20, "physics_hz": 120,
          "target_kph": 60., "preview_base_m": 5., "preview_seconds": .45,
          "throttle_bias": .18, "speed_p": .4, "brake_p": .3, "brake_deadband_mps": .5}


def target_x(distance):
    previous_y, previous_x = ENTRY_DISTANCE, 0.
    for y, x in GATES:
        if distance <= y:
            fraction = max(0., min(1., (distance-previous_y)/(y-previous_y)))
            return previous_x+(x-previous_x)*.5*(1-math.cos(math.pi*fraction))
        previous_y, previous_x = y, x
    return 0.


class VirtualTestDriver:
    def __init__(self, config, origin, policy=None):
        self.config, self.origin = config, origin
        self.policy = POLICY.copy() if policy is None else policy.copy()

    def sample(self, snapshot, dt):
        car = snapshot.player
        policy = self.policy
        x, y = car.position[:2]
        look = policy["preview_base_m"]+abs(car.speed)*policy["preview_seconds"]
        dx, dy = target_x(y-self.origin+look)-x, look
        error = math.atan2(-dx, dy)-math.radians(car.heading)
        # 同一算法使用各车已知轴距，不用另一辆车的几何反算方向盘。
        wheel_angle = math.degrees(math.atan2(2*self.config.wheelbase*math.sin(error), math.hypot(dx, dy)))
        steering = max(-1., min(1., -wheel_angle/steering_limit(car.speed, self.config)))
        speed_error = policy["target_kph"]/3.6-car.speed
        return Control(steering=steering,
            throttle=max(0., min(1., policy["throttle_bias"]+policy["speed_p"]*speed_error)),
            brake=max(0., min(1., -policy["brake_p"]*speed_error))
                  if speed_error < -policy["brake_deadband_mps"] else 0.)
