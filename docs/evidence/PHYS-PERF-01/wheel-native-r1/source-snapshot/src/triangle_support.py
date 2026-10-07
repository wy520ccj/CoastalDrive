"""道路三角网格的静态几何索引和有限胎宽首次接触。"""

import math
from dataclasses import dataclass, field

from wheel_contact_kernels import triangle_face

from rotor_dynamics import dot
from suspension_geometry import box_interval
from wheel_envelope import convex_distance, cylinder_support, subtract


def clipped_triangle(triangle, start, end, padding):
    """只保留扫掠外廓可能触及的原三角面，缩短大网格边的凸体距离尺度。"""
    polygon = list(triangle)
    for axis in range(3):
        for sign, bound in ((1., min(start[axis],end[axis])-padding[axis]),
                            (-1., max(start[axis],end[axis])+padding[axis])):
            result = []
            for a,b in zip(polygon,polygon[1:]+polygon[:1]):
                da, db = sign*(a[axis]-bound), sign*(b[axis]-bound)
                if da >= 0.:
                    result.append(a)
                if (da >= 0.) != (db >= 0.):
                    fraction = da / (da-db)
                    point = tuple(math.fma(fraction,b[i]-a[i],a[i]) if i != axis else bound for i in range(3))
                    result.append(point)
            polygon = result
    return polygon


def triangle_entry(start, end, triangle, margin, axis, radius, width, shoulder, crown, *, face_only=False, ceiling=1.):
    # 原生阶段只处理支持平面和有限面；实际边/角仍进入原凸体距离求解。
    finished, hit = triangle_face(start, end, triangle, margin, axis, radius, width, shoulder, crown,
                                  face_only=face_only, ceiling=ceiling)
    if finished:
        return hit
    velocity = subtract(end, start)
    padding = tuple(cylinder_support(tuple(float(a == i) for a in range(3)),axis,radius,width/2,shoulder,crown)[i]
                    + margin for i in range(3))
    polygon = clipped_triangle(triangle,start,end,padding)
    if not polygon:
        return None

    def support(direction):
        return max(polygon, key=lambda p: dot(p, direction))

    fraction = 0.
    for _ in range(64):
        center = tuple(start[i] + fraction * velocity[i] for i in range(3))
        distance, normal, witness = convex_distance(center, axis, support, radius, width / 2, shoulder, crown)
        gap = distance - margin - shoulder
        if fraction == 0. and gap < -1e-9:
            return None
        if gap <= 1e-9:
            return fraction, normal, tuple(witness[i] + margin * normal[i] for i in range(3)), None
        closing = -dot(normal, velocity)
        if closing <= 0.:
            return None
        fraction += gap / closing
        if fraction > ceiling:
            return None
    raise ArithmeticError("圆柱/三角形悬架扫掠未收敛")


@dataclass(frozen=True)
class TriangleSupport:
    """按真实三角形AABB建立的二叉索引；只在道路生成时构造。"""
    low: tuple
    high: tuple
    triangles: tuple = ()
    children: tuple = ()
    center: tuple = field(init=False)
    half: tuple = field(init=False)
    triangle_bounds: tuple = field(init=False)

    def __post_init__(self):
        # 道路生成后几何固定；查询只为这些原包围盒加轮胎外廓。
        object.__setattr__(self, "center", tuple((a+b)/2 for a,b in zip(self.low,self.high)))
        object.__setattr__(self, "half", tuple((b-a)/2 for a,b in zip(self.low,self.high)))
        bounds = []
        for triangle in self.triangles:
            low = tuple(min(p[i] for p in triangle) for i in range(3))
            high = tuple(max(p[i] for p in triangle) for i in range(3))
            bounds.append((tuple((a+b)/2 for a,b in zip(low,high)),
                           tuple((b-a)/2 for a,b in zip(low,high))))
        object.__setattr__(self, "triangle_bounds", tuple(bounds))

    @classmethod
    def build(cls, triangles):
        triangles = tuple(tuple(tuple(p) for p in triangle) for triangle in triangles)
        points = tuple(p for triangle in triangles for p in triangle)
        low = tuple(min(p[i] for p in points) for i in range(3))
        high = tuple(max(p[i] for p in points) for i in range(3))
        if len(triangles) <= 8:
            return cls(low, high, triangles)
        axis = max(range(3), key=lambda i: high[i] - low[i])
        ordered = sorted(triangles, key=lambda triangle: sum(p[axis] for p in triangle))
        middle = len(ordered) // 2
        return cls(low, high, children=(cls.build(ordered[:middle]), cls.build(ordered[middle:])))

    def candidates(self, start, end, padding):
        center = self.center
        half = tuple(value + padding[i] for i,value in enumerate(self.half))
        interval = box_interval(subtract(start, center), subtract(end, center), half)
        if interval is None or interval[0] > 1. or interval[1] < 0.:
            return
        for child in self.children:
            yield from child.candidates(start,end,padding)
        for triangle, (center, base_half) in zip(self.triangles, self.triangle_bounds):
            half = tuple(value + padding[i] for i,value in enumerate(base_half))
            interval = box_interval(subtract(start,center),subtract(end,center),half)
            if interval is None or interval[0] > 1. or interval[1] < 0.:
                continue
            yield triangle

    def entry(self, start, end, margin, axis, radius, width, shoulder, crown):
        hits, curved = [], []
        padding = tuple(cylinder_support(tuple(float(a == i) for a in range(3)),axis,radius,width/2,shoulder,crown)[i]
                        + margin for i in range(3))
        for triangle in self.candidates(start,end,padding):
            hit = triangle_entry(start,end,triangle,margin,axis,radius,width,shoulder,crown,face_only=True)
            if hit is not None:
                hits.append(hit)
            else:
                curved.append(triangle)
        ceiling = min((hit[0] for hit in hits),default=1.)
        for triangle in curved:
            hit = triangle_entry(start,end,triangle,margin,axis,radius,width,shoulder,crown,ceiling=ceiling)
            if hit is not None:
                hits.append(hit)
                ceiling = min(ceiling,hit[0])
        return min(hits,key=lambda hit: hit[0]) if hits else None
