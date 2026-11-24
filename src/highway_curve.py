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
        self._signs = {}
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
        cached = self._signs.get(index)
        if cached is not None:
            return cached
        bits = _mix(self.seed ^ _mix(index))
        result = (-1 if bits & 1 else 1), (-1 if bits & 2 else 1)
        self._signs[index] = result
        return result

    # 道路参数在实例生命周期内固定，复用完全相同的采样；缓存有上限，不近似位置。
    def sample(self, distance, lateral=0):
        index = math.floor(distance / CELL_LENGTH)
        local = distance - index * CELL_LENGTH
        t = local / CELL_LENGTH
        side, hill = self.signs(index)
        b = bump(t)
        x = side * 60 * b
        z = self.base_height + hill * self.height * b
        row = int(local)
        if row >= CELL_LENGTH:
            row = CELL_LENGTH - 1
        fraction = local - row
        y_table = self.y_table
        y = index * self.advance + y_table[row] * (1 - fraction) + y_table[row + 1] * fraction
        d = slope(t)
        dx, dz = side * 60 * d, hill * self.height * d
        dy = math.sqrt(1 - dx * dx - dz * dz)
        horizontal = math.hypot(dx, dy)
        return MapPoint(
            x + lateral * dy / horizontal,
            y - lateral * dx / horizontal,
            z,
            math.degrees(math.atan2(-dx, dy)),
            math.degrees(math.atan2(dz, horizontal)),
        )

    def heading_at(self, distance):
        index = math.floor(distance / CELL_LENGTH)
        t = (distance - index * CELL_LENGTH) / CELL_LENGTH
        side, hill = self.signs(index)
        d = slope(t)
        dx, dz = side * 60 * d, hill * self.height * d
        dy = math.sqrt(1 - dx * dx - dz * dz)
        return math.degrees(math.atan2(-dx, dy))

    def distance_at_y(self, y):
        index = math.floor(y / self.advance)
        local_y = y - index * self.advance
        y_table = self.y_table
        row = bisect_right(y_table, local_y) - 1
        if row < 0:
            row = 0
        elif row >= CELL_LENGTH:
            row = CELL_LENGTH - 1
        y0 = y_table[row]
        fraction = (local_y - y0) / (y_table[row + 1] - y0)
        return index * CELL_LENGTH + row + fraction

    def on_asphalt(self, x, y):
        distance = self.distance_at_y(y)
        index = math.floor(distance / CELL_LENGTH)
        side, _ = self.signs(index)
        center_x = side * 60 * bump((distance - index * CELL_LENGTH) / CELL_LENGTH)
        # This centreline point has the same y. Its inner 6.5 m lies inside the road;
        # given max |dx/dy| < 0.211, points beyond 8.5 m in x cannot lie within 6.75 m laterally.
        offset = abs(x - center_x)
        if offset < 6.5:
            return True
        if offset > 8.5:
            return False
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
