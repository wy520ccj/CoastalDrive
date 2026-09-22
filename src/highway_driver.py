"""Seeded driving styles, IDM following and conservative adjacent-lane decisions.

IDM/MOBIL references and our physical-controller differences: docs/traffic-research.md.
"""

import math
import random

from traffic import Driver, Road, extents
from vehicle_state import Control

FLAT_ROAD = Road("endless")


def motion(car):
    if car.velocity is not None:
        return car.velocity[:2]
    angle = math.radians(car.heading)
    return -math.sin(angle) * car.speed, math.cos(angle) * car.speed


def acceleration(speed, desired, gap=math.inf, lead_speed=0, *, headway=1.6, comfort=2.0):
    speed = max(0, speed)
    wanted = 3 + max(
        0, speed * headway + speed * (speed - lead_speed) / (2 * math.sqrt(2 * comfort))
    )
    return max(
        -8, min(2, 2 * (1 - (speed / max(desired, 0.1)) ** 4 - (wanted / max(gap, 0.1)) ** 2))
    )


class HighwayDriver(Driver):
    def __init__(self, lane, seed):
        super().__init__(lane, 25)
        self.rng = random.Random(seed)
        self.style = self.rng.choices(("relaxed", "regular", "brisk"), (2, 5, 3))[0]
        low, high, headway = {
            "relaxed": (19, 24, 2.1),
            "regular": (24, 30, 1.7),
            "brisk": (29, 35, 1.4),
        }[self.style]
        self.preferred_speed = self.rng.uniform(low, high)
        self.cruise = self.preferred_speed
        self.headway = headway + self.rng.uniform(-0.1, 0.2)
        self.politeness = self.rng.uniform(0.2, 0.5)
        self.reaction_time = self.rng.uniform(0.3, 0.6)
        self.gain_threshold = self.rng.uniform(0.15, 0.35)
        self.target_speed = self.cruise
        self.speed_clock = self.rng.uniform(5, 12)
        self.pace = "cruise"
        self.decision_clock = self.rng.uniform(2, 6)
        self.cooldown = 0.0
        self.waiting = 0.0
        self.clear_time = 0.0
        self.threat_time = 0.0
        self.rear_time = 0.0
        self.rear_pressure = False
        self.avoid_offset = 0.0
        self.hazard_brake = 0.0
        self.reason = "cruise"
        self.target_lane = lane
        self.phase = "cruise"
        self.signal = 0
        self.elapsed = 0.0
        self.start_y = 0.0
        self.change_length = 60.0
        self.pedal = 0.0
        self.lane_changes = 0

    def neighbors(self, car, traffic, road, lane):
        front, rear = (math.inf, None), (math.inf, None)
        lateral = road.lanes[lane]
        for other in traffic:
            if not other.active:
                continue
            width, length = extents(other.heading, 0)
            if abs(other.position[0] - lateral) > width + 0.95 + 0.25:
                continue
            delta = other.position[1] - car.position[1]
            gap = abs(delta) - length - extents(car.heading, 0)[1]
            if delta >= 0 and gap < front[0]:
                front = gap, other
            elif delta < 0 and gap < rear[0]:
                rear = gap, other
        return front, rear

    def lane_acceleration(self, car, front):
        gap, leader = front
        return acceleration(
            car.speed,
            self.cruise,
            gap,
            motion(leader)[1] if leader else self.cruise,
            headway=self.headway,
        )

    def opportunity(self, car, traffic, road, lane, reservations):
        front, rear = self.neighbors(car, traffic, road, lane)
        for target, y, speed in reservations:
            if target == lane and abs(y - car.position[1]) < 12 + max(speed, car.speed) * 3:
                return None
        gap, leader = front
        if leader and gap < max(8, car.speed * self.headway):
            return None
        back_gap, follower = rear
        penalty = 0.0
        if follower:
            closing = max(0, motion(follower)[1] - motion(car)[1])
            if back_gap < 8 + closing * 5 + closing * closing / 4:
                return None
            imposed = acceleration(
                follower.speed, max(follower.speed, self.cruise), back_gap, car.speed, headway=1.8
            )
            if imposed < -2.0:
                return None
            penalty = min(0, imposed)
        # Check the complete crossing horizon, including fast cars approaching from behind.
        for other in traffic:
            if not other.active or abs(other.position[0] - road.lanes[lane]) > 2.3:
                continue
            now = other.position[1] - car.position[1]
            later = now + (motion(other)[1] - motion(car)[1]) * 5
            if now * later <= 0 or min(abs(now), abs(later)) < 9:
                return None
        return self.lane_acceleration(car, front) + self.politeness * penalty

    def anticipate(self, car, traffic, road):
        """Notice encroachment early; yield inside the lane before considering a lane change."""
        vx, vy = motion(car)
        width, length = extents(car.heading, 0)
        offset, braking = 0.0, 0.0
        danger = False
        approaching = False
        for other in traffic:
            if not other.active:
                continue
            dx = other.position[0] - car.position[0]
            dy = other.position[1] - car.position[1]
            if abs(dy) > 12 + abs(vy) * 2:
                continue
            ox, oy = motion(other)
            ow, ol = extents(other.heading, 0)
            if (
                dy < -length - ol and abs(dx) < width + ow + 0.5
                and oy - vy > 2 and -dy - length - ol < max(20, (oy - vy) * 5)
            ):
                approaching = True
            # Use physical lateral velocity, including a sliding or diagonally driven player.
            near = any(
                abs(dx + (ox - vx) * t) < width + ow + 0.45
                and abs(dy + (oy - vy) * t) < length + ol + 3
                for t in (0, 0.5, 1.0, 1.5)
            )
            if not near:
                continue
            danger = True
            # Braking for a car entirely behind us would make a rear-end approach worse.
            if dy > -length:
                closing = max(0, vy - oy)
                gap = max(1, dy - length - ol - 2)
                braking = max(braking, min(7, 1.5 + closing * closing / (2 * gap)))
                if abs(dx) > 0.4 and abs(dy) < 12:
                    offset += -0.65 if dx > 0 else 0.65
        self.threat_time = self.threat_time + 0.05 if danger else 0.0
        self.rear_time = self.rear_time + 0.05 if approaching else 0.0
        self.rear_pressure = self.rear_time >= self.reaction_time
        if self.threat_time < self.reaction_time:
            offset, braking = 0.0, 0.0
        offset = max(-0.65, min(0.65, offset))
        target = road.lanes[self.lane] + offset
        # Never dodge into a car on the other side. Braking remains available.
        for other in traffic:
            ow, ol = extents(other.heading, 0)
            if (
                other.active
                and abs(other.position[1] - car.position[1]) < length + ol + 5
                and abs(other.position[0] - target) < width + ow + 0.3
                and abs(other.position[0] - target) < abs(other.position[0] - car.position[0])
            ):
                offset = 0.0
        self.avoid_offset += max(-0.03, min(0.03, offset - self.avoid_offset))
        self.hazard_brake = braking

    def plan(self, car, traffic, road, reservations):
        if road.curve:
            self.plan(road.lane_frame(car), [road.lane_frame(c) for c in traffic],
                      FLAT_ROAD, reservations)
            return
        dt = 0.05
        self.speed_clock -= dt
        self.decision_clock -= dt
        self.cooldown = max(0, self.cooldown - dt)
        if self.speed_clock <= 0:
            self.pace = self.rng.choices(("cruise", "ease", "hurry"), (4, 3, 3))[0]
            low, high = {"cruise": (-1, 1), "ease": (-5, -2.5), "hurry": (2, 4)}[self.pace]
            self.target_speed = max(17, min(36, self.preferred_speed + self.rng.uniform(low, high)))
            self.speed_clock = self.rng.uniform(10, 22)
        self.cruise += max(-0.03, min(0.03, self.target_speed - self.cruise))
        self.anticipate(car, traffic, road)
        if self.rear_pressure and self.phase == "cruise":
            self.decision_clock = 0
        front, _ = self.neighbors(car, traffic, road, self.lane)
        gap, leader = front
        blocked = leader is not None and gap < self.cruise * 4 and car.speed < self.cruise - 2
        self.waiting = min(12, self.waiting + dt) if blocked else max(0, self.waiting - dt)
        self.clear_time = self.clear_time + dt if gap > max(45, car.speed * 3) else 0
        if self.phase == "signal":
            self.elapsed += dt
            if self.opportunity(car, traffic, road, self.target_lane, reservations) is None:
                self.cancel()
            elif self.elapsed >= 1.0:
                self.phase = "changing"
                self.start_y = car.position[1]
                self.change_length = max(45, car.speed * 4)
        elif self.phase == "changing":
            if (
                abs(car.position[0] - road.lanes[self.lane]) < 0.8
                and self.opportunity(car, traffic, road, self.target_lane, reservations) is None
            ):
                self.cancel()
                return
            if abs(car.position[0] - road.lanes[self.target_lane]) < 0.25 and abs(car.heading) < 3:
                self.lane = self.target_lane
                self.lane_changes += 1
                self.cancel()
        elif (
            self.decision_clock <= 0 and car.speed > 6 and not self.recovering
            and (self.cooldown <= 0 or self.hazard_brake > 2 or self.rear_pressure)
        ):
            current = self.lane_acceleration(car, front)
            yielding = self.rear_pressure
            candidates = []
            for lane in (self.lane - 1, self.lane + 1):
                if 0 <= lane < len(road.lanes):
                    gain = self.opportunity(car, traffic, road, lane, reservations)
                    if gain is None:
                        continue
                    benefit, reason = gain - current, "overtake"
                    if gain > current - 0.1:
                        if yielding:
                            benefit += 0.8 if lane > self.lane else 0.55
                            reason = "yield_rear"
                        elif lane > self.lane and self.clear_time > 5:
                            benefit += 0.4
                            reason = "keep_right"
                    threshold = max(0.08, self.gain_threshold - self.waiting * 0.02)
                    if benefit > threshold:
                        candidates.append((benefit, lane, reason))
            if candidates:
                _, self.target_lane, self.reason = max(candidates)
                self.phase, self.elapsed = "signal", 0
                self.signal = 1 if self.target_lane > self.lane else -1
            self.decision_clock = self.rng.uniform(0.6, 1.2)
        if self.phase in ("signal", "changing"):
            reservations.append((self.target_lane, car.position[1], car.speed))

    def cancel(self):
        self.phase, self.signal = "cruise", 0
        self.target_lane = self.lane
        self.target_lateral = None
        self.cooldown = self.rng.uniform(5, 9)
        self.decision_clock = self.rng.uniform(0.6, 1.2)
        self.clear_time = self.waiting = 0.0
        self.reason = "cruise"

    def control(self, car, traffic, road, locations):
        if road.curve:
            local_car = road.lane_frame(car)
            local_traffic = [road.lane_frame(c) for c in traffic]
            action = self.control(local_car, local_traffic, FLAT_ROAD,
                                  [FLAT_ROAD.locate(c) for c in [local_car, *local_traffic]])
            steering = super().control(car, traffic, road, locations)
            if self.recovering:
                return steering
            distance = locations[0][0]
            speed_limit = self.cruise
            for ahead in range(0, max(20, int(abs(car.speed) * 2)), 5):
                a, b = road.sample(distance + ahead, self.lane), road.sample(distance + ahead + 8, self.lane)
                curvature = abs(math.radians((b.heading - a.heading + 180) % 360 - 180)) / 8
                speed_limit = min(speed_limit, math.sqrt(2.5 / max(curvature, 0.0001) + 5 * ahead))
            if car.speed > speed_limit + 0.5:
                return Control(steering.steering, 0, max(action.brake, min(1, (car.speed - speed_limit) * 0.2)))
            return Control(steering.steering, action.throttle, action.brake)
        if self.phase == "changing":
            lookahead = 5 + abs(car.speed) * 0.65
            t = max(0, min(1, (car.position[1] + lookahead - self.start_y) / self.change_length))
            smooth = t * t * t * (10 - 15 * t + 6 * t * t)
            self.target_lateral = (
                road.lanes[self.lane]
                + (road.lanes[self.target_lane] - road.lanes[self.lane]) * smooth
            )
        else:
            self.target_lateral = road.lanes[self.lane] + self.avoid_offset
        steering_action = super().control(car, traffic, road, locations)
        if self.recovering:
            self.cancel()
            return steering_action
        lanes = (self.lane, self.target_lane) if self.phase == "changing" else (self.lane,)
        desired_acc = min(
            self.lane_acceleration(car, self.neighbors(car, traffic, road, lane)[0])
            for lane in lanes
        )
        if self.hazard_brake:
            desired_acc = min(desired_acc, -self.hazard_brake)
        if desired_acc < -0.1:
            self.pedal = 0
            brake = min(1, -desired_acc / 7.5 + 0.06)
        else:
            self.pedal = max(0, min(1, self.pedal + (desired_acc - car.acceleration) * 0.009))
            brake = 0
        if car.speed < 0.3 and desired_acc < 0:
            brake = 1
        return Control(steering_action.steering, self.pedal, brake)
