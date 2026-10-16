"""试验台数值输入边界；错误携带字段，供界面定位而不猜测异常文本。"""

import math

from vehicle_state import FIXED_DT

FIELDS = {
    "speed": ("初速", "km/h", 0., 200.),
    "mu": ("路面附着系数", "", .1, 2.),
    "duration": ("时长", "s", FIXED_DT, 60.),
    "steer": ("目标转角", "°", -90., 90.),
    "onset": ("输入起始", "s", 0., 60.),
    "radius": ("定圆半径", "m", 15., 150.),
    "right_mu": ("右侧附着系数", "", .1, 2.),
    "bump_height": ("凸起高度", "m", .001, .05),
    "bump_length": ("凸起长度", "m", .1, 5.),
    "bump_distance": ("凸起距离", "m", 2., 100.),
    "cg": ("质心高度", "m", .2, 1.),
    "tire_load": ("轮胎基准轮荷", "N", 0., math.inf),
    "manual.throttle": ("油门", "%", 0., 100.),
    "manual.brake": ("制动", "%", 0., 100.),
    "manual.clutch": ("离合", "%", 0., 100.),
    "manual.gear": ("挡位", "", -1., 20.),
}


class LabInputError(ValueError):
    def __init__(self, key, message):
        super().__init__(message)
        self.key = key


def validate_number(key, value, *, bounds=None):
    name, unit, low, high = FIELDS[key]
    if bounds is not None:
        low, high = bounds
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise LabInputError(key, f"{name}须为有限数字，不能填写空值、无穷大或非数字。")
    if key == "tire_load" and value <= 0:
        raise LabInputError(key, "轮胎基准轮荷须大于0 N；留空采用车型值。")
    if not low <= value <= high:
        raise LabInputError(key, f"{name}须在 {low:.8g}～{high:.8g} {unit} 范围内。")
    if key == "manual.gear" and value != int(value):
        raise LabInputError(key, "挡位须填写整数：倒挡=-1，空挡=0，前进挡=1、2……")
    return value


def read_number(text, key, *, bounds=None, optional=False):
    text = text.strip()
    if not text:
        if optional:
            return None
        raise LabInputError(key, f"{FIELDS[key][0]}不能为空，请填写数字。")
    try:
        value = float(text)
    except ValueError as error:
        raise LabInputError(key, f"{FIELDS[key][0]}须填写数字，不能包含字母或其他字符。") from error
    return validate_number(key, value, bounds=bounds)
