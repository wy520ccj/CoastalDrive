"""轮心—部件安装位移的保单调三次曲线；只缓存不可变几何，不积分车辆状态。"""

import math
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise


@dataclass(frozen=True)
class InstallationAxis:
    q: tuple
    displacement: tuple
    slopes: tuple
    reference_ratio: float

    def at(self, position):
        """返回位移、运动比及其梯度；区间外明确采用端点切线线性外推。"""
        q,x,m = self.q,self.displacement,self.slopes
        if position<q[0] or position>q[-1]:
            end = 0 if position<q[0] else -1
            return x[end]+m[end]*(position-q[end]),m[end],0.
        i = min(bisect_right(q,position)-1,len(q)-2)
        h,t = q[i+1]-q[i],position-q[i]
        secant = (x[i+1]-x[i])/h
        cubic = (m[i]+m[i+1]-2*secant)/(h*h)
        square = (3*secant-2*m[i]-m[i+1])/h
        return (x[i]+t*(m[i]+t*(square+t*cubic)),
                m[i]+t*(2*square+3*t*cubic),2*square+6*t*cubic)


def _axis(q, positions):
    h = [b-a for a,b in pairwise(q)]
    delta = [(b-a)/step for a,b,step in zip(positions[:-1],positions[1:],h,strict=True)]
    slopes = [max(0.,((2*h[0]+h[1])*delta[0]-h[0]*delta[1])/(h[0]+h[1]))]
    for i in range(1,len(q)-1):
        w1,w2 = 2*h[i]+h[i-1],h[i]+2*h[i-1]
        slopes.append((w1+w2)/(w1/delta[i-1]+w2/delta[i]))
    slopes.append(max(0.,((2*h[-1]+h[-2])*delta[-1]-h[-1]*delta[-2])/(h[-1]+h[-2])))
    return InstallationAxis(q,positions,tuple(slopes),slopes[q.index(0.)])


@lru_cache(maxsize=32)
def installation_curve(rows):
    """文件/配置边界验证后构造两条PCHIP；q=0为内部锚点，位移增量必须为零。"""
    if len(rows)<3 or any(len(row)!=3 for row in rows):
        raise ValueError("安装曲线至少三行，每行为轮心行程/弹簧位移增量/减振器位移增量m")
    if any(isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) for row in rows for value in row):
        raise ValueError("安装曲线各坐标须为有限数m")
    if any(any(b[i]<=a[i] for i in range(3)) for a,b in pairwise(rows)):
        raise ValueError("当前安装曲线须按轮心行程递增，两部件位移均严格递增")
    q,spring,damper = (tuple(row[i] for row in rows) for i in range(3))
    if not q[0]<0.<q[-1] or 0. not in q or rows[q.index(0.)][1:]!=(0.,0.):
        raise ValueError("安装曲线须含内部锚点(0,0,0)，并覆盖正负轮心行程")
    return _axis(q,spring),_axis(q,damper)
