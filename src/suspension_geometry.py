"""支撑包络的纯几何；实际世界查询和机械末姿态共用同一球/Box内核。"""

import math
from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class BoxSurface:
    """当前车身原点相对静态Box的局部坐标及变换；不持有世界或刚体。"""
    half: tuple
    radius: float
    axes: tuple
    offset: tuple
    wheel_radius: float
    reach: float

    def local(self, point):
        return tuple(self.offset[a] + sum(x*y for x,y in zip(self.axes[a], point)) for a in range(3))

    def world_vector(self, vector):
        return tuple(sum(vector[a] * self.axes[a][b] for a in range(3)) for b in range(3))


def box_interval(start, end, half):
    """三轴区间给出直线进入/离开Box的时刻及入射面。"""
    entry, exit_time, normal = float("-inf"), float("inf"), None
    for axis in range(3):
        speed = end[axis] - start[axis]
        if speed == 0.:
            if abs(start[axis]) > half[axis]:
                return None
            continue
        near, far = (-half[axis] - start[axis]) / speed, (half[axis] - start[axis]) / speed
        sign = -1. if speed > 0. else 1.
        if near > far:
            near, far = far, near
        if near > entry:
            entry, normal = near, tuple(sign if i == axis else 0. for i in range(3))
        exit_time = min(exit_time, far)
        if entry > exit_time:
            return None
    return entry, exit_time, normal


def box_entry(start, end, half):
    """有限线段入射；内部起点不伪造新的入射接触。"""
    interval = box_interval(start, end, half)
    return (interval[0], interval[2]) if interval is not None and 0. <= interval[0] <= 1. else None


def sphere_box_entry(start, end, half, radius):
    """Box与球的Minkowski包络：面/圆柱棱/球角均按真实距离求首个交点。"""
    interval = box_interval(start, end, tuple(h + radius for h in half))
    if interval is None:
        return None
    low, high = max(0., interval[0]), min(1., interval[1])
    if low > high or sum(max(abs(x) - h, 0.) ** 2 for x, h in zip(start, half)) < radius * radius:
        return None
    speed = tuple(b - a for a, b in zip(start, end))
    knots = {low, high}
    for axis in range(3):
        if speed[axis] != 0.:
            for bound in (-half[axis], half[axis]):
                crossing = (bound - start[axis]) / speed[axis]
                if low < crossing < high:
                    knots.add(crossing)
    for left, right in pairwise(sorted(knots)):
        middle = tuple(start[a] + (left + right) * speed[a] / 2 for a in range(3))
        axes = [a for a in range(3) if abs(middle[a]) > half[a]]
        offsets = {a: start[a] - math.copysign(half[a], middle[a]) for a in axes}
        quadratic = sum(speed[a] ** 2 for a in axes)
        if quadratic == 0.:
            continue
        linear = sum(offsets[a] * speed[a] for a in axes)
        constant = sum(value * value for value in offsets.values()) - radius * radius
        discriminant = linear * linear - quadratic * constant
        if discriminant < 0.:
            continue
        entry = (-linear - math.sqrt(discriminant)) / quadratic
        if left - 1e-12 <= entry <= right + 1e-12:
            center = tuple(start[a] + entry * speed[a] for a in range(3))
            difference = tuple(center[a] - max(-half[a], min(half[a], center[a])) for a in range(3))
            length = math.sqrt(sum(value * value for value in difference))
            return entry, tuple(value / length for value in difference)
    return None


