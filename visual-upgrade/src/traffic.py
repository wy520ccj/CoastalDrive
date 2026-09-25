"""Lane following and gap control. Vehicles execute ordinary pedal/steering inputs."""

import math
from dataclasses import dataclass, replace

from coastal_map import MapPoint, map_length, offset_point, point_at, project
from highway_curve import HighwayCurve
from highway_map import HIGHWAY_LENGTH, lane_x
from vehicle_response import steering_limit
from vehicle_state import Control

# Include the accepted player body and exposed tyres in clearance queries.
HALF_WIDTH = 0.95
HALF_LENGTH = 2.15


class Road:
    def __init__(self, track, *, seed=0, shape="straight"):
        self.track = track
        self.closed = track == "coastal"
        self.endless = track == "endless"
        self.length = map_length() if self.closed else HIGHWAY_LENGTH
        self.lanes = (-2.15, 2.15) if self.closed else tuple(lane_x(i) for i in range(3))
        self.curve = HighwayCurve(seed, hills=shape == "hills") if self.endless and shape != "straight" else None
        self.origin_y = 0.0

    def sample(self, distance, lane):
        return self.sample_lateral(distance, self.lanes[lane])

    def sample_lateral(self, distance, lateral):
        if self.curve:
            p = self.curve.sample(distance, lateral)
            return MapPoint(p.x, p.y - self.origin_y, p.z, p.heading, p.grade)
        if not self.closed:
            return MapPoint(lateral, distance, 0, 0, 0)
        point = point_at(distance)
        return MapPoint(*offset_point(point, lateral), point.heading, point.grade)

    def locate(self, car):
        x, y = car.position[:2]
        if self.curve:
            return self.curve.project((x, y + self.origin_y))
        if not self.closed:
            return y, x
        p, _, distance = project(x, y)
        angle = math.radians(p.heading)
        lateral = (x - p.x) * math.cos(angle) + (y - p.y) * math.sin(angle)
        return distance, lateral

    def delta(self, ahead, behind):
        value = ahead - behind
        return (value + self.length / 2) % self.length - self.length / 2 if self.closed else value

    def lane_frame(self, car, location=None):
        """Express sensing in road coordinates; never write this pose into physics."""
        distance, lateral = self.locate(car) if location is None else location
        p = self.sample_lateral(distance, 0)
        angle = math.radians(p.heading)
        velocity = car.velocity
        if velocity is not None:
            vx, vy, vz = velocity
            grade = math.radians(p.grade)
            tangent = -vx * math.sin(angle) + vy * math.cos(angle)
            velocity = (
                vx * math.cos(angle) + vy * math.sin(angle),
                tangent * math.cos(grade) + vz * math.sin(grade),
                vz,
            )
        return replace(car, position=(lateral, distance, car.position[2] - p.z),
                       heading=(car.heading - p.heading + 180) % 360 - 180, velocity=velocity)


def extents(heading, road_heading):
    angle = math.radians(heading - road_heading)
    sine, cosine = abs(math.sin(angle)), abs(math.cos(angle))
    return HALF_WIDTH * cosine + HALF_LENGTH * sine, HALF_LENGTH * cosine + HALF_WIDTH * sine


@dataclass
class Driver:
    lane: int
    cruise: float
    recovering: bool = False
    target_lateral: float | None = None

    def control(self, car, traffic, road, locations):
        distance, lateral = locations[0]
        p = road.sample(distance, self.lane)
        heading_error = (car.heading - p.heading + 180) % 360 - 180
        off_lane = abs(lateral - road.lanes[self.lane])
        if self.target_lateral is not None:
            off_lane = abs(lateral - self.target_lateral)
        # Severe impacts stop the car instead of dragging it sideways through traffic.
        if abs(heading_error) > 55 or off_lane > 2.8 or abs(car.roll) > 35:
            self.recovering = True
        if self.recovering:
            if (
                abs(car.speed) < 0.5
                and abs(heading_error) < 25
                and off_lane < 1.8
                and abs(car.roll) < 15
            ):
                self.recovering = False
            else:
                return Control(brake=1)
        lookahead = 5 + abs(car.speed) * 0.65
        target = road.sample(distance + lookahead, self.lane)
        if self.target_lateral is not None:
            target = road.sample_lateral(distance + lookahead, self.target_lateral)
        dx, dy = target.x - car.position[0], target.y - car.position[1]
        error = math.atan2(-dx, dy) - math.radians(car.heading)
        angle = math.degrees(math.atan2(4.4 * math.sin(error), math.hypot(dx, dy)))
        steering = max(-1, min(1, -angle / steering_limit(car.speed)))
        desired = self.cruise
        if not road.closed and not road.endless:
            # The finite preview ends here. Wait on the road until safe to recycle.
            desired = min(desired, math.sqrt(max(0, 4 * (road.length - 12 - distance))))
        for ahead in range(0, max(20, int(abs(car.speed) * 2)), 5):
            a, b = (
                road.sample(distance + ahead, self.lane),
                road.sample(distance + ahead + 8, self.lane),
            )
            curvature = abs(math.radians((b.heading - a.heading + 180) % 360 - 180)) / 8
            bend_speed = math.sqrt(2.5 / max(curvature, 0.001))
            desired = min(desired, math.sqrt(bend_speed**2 + 5 * ahead))
        own_width, own_length = extents(car.heading, p.heading)
        nearest_gap = math.inf
        lead_speed = desired
        for other, (other_distance, other_lateral) in zip(traffic, locations[1:]):
            if not other.active:
                continue
            delta = road.delta(other_distance, distance)
            other_width, other_length = extents(other.heading, p.heading)
            if delta <= 0 or abs(other_lateral - lateral) > own_width + other_width + 0.2:
                continue
            gap = delta - own_length - other_length
            if gap < nearest_gap:
                nearest_gap = gap
                lead_speed = max(0, other.speed * math.cos(math.radians(other.heading - p.heading)))
        # Comfortable stop gap plus a time gap; close quickly to slow traffic only when braking permits.
        if nearest_gap < math.inf:
            desired = min(
                desired,
                max(0, (nearest_gap - 3) / 1.6),
                math.sqrt(max(0, lead_speed**2 + 8 * (nearest_gap - 3))),
            )
        if desired < 0.3 and car.speed < 0.5:
            return Control(steering=steering, brake=1)
        error = desired - car.speed
        throttle = max(0, min(1, 0.35 + error * 0.22))
        brake = max(0, min(1, -error * 0.3)) if error < -0.5 else 0
        closing = max(0, car.speed - lead_speed)
        if nearest_gap < 3 + closing * 0.35 + closing * closing / 12:
            brake = 1
        return Control(steering=steering, throttle=0 if brake else throttle, brake=brake)
