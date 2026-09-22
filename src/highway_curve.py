"""Seeded arc-length geometry for curved and hilly endless roads."""

import math
from bisect import bisect_right

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

    def forward_slope(self, t):
        d = slope(t)
        return math.sqrt(1 - (60 * d)**2 - (self.height * d)**2)

    def signs(self, index):
        bits = _mix(self.seed ^ _mix(index))
        return (-1 if bits & 1 else 1), (-1 if bits & 2 else 1)

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

    def project(self, position):
        """Nearest centreline in plan view, returning arc distance and lateral offset."""
        x, y = position[:2]
        index = math.floor(y / self.advance)
        local_y = y - index * self.advance
        row = max(0, min(CELL_LENGTH - 1, bisect_right(self.y_table, local_y) - 1))
        fraction = (local_y - self.y_table[row]) / (self.y_table[row + 1] - self.y_table[row])
        distance = index * CELL_LENGTH + row + fraction
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
