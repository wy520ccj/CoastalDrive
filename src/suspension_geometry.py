"""支撑包络的纯几何；实际世界查询和机械末姿态共用有限表面。"""

import math
from dataclasses import dataclass
from itertools import pairwise

from wheel_contact_kernels import box_interval, surface_transform


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
        return surface_transform(point, self.axes, self.offset)

    def world_vector(self, vector):
        return surface_transform(vector, self.axes, transpose=True)


@dataclass(frozen=True)
class CylinderSurface(BoxSurface):
    """有限胎宽支持面；Box内核或解析Plane与末姿态共用同一入口。"""
    width: float
    shoulder: float
    wheel_axis: tuple
    plane: tuple | None = None
    crown: float = 0.
    triangles: object | None = None

    def relative_entry(self, start, end, axis):
        """输入和见证点保持车身相对坐标，避免先加大世界坐标再减回。"""
        found = self.entry(self.local(start), self.local(end), axis)
        if found is None:
            return None
        fraction, normal, point, face = found
        return fraction, self.world_vector(normal), self.world_vector(tuple(point[a] - self.offset[a] for a in range(3))), face

    def entry(self, start, end, axis):
        from wheel_envelope import cylinder_box_entry, cylinder_support
        local_axis = surface_transform(axis, self.axes)
        if self.triangles is not None:
            found = self.triangles.entry(start,end,self.radius,local_axis,self.wheel_radius,self.width,self.shoulder,self.crown)
        elif self.plane is None:
            found = cylinder_box_entry(start, end, self.half, self.radius, local_axis,
                                       self.wheel_radius, self.width / 2, self.shoulder, self.crown)
        else:
            normal, constant = self.plane
            extent = cylinder_support(normal, local_axis, self.wheel_radius, self.width / 2, self.shoulder, self.crown)
            distance = sum(n * (x - y) for n, x, y in zip(normal, start, extent)) - constant
            speed = sum(n * (y - x) for n, x, y in zip(normal, start, end))
            if speed >= 0. or distance < 0. or distance + speed > 0.:
                return None
            fraction = -distance / speed
            point = tuple(start[i] + fraction * (end[i] - start[i]) - extent[i] for i in range(3))
            squared = sum(n*n for n in normal)
            found = fraction, normal, point, (tuple(constant*n/squared for n in normal), 0.)
        if found is None:
            return None
        fraction, normal, point, face = found
        # 面锚点相对本子步车身原点，避免末姿态查询把固定平面重新舍入为移动接点。
        if face is not None:
            anchor, margin = face
            face = self.world_vector(tuple(anchor[a] - self.offset[a] for a in range(3))), margin
        return fraction, normal, point, face




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


