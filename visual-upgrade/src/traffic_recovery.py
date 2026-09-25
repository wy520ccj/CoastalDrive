"""Low-speed recovery after a spin or a shove, using ordinary vehicle controls."""

import math

from traffic import extents
from vehicle_config import CAR
from vehicle_response import steering_limit
from vehicle_state import Control


class TrafficRecovery:
    def __init__(self):
        self.phase = ""
        self.lane = 0
        self.settled = 0.0
        self.clear = 0.0
        self.aligned = 0.0

    def update(self, car, traffic, road, lane, target_lateral):
        target = road.lanes[lane] if target_lateral is None else target_lateral
        disturbed = abs(car.heading) > 45 or abs(car.position[0] - target) > 2.8 or abs(car.roll) > 35
        if not self.phase:
            if not disturbed:
                return None
            self.phase = "braking"
            self.settled = self.clear = self.aligned = 0.0
            self.lane = min(range(len(road.lanes)), key=lambda i: abs(car.position[0] - road.lanes[i]))

        vx, vy = self.velocity(car)
        speed = math.hypot(vx, vy)
        upright = abs(car.roll) < 20 and abs(car.pitch) < 20 and abs(car.heading) < 105
        if not upright:
            self.phase = "blocked"
            self.settled = self.clear = self.aligned = 0.0
            return Control(brake=1)
        if self.phase in ("braking", "blocked"):
            self.settled = self.settled + 0.05 if speed < 0.7 else 0.0
            if self.settled < 0.6:
                return Control(brake=1)
            self.phase = "waiting"

        lateral_error = road.lanes[self.lane] - car.position[0]
        lookahead = 5 + speed * 0.65
        error = math.atan2(-lateral_error, lookahead) - math.radians(car.heading)
        angle = math.degrees(math.atan2(2 * CAR.wheelbase * math.sin(error), math.hypot(lateral_error, lookahead)))
        steering = max(-1, min(1, -angle / steering_limit(car.speed)))
        desired_speed = 2.0 if abs(car.heading) > 35 else 3.0
        if not self.path_clear(car, traffic, steering, desired_speed):
            self.phase = "waiting"
            self.clear = self.aligned = 0.0
            return Control(steering=steering, brake=1)

        self.clear += 0.05
        if self.clear < 0.8:
            return Control(steering=steering, brake=1)
        self.phase = "returning"
        aligned = abs(lateral_error) < 0.45 and abs(car.heading) < 6 and abs(car.roll) < 10
        self.aligned = self.aligned + 0.05 if aligned else 0.0
        if self.aligned >= 0.8:
            self.phase = ""
            return None
        error = desired_speed - car.speed
        brake = min(1, -error * 0.4) if error < -0.3 else 0
        throttle = max(0, min(0.4, 0.18 + error * 0.2)) if not brake else 0
        return Control(steering, throttle, brake)

    @staticmethod
    def velocity(car):
        if car.velocity is not None:
            return car.velocity[:2]
        angle = math.radians(car.heading)
        return -math.sin(angle) * car.speed, math.cos(angle) * car.speed

    def path_clear(self, car, traffic, steering, desired_speed):
        """Check the swept footprint and approaching cars before creeping forward."""
        x, y = car.position[:2]
        heading = math.radians(car.heading)
        speed = max(0, car.speed)
        for step in range(11):
            t = step * 0.25
            width, length = extents(math.degrees(heading), 0)
            if abs(x) + width > 7.65:
                return False
            for other in traffic:
                if not other.active:
                    continue
                vx, vy = self.velocity(other)
                ox, oy = other.position[0] + vx * t, other.position[1] + vy * t
                ow, ol = extents(other.heading, 0)
                if abs(ox - x) < width + ow + 0.35 and abs(oy - y) < length + ol + 1.0:
                    return False
            speed += max(-0.5, min(0.25, desired_speed - speed))
            rack = car.steering if step == 0 else steering * steering_limit(speed)
            heading -= speed / CAR.wheelbase * math.tan(math.radians(rack)) * 0.25
            x -= math.sin(heading) * speed * 0.25
            y += math.cos(heading) * speed * 0.25
        return True
