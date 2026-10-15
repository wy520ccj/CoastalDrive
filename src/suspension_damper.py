"""无记忆被动减振器力速表；插值/外推保留耗散符号，不表示液压迟滞。"""

import math
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise


@dataclass(frozen=True)
class DamperCurve:
    speed: tuple
    force: tuple

    def at(self, velocity):
        """节点间线性插值；域外沿端段斜率延续，不钳制速度。"""
        i=min(max(bisect_right(self.speed,velocity)-1,0),len(self.speed)-2)
        slope=(self.force[i+1]-self.force[i])/(self.speed[i+1]-self.speed[i])
        return self.force[i]+slope*(velocity-self.speed[i]),slope


@lru_cache(maxsize=32)
def damper_curve(rows):
    if len(rows)<7 or any(len(row)!=2 for row in rows):
        raise ValueError("减振器力速表须至少七行(速度m/s,本构阻力N)")
    if any(isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)
           for row in rows for value in row):
        raise ValueError("减振器力速坐标须为有限数")
    if any(b[0]<=a[0] or b[1]<a[1] for a,b in pairwise(rows)):
        raise ValueError("当前被动力速表须速度严格递增、阻力非递减；拒绝非单调拟合")
    speed,force=(tuple(row[i] for row in rows) for i in range(2))
    if (0.,0.) not in rows or sum(v<0. for v in speed)<3 or sum(v>0. for v in speed)<3:
        raise ValueError("力速表须含(0,0)，正负方向均至少三个非零速度")
    if any(v*f<0. for v,f in rows):
        raise ValueError("本构阻力须与速度同号，不能向被动端口注入能量")
    return DamperCurve(speed,force)
