"""从已完成试验记录计算工程指标；未满足工况条件时保留原因。"""

import math
from itertools import pairwise
from statistics import mean

VERSION = "coastal-engineering-metrics-v3"
WHEELS = ("fl", "fr", "rl", "rr")


def metric(key, label, unit, value, note, window=None):
    return {"key": key, "label": label, "unit": unit, "value": value,
            "status": "available" if value is not None else "unavailable",
            "note": note, "window": window}


def brake_start_index(rows,maneuver):
    """延迟制动取首次请求前的真实样本；原立即制动协议保留初样本。"""
    if maneuver!="ride_braking":
        return 0
    return next((index-1 for index,row in enumerate(rows[1:],1) if row["brake_request"]>0.),None)


def mfdd(rows, positions, maneuver, reason):
    """速度/路径交点线性插值，80%→10%区间内不能反向增速。"""
    invalid = lambda note: metric("mfdd", "充分发出平均减速度", "m/s²", None, note)
    if maneuver not in ("braking", "split_braking", "ride_braking"):
        return invalid("仅适用于制动工况")
    if reason in ("failed", "collision", "reset"):
        return invalid("试验异常终止，保留信号但不发布有效指标")
    reference = brake_start_index(rows,maneuver)
    if reference is None:
        return invalid("尚未施加制动请求")
    reference_time = rows[reference]["time"]
    rows,positions = rows[reference:],positions[reference:]
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
                  + ("；对开附着的曲线路径工程值，不作为直线制动合格结果" if maneuver == "split_braking" else "")
                  + ("；凸起研究工况，以制动请求前样本为基准，不作为平路制动合格结果" if maneuver=="ride_braking" else ""),
                  {"start_s": start[1], "end_s": end[1], "start_m": start[2], "end_m": end[2],
                   "start_speed_mps": .8*initial, "end_speed_mps": .1*initial,
                   "reference_time_s":reference_time,"reference_speed_mps":initial})


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
    # 原记录的刚体通道保持；新模型的制动距离/稳态速度取整车质量加权CG。
    motion_rows, positions = [], []
    for row, snapshot in zip(rows, snapshots, strict=True):
        state = snapshot.player.unsprung_state
        motion_rows.append({**row, "horizontal_speed": math.hypot(*state.total_center_velocity[:2])}
                           if state is not None else row)
        positions.append(state.total_center_position if state is not None else snapshot.player.position)
    results = [mfdd(motion_rows, positions, options["maneuver"], reason),
               yaw_gain(motion_rows, options["maneuver"], options["onset"], reason)]
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
    return {"version": VERSION, "metrics": results,
            "ride":ride_analysis(rows,snapshots,options,reason)}


def ride_analysis(rows, snapshots, options, reason):
    """单侧凸起的未加权运动与接地描述，不用ISO座椅舒适等级解释质心RMS。"""
    definitions = (("ride.body_rms","簧上垂向RMS","m/s²"),
                   ("ride.body_peak","簧上垂向峰值","m/s²"),
                   ("ride.hub_peak","轮心垂向峰值","m/s²"),
                   ("ride.max_travel","最大压缩行程","m"),
                   ("ride.unload_fraction","零轮荷采样比例","1"),
                   *((f"ride.min_load_{w}",f"最小施力轮荷 {w.upper()}","N") for w in WHEELS),
                   ("ride.load_cv_fl","FL动态轮荷比","1"))
    issue = ("需要实体凸起工况" if options["maneuver"] not in ("ride_bump","ride_braking") else
             "试验异常终止" if reason in ("failed","collision","reset") else
             "记录没有独立轮心观测" if any(s.player.unsprung_state is None for s in snapshots) else None)
    if issue is None:
        reached = [any(s.player.wheel_contacts[i].in_contact and s.player.wheel_contacts[i].contact_point[2]>0.
                       for s in snapshots) for i in (0,2)]
        if not all(reached):
            issue = "尚未完整刺激左前/左后轮，延长试验或调整初速/凸起距离"
    window = {"start_s":rows[0]["time"],"end_s":rows[-1]["time"],
              "basis":"全部已完成步；世界Z惯性加速度，未做频率加权"}
    if issue is not None:
        return {"metrics":[metric(key,label,unit,None,issue,window) for key,label,unit in definitions]}
    complete = rows[1:]
    body = [float(r["sprung_az"]) for r in complete if r["sprung_az"] is not None]
    hubs = [abs(float(r[f"hub_az_{w}"])) for r in complete for w in WHEELS if r[f"hub_az_{w}"] is not None]
    if not body or not hubs:
        return {"metrics":[metric(key,label,unit,None,"旧观测未保存加速度",window) for key,label,unit in definitions]}
    static = float(rows[0]["load_fl"])
    values = (math.sqrt(mean(v*v for v in body)),max(map(abs,body)),max(hubs),
              max(r[f"travel_{w}"] for r in complete for w in WHEELS),
              sum(r[f"load_{w}"]<=0. for r in complete for w in WHEELS)/(4*len(complete)),
              *(min(r[f"load_{w}"] for r in complete) for w in WHEELS),
              math.sqrt(mean((float(r["load_fl"])-static)**2 for r in complete))/static if static>0. else None)
    notes = ("簧上CG世界Z加速度RMS，未加权；不是座椅ISO舒适等级",
             "簧上CG世界Z惯性加速度绝对峰值", "四轮实际速度差的世界Z加速度绝对峰值",
             "实际轮心相对车身的压缩行程最大值", "四轮Fn=0的完成步占比；不是插值后的精确离地时长",
             *("末机械子步实际Fn最小值；负荷预算另按同阶段Fn计算" for _ in WHEELS),
             "sqrt(mean((Fn_FL−初始Fn_FL)^2))/初始Fn_FL，完整区间")
    return {"metrics":[metric(key,label,unit,float(value) if value is not None else None,note,window)
                       for (key,label,unit),value,note in zip(definitions,values,notes,strict=True)]}
