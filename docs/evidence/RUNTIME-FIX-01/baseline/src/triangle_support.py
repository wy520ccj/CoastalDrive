"""道路三角网格的静态几何索引和有限胎宽首次接触。"""

from dataclasses import dataclass, field

from wheel_contact_kernels import (
    triangle_face,
    triangle_support_coefficients,
    triangle_support_entry,
    triangle_support_window,
)

from suspension_geometry import box_interval
from wheel_envelope import cylinder_support, subtract, triangle_edge_entry


def triangle_entry(start, end, triangle, margin, axis, radius, width, shoulder, crown, *, face_only=False, ceiling=1., padding=None,
                   face_checked=False):
    # 原生阶段只处理支持平面和有限面；实际边/角仍进入原凸体距离求解。
    if not face_checked:
        finished, hit = triangle_face(start, end, triangle, margin, axis, radius, width, shoulder, crown,
                                      face_only=face_only, ceiling=ceiling)
        if finished:
            return hit
    if padding is None:
        padding = tuple(cylinder_support(tuple(float(a == i) for a in range(3)),axis,radius,width/2,shoulder,crown)[i]
                        + margin for i in range(3))
    return triangle_edge_entry(start, end, triangle, margin, axis, radius, width, shoulder, crown, ceiling, padding)


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
        # 原生数值只复用本节点不可变几何；公开三角面和子节点仍为原对象。
        object.__setattr__(self, "_native", triangle_support_coefficients(
            self.center, self.half, self.triangles, self.triangle_bounds, tuple(child._native for child in self.children)))

    def __reduce__(self):
        """进程只交换不可变网格数值；各进程自行重建原生只读索引。"""
        return type(self), (self.low, self.high, self.triangles, self.children)

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

    def window(self, start, end, padding):
        """保留原索引遍历顺序与整根边界；原生窗口复用已计算的三角面几何。"""
        triangles, bounds, native = triangle_support_window(self._native, start, end, padding)
        result = TriangleSupport.__new__(TriangleSupport)
        for name, value in (('low', self.low), ('high', self.high), ('center', self.center),
                            ('half', self.half), ('triangles', triangles), ('children', ()),
                            ('triangle_bounds', bounds), ('_native', native)):
            object.__setattr__(result, name, value)
        return result

    def entry(self, start, end, margin, axis, radius, width, shoulder, crown):
        return triangle_support_entry(self._native, start, end, margin, axis, radius, width, shoulder, crown, triangle_entry)
