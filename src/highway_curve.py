"""Seeded arc-length geometry for curved and hilly endless roads."""

import math
from bisect import bisect_right
from functools import lru_cache

from coastal_map import MapPoint
from highway_segments import _mix

CELL_LENGTH = 1000


def bump(t):
    return 64 * t**3 * (1 - t)**3


def slope(t):
    return 192 * t**2 * (1 - t)**2 * (1 - 2 * t) / CELL_LENGTH


class HighwayCurve:
    def __init__(self, seed=0, *, hills=False):
        self.seed = seed
        self.height = 12 if hills else 0
        self.base_height = 16 if hills else 0
        self.y_table = [0.0]
        previous = self.forward_slope(0)
        for s in range(1, CELL_LENGTH + 1):
            current = self.forward_slope(s / CELL_LENGTH)
            self.y_table.append(self.y_table[-1] + (previous + current) / 2)
            previous = current
        self.advance = self.y_table[-1]
        # 缓存随道路实例释放，避免类级缓存保留历史场景。
        self.sample = lru_cache(maxsize=8192)(self.sample)

    def forward_slope(self, t):
        d = slope(t)
        return math.sqrt(1 - (60 * d)**2 - (self.height * d)**2)

    def signs(self, index):
        bits = _mix(self.seed ^ _mix(index))
        return (-1 if bits & 1 else 1), (-1 if bits & 2 else 1)

    # 道路参数在实例生命周期内固定，复用完全相同的采样；缓存有上限，不近似位置。
    def sample(self, distance, lateral=0):
        index = math.floor(distance / CELL_LENGTH)
        local = distance - index * CELL_LENGTH
        t = local / CELL_LENGTH
        side, hill = self.signs(index)
        x = side * 60 * bump(t)
        z = self.base_height + hill * self.height * bump(t)
        row = min(int(local), CELL_LENGTH - 1)
        fraction = local - row
        y = index * self.advance + self.y_table[row] * (1 - fraction) + self.y_table[row + 1] * fraction
        dx, dz = side * 60 * slope(t), hill * self.height * slope(t)
        dy = self.forward_slope(t)
        horizontal = math.hypot(dx, dy)
        return MapPoint(
            x + lateral * dy / horizontal,
            y - lateral * dx / horizontal,
            z,
            math.degrees(math.atan2(-dx, dy)),
            math.degrees(math.atan2(dz, horizontal)),
        )

    def distance_at_y(self, y):
        index = math.floor(y / self.advance)
        local_y = y - index * self.advance
        row = max(0, min(CELL_LENGTH - 1, bisect_right(self.y_table, local_y) - 1))
        fraction = (local_y - self.y_table[row]) / (self.y_table[row + 1] - self.y_table[row])
        return index * CELL_LENGTH + row + fraction

    def on_asphalt(self, x, y):
        distance = self.distance_at_y(y)
        index = math.floor(distance / CELL_LENGTH)
        side, _ = self.signs(index)
        center_x = side * 60 * bump((distance - index * CELL_LENGTH) / CELL_LENGTH)
        # This centreline point has the same y. Its inner 6.5 m lies inside the road.
        if abs(x - center_x) < 6.5:
            return True
        return abs(self.project((x, y))[1]) <= 6.75

    def project(self, position):
        """Nearest centreline in plan view, returning arc distance and lateral offset."""
        x, y = position[:2]
        distance = self.distance_at_y(y)
        for _ in range(8):
            p = self.sample(distance)
            heading, grade = math.radians(p.heading), math.radians(p.grade)
            tx, ty = -math.sin(heading), math.cos(heading)
            correction = ((x - p.x) * tx + (y - p.y) * ty) / math.cos(grade)
            distance += correction
            if abs(correction) < 1e-8:
                break
        p = self.sample(distance)
        heading = math.radians(p.heading)
        lateral = (x - p.x) * math.cos(heading) + (y - p.y) * math.sin(heading)
        return distance, lateral
