"""从已完成试验记录计算工程指标；未满足工况条件时保留原因。"""

import math
from itertools import pairwise
from statistics import mean

VERSION = "coastal-engineering-metrics-v1"
WHEELS = ("fl", "fr", "rl", "rr")


def metric(key, label, unit, value, note, window=None):
    return {"key": key, "label": label, "unit": unit, "value": value,
            "status": "available" if value is not None else "unavailable",
            "note": note, "window": window}


def mfdd(rows, positions, maneuver, reason):
    """速度/路径交点线性插值，80%→10%区间内不能反向增速。"""
    invalid = lambda note: metric("mfdd", "充分发出平均减速度", "m/s²", None, note)
    if maneuver not in ("braking", "split_braking"):
        return invalid("仅适用于制动工况")
    if reason in ("failed", "collision", "reset"):
        return invalid("试验异常终止，保留信号但不发布有效指标")
    initial = rows[0]["horizontal_speed"]
    if initial <= 1:
        return invalid("初速不足1m/s")
    distances = [0.]
    for previous, current in pairwise(positions):
        distances.append(distances[-1]+math.dist(previous[:2], current[:2]))
    crossings = []
    for ratio in (.8, .1):
        target = ratio*initial
        for index in range(1, len(rows)):
            before, after = rows[index-1]["horizontal_speed"], rows[index]["horizontal_speed"]
            if before > target >= after:
                fraction = (before-target)/(before-after)
                crossings.append((index, rows[index-1]["time"]+fraction*(rows[index]["time"]-rows[index-1]["time"]),
                                  distances[index-1]+fraction*(distances[index]-distances[index-1])))
                break
        else:
            return invalid(f"未达到{ratio:.0%}初速")
    start, end = crossings
    if end[0] <= start[0] or end[2] <= start[2]:
        return invalid("区间路径或采样点不足")
    if any(rows[i]["horizontal_speed"] > rows[i-1]["horizontal_speed"]+1e-6
           for i in range(start[0]+1, end[0]+1)):
        return invalid("80%→10%区间内存在增速，未形成连续制动区间")
    value = ((.8*initial)**2-(.1*initial)**2)/(2*(end[2]-start[2]))
    return metric("mfdd", "充分发出平均减速度", "m/s²", value,
                  "按水平路径距离平均，80%→10%初速交点线性插值；不等于减速度峰值"
                  + ("；对开附着的曲线路径工程值，不作为直线制动合格结果" if maneuver == "split_braking" else ""),
                  {"start_s": start[1], "end_s": end[1], "start_m": start[2], "end_m": end[2],
                   "start_speed_mps": .8*initial, "end_speed_mps": .1*initial})


def yaw_gain(rows, maneuver, onset, reason):
    invalid = lambda note, window=None: metric("yaw_gain", "稳态横摆增益", "1/s", None, note, window)
    if maneuver not in ("step_steer", "circle", "constant_radius"):
        return invalid("需要固定转角或定圆稳态工况")
    if reason in ("failed", "collision", "reset"):
        return invalid("试验异常终止")
    end = rows[-1]["time"]
    if end < onset+2:
        return invalid("需要转向开始至少2s，尾窗至少1s")
    tail = [row for row in rows if row["time"] >= end-1-1e-9]
    speed = mean(row["horizontal_speed"] for row in tail)
    delta = mean(math.radians(row["steering"]) for row in tail)
    right_yaw = mean(-row["yaw"] for row in tail)
    speed_span = max(row["horizontal_speed"] for row in tail)-min(row["horizontal_speed"] for row in tail)
    delta_span = math.radians(max(row["steering"] for row in tail)-min(row["steering"] for row in tail))
    yaw_span = max(row["yaw"] for row in tail)-min(row["yaw"] for row in tail)
    window = {"start_s": tail[0]["time"], "end_s": end, "mean_speed_mps": speed,
              "speed_span_mps": speed_span, "mean_roadwheel_angle_rad": delta,
              "angle_span_rad": delta_span, "mean_right_yaw_radps": right_yaw, "yaw_span_radps": yaw_span}
    if speed <= 1 or abs(delta) < math.radians(.1) or abs(right_yaw) < .005:
        return invalid("速度/实际转角/横摆响应不足", window)
    # 这些为本工作台的公开分析条件，不冒用法规或商业软件合格阈值。
    if speed_span > .02*speed or delta_span > max(math.radians(.02), .02*abs(delta)) or yaw_span > .05*abs(right_yaw):
        return invalid("尾窗未稳态：速度/转角峰峰变化须≤2%，横摆≤5%（角度绝对容差0.02°）", window)
    return metric("yaw_gain", "稳态横摆增益", "1/s", right_yaw/delta,
                  "右转为正：−世界z横摆率 / 实际中心前轮角；不是方向盘增益，也不是不足转向梯度", window)


def engineering_analysis(rows, snapshots, options, reason):
    results = [mfdd(rows, [state.player.position for state in snapshots], options["maneuver"], reason),
               yaw_gain(rows, options["maneuver"], options["onset"], reason)]
    for key, label, unit in (("beta", "峰值车身侧偏", "deg"), ("roll", "峰值车身侧倾", "deg"),
                             ("ltr_front", "峰值前轴左右轮荷差比", "1"), ("ltr_rear", "峰值后轴左右轮荷差比", "1")):
        values = [abs(row[key]) for row in rows if row[key] is not None]
        results.append(metric(key, label, unit, max(values) if values else None,
                              "已完成步记录的绝对峰值；轮荷差比是(R−L)/(R+L)，不作为翻车合格判据"))
    for wheel in WHEELS:
        values = [row[f"utilization_{wheel}"] for row in rows[1:] if row[f"utilization_{wheel}"] is not None]
        results.append(metric(f"utilization_{wheel}", f"峰值附着利用率 {wheel.upper()}", "1",
                              max(values) if values else None,
                              "末机械子步hypot(Fx,Fy)/同阶段D，不限幅；残差单独记录，离地未定义"))
    return {"version": VERSION, "metrics": results}
