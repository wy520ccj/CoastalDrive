"""通用暖机汽油机耗油观察；只读已接受机械功，不向动力学反馈。"""

import math
from bisect import bisect_right
from dataclasses import dataclass

FUEL_MODEL_VERSION = 'warm-gasoline-design-v1'
ENERGY_PER_LITRE = 32_000_000.
SPEED_AXIS = (.15, .30, .50, .70, .90, 1.)
LOAD_AXIS = (0., .10, .25, .50, .75, 1., 1.20)
# 项目设计效率岛，非EPA/原厂实测数据；数值依据及适用边界见docs/challenge-energy.md。
EFFICIENCY = (
    (.10, .15, .21, .26, .28, .26, .23),
    (.12, .19, .26, .31, .33, .31, .28),
    (.12, .21, .28, .32, .34, .32, .29),
    (.11, .19, .26, .31, .32, .30, .27),
    (.10, .16, .22, .27, .28, .26, .24),
    (.09, .14, .20, .25, .26, .24, .22),
)
FUEL_STEP_COLUMNS = ('work_j', 'before_omega', 'after_omega', 'full_torque_nm', 'dt_s', 'coupled')


def _cell(axis, value):
    value = max(axis[0], min(axis[-1], value))
    index = min(len(axis)-2, max(0, bisect_right(axis, value)-1))
    return index, (value-axis[index])/(axis[index+1]-axis[index])


def fuel_efficiency(speed_fraction, load):
    row, y = _cell(SPEED_AXIS, speed_fraction)
    col, x = _cell(LOAD_AXIS, load)
    low = EFFICIENCY[row][col]*(1-x)+EFFICIENCY[row][col+1]*x
    high = EFFICIENCY[row+1][col]*(1-x)+EFFICIENCY[row+1][col+1]*x
    return low*(1-y)+high*y


@dataclass(frozen=True)
class FuelState:
    litres: float = 0.
    rate_lph: float = 0.
    cutoff: bool = False
    model: str = FUEL_MODEL_VERSION


class FuelMeter:
    def __init__(self, idle_rpm, redline_rpm):
        self.idle_rpm, self.redline_rpm = idle_rpm, redline_rpm
        self.litres = self.rate_lph = 0.
        self.cutoff = False
        self.samples = None

    def values(self):
        """子步数值包只传值，试算不能提前修改主世界的计量与原始样本。"""
        return {**self.__dict__, 'samples': None if self.samples is None else self.samples.copy()}

    @classmethod
    def from_values(cls, values):
        meter = cls(values['idle_rpm'], values['redline_rpm'])
        meter.__dict__.update(values)
        meter.samples = None if values['samples'] is None else values['samples'].copy()
        return meter

    def accept(self, work, before_omega, after_omega, full_torque, dt, *, coupled):
        if self.samples is not None:
            self.samples.append((work, before_omega, after_omega, full_torque, dt, coupled))
        # 燃烧主动功包含怠速补偿、离合损失与自由曲轴加速，不能只读轮端驱动功。
        omega = max(0., (before_omega+after_omega)/2)
        rpm = omega*60/math.tau
        positive_work = max(0., work)
        self.cutoff = positive_work == 0. and coupled and rpm > self.idle_rpm*1.35
        if rpm <= 0. or self.cutoff:
            self.rate_lph = 0.
            return
        load = positive_work / (max(omega*full_torque, 1e-12)*dt)
        efficiency = fuel_efficiency(rpm/self.redline_rpm, load)
        # 全域流率取空载下限和主动功供能中的较大者，不重复叠加怠速耗油。
        no_load_lph = .7+1.8*max(0., (rpm-self.idle_rpm)/(self.redline_rpm-self.idle_rpm))
        litres = max(no_load_lph*dt/3600, positive_work/(efficiency*ENERGY_PER_LITRE))
        self.litres += litres
        self.rate_lph = litres*3600/dt

    def snapshot(self):
        return FuelState(self.litres, self.rate_lph, self.cutoff)
