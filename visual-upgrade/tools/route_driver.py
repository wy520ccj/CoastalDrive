"""Deterministic route driver for H2 checks. This is not a player-facing AI mode."""

import math

from coastal_map import point_at, project
from simulation import Control
from vehicle_response import steering_limit


class RouteDriver:
    def __init__(self, speed_kmh=90):
        self.speed = speed_kmh / 3.6

    def sample(self, state, dt):
        return self.control(state.player)

    def control(self, car):
        _, _, progress = project(*car.position[:2])
        lookahead = 5 + abs(car.speed) * 0.65
        target = point_at(progress + lookahead)
        dx, dy = target.x - car.position[0], target.y - car.position[1]
        error = math.atan2(-dx, dy) - math.radians(car.heading)
        angle = math.degrees(math.atan2(4.4 * math.sin(error), math.hypot(dx, dy)))
        steering = max(-1, min(1, -angle / steering_limit(car.speed)))
        desired_speed = self.speed
        # Brake before a bend; steering assistance cannot make a fast car turn arbitrarily hard.
        for ahead in range(0, max(20, int(abs(car.speed) * 2)), 5):
            a, b = point_at(progress + ahead), point_at(progress + ahead + 8)
            curvature = abs(math.radians((b.heading - a.heading + 180) % 360 - 180)) / 8
            bend_speed = math.sqrt(3.5 / max(curvature, 0.001))
            desired_speed = min(desired_speed, math.sqrt(bend_speed**2 + 5 * ahead))
        error = desired_speed - car.speed
        return Control(
            steering=steering,
            throttle=max(0, min(1, 0.35 + error * 0.22)),
            brake=max(0, min(1, -error * 0.25)) if error < -0.8 else 0,
        )
