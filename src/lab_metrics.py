"""从已完成试验记录计算工程指标；未满足工况条件时保留原因。"""

import math
from dataclasses import replace
from itertools import pairwise
from statistics import mean

from iso_ride import rough_road_ride_analysis
from lab_maneuvers import CIRCLE_BRAKING_MANEUVERS
from theory_baselines import (
    braking_curves,
    constant_speed_fuel_curve,
    fit_quasi_steady_understeer,
    linear_handling_baseline,
    power_balance_curves,
    theoretical_stop_distance,
)
from vehicle_designs import vehicle_design

VERSION = "coastal-engineering-metrics-v3"
WHEELS = ("fl", "fr", "rl", "rr")
NEW_BRAKING_MANEUVERS = (*CIRCLE_BRAKING_MANEUVERS, "step_steer_braking")
DELAYED_BRAKING_MANEUVERS = ("ride_braking", *NEW_BRAKING_MANEUVERS)
BRAKING_MANEUVERS = ("braking", "split_braking", *DELAYED_BRAKING_MANEUVERS)


def metric(key, label, unit, value, note, window=None):
    return {"key": key, "label": label, "unit": unit, "value": value,
            "status": "available" if value is not None else "unavailable",
            "note": note, "window": window}


def brake_start_index(rows,maneuver):
    """延迟制动取首次请求前的真实样本；原立即制动协议保留初样本。"""
    if maneuver not in DELAYED_BRAKING_MANEUVERS:
        return 0
    return next((index-1 for index,row in enumerate(rows[1:],1) if row["brake_request"]>0.),None)


def mfdd(rows, positions, maneuver, reason):
    """速度/路径交点线性插值，80%→10%区间内不能反向增速。"""
    invalid = lambda note: metric("mfdd", "充分发出平均减速度", "m/s²", None, note)
    if maneuver not in BRAKING_MANEUVERS:
        return invalid("仅适用于制动工况")
    if reason in ("failed", "collision", "reset"):
        return invalid("试验异常终止，无有效统计指标")
    reference = brake_start_index(rows,maneuver)
    if reference is None:
        return invalid("尚未施加制动请求")
    reference_time = rows[reference]["time"]
    rows,positions = rows[reference:],positions[reference:]
    initial = rows[0]["horizontal_speed"]
    if initial <= 1:
        return invalid("初速不足 1 m/s")
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
            return invalid(f"未达到 {ratio:.0%} 初速")
    start, end = crossings
    if end[0] <= start[0] or end[2] <= start[2]:
        return invalid("区间路径或采样点不足")
    if any(rows[i]["horizontal_speed"] > rows[i-1]["horizontal_speed"]+1e-6
           for i in range(start[0]+1, end[0]+1)):
        return invalid("80%–10% 初速区间内存在增速，未构成连续制动过程")
    value = ((.8*initial)**2-(.1*initial)**2)/(2*(end[2]-start[2]))
    return metric("mfdd", "充分发出平均减速度", "m/s²", value,
                  "按水平路径距离计算的 80%–10% 初速区间平均减速度"
                  + ("（对开附着弯道路径）" if maneuver == "split_braking" else "")
                  + ("（凸起路面工况，以制动请求前瞬时速度为基准）" if maneuver=="ride_braking" else ""),
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
        return invalid("末 1 s 窗口未达稳态：车速与转角峰峰波动须 ≤ 2%，横摆角速度 ≤ 5%（转角绝对容差 0.02°）", window)
    return metric("yaw_gain", "稳态横摆增益", "1/s", right_yaw/delta,
                  "右转为正：世界 Z 轴横摆角速度与实际中心前轮转角之比（rad/s / rad）", window)


def cg_motion(player):
    """取整车质心位置与速度，兼容刚体和独立轮心模型。"""
    state = player.unsprung_state
    if state is None:
        return player.position, player.velocity
    return state.total_center_position, state.total_center_velocity


def _finite(value):
    return float(value) if value is not None and math.isfinite(value) else None


def _resolve_config(options, config):
    if config is not None:
        return config
    resolved = vehicle_design(options.get("vehicle_id", "reference-rwd")).config
    if options.get("friction") is not None:
        resolved = replace(resolved, road_friction=float(options["friction"]))
    if options.get("cg_height") is not None:
        resolved = replace(resolved, center_of_mass_height=float(options["cg_height"]))
    if options.get("tire_reference_load") is not None:
        resolved = replace(resolved, tire_reference_load=float(options["tire_reference_load"]))
    return resolved


def iso_ride_analysis(snapshots, options, reason, config):
    """ISO 8608 随机路面下的 ISO 2631-1 Wk 加权平顺性与频谱分析。"""
    definitions = (
        ("iso.awz_rms", "Wk 加权垂向加速度 RMS", "m/s²"),
        ("iso.unweighted_rms", "未加权垂向加速度 RMS", "m/s²"),
        ("iso.sprung_peak_hz", "车身偏频主峰", "Hz"),
        ("iso.unsprung_peak_hz", "车轮跳动频峰", "Hz"),
        ("iso.dynamic_load_fl", "FL 相对动载", "1"),
        ("iso.travel_rms_mm", "悬架动挠度 RMS", "mm"),
    )
    issue = (
        "需要标准等级随机路面工况（iso_rough_road）"
        if options.get("maneuver") != "iso_rough_road"
        else "试验异常终止" if reason in ("failed", "collision", "reset")
        else None
    )
    if issue is not None:
        return {
            "metrics": [metric(key, label, unit, None, issue) for key, label, unit in definitions],
            "discomfort_level": None,
            "notes": issue,
        }
    result = rough_road_ride_analysis(snapshots, config)
    if result["status"] != "available":
        return {
            "metrics": [metric(key, label, unit, None, result["note"]) for key, label, unit in definitions],
            "discomfort_level": None,
            "notes": result["note"],
        }
    level = result["discomfort_level"]
    values = (
        _finite(result["awz_rms_mps2"]),
        _finite(result["unweighted_az_rms_mps2"]),
        _finite(result["sprung_peak_hz"]),
        _finite(result["unsprung_peak_hz"]),
        _finite(result["dynamic_load_ratio_fl"]),
        _finite(result["suspension_travel_rms_mm"]),
    )
    notes_list = (
        f"ISO 2631-1 Wk 加权均方根，主观舒适度：{level}",
        "跳过起步瞬态后的簧上垂向加速度标准差，未加权",
        "Welch PSD 在 0.5–4.0 Hz 簧载频段主峰值频率",
        "6.0–25.0 Hz 非簧载轮跳主峰（未启用独立轮心时无轮心加速度）"
        if result["unsprung_peak_hz"] is None
        else "Welch PSD 在 6.0–25.0 Hz 非簧载频段轮跳主峰",
        "左前轮法向力标准差 σ_Fd 与初始静载 G0 之比",
        "左前轮悬架压缩行程波动均方根（mm）",
    )
    extra = "；当前为刚体悬架，未输出非簧载轮跳频峰" if result["unsprung_peak_hz"] is None else ""
    return {
        "metrics": [
            metric(key, label, unit, value, note)
            for (key, label, unit), value, note in zip(definitions, values, notes_list, strict=True)
        ],
        "discomfort_level": level,
        "notes": f"{result['note']}；主观舒适度分级：{level}{extra}。",
    }


def theory_analysis(motion_rows, options, reason, config):
    """汇总《汽车理论》动力/经济/制动/二自由度操稳解析基线及准稳态扫点对账。"""
    pb = power_balance_curves(config)
    fuel = constant_speed_fuel_curve(config)
    mu = float(options.get("friction", config.road_friction))
    cfg_mu = replace(config, road_friction=mu) if mu != config.road_friction else config
    bc = braking_curves(cfg_mu)
    eff_at_mu = braking_curves(cfg_mu, phi_grid=(mu,))["efficiency"][0]
    hb = linear_handling_baseline(config)

    maneuver = options.get("maneuver")
    abs_flag = bool(options.get("abs_enabled", config.braking.abs_enabled)) or (
        options.get("controller_mode") == "coord_abs_dyc"
    )
    stop_speed_kph = (
        float(options["speed_kph"])
        if maneuver in BRAKING_MANEUVERS and float(options.get("speed_kph", 0.0)) > 0.0
        else 100.0
    )
    stop_dist = theoretical_stop_distance(stop_speed_kph, mu, cfg_mu, abs_enabled=abs_flag)
    us = (
        fit_quasi_steady_understeer(motion_rows, config, radius_m=options.get("radius_m"))
        if maneuver == "quasi_steady_circle" and reason not in ("failed", "collision", "reset")
        else None
    )

    max_grade_drive = pb["max_grade_1st_drive"]
    max_grade_adhesion = pb["max_grade_1st_adhesion"]
    max_grade_pct = _finite(min(max_grade_drive, max_grade_adhesion) * 100.0)
    k_sim = _finite(us["K_sim_deg_per_g"]) if us is not None else None
    k_delta = _finite(us["K_delta_deg_per_g"]) if us is not None else None
    qs_note = (
        us["note"] if us is not None
        else "需准稳态定圆扫点工况（quasi_steady_circle）且无异常终止"
    )

    items = (
        ("theory.vmax", "理论最高车速", "km/h", _finite(pb["v_max_kph"]),
         "最高挡驱动力与滚动/空气阻力平衡车速（超红线则截断到红线车速）"),
        ("theory.time_0_100", "理论 0–100 加速", "s", _finite(pb["time_0_100_s"]),
         "平路全油门理想换挡数值积分，含旋转质量换算系数 δ"),
        ("theory.max_grade", "1 挡最大爬坡度", "%", max_grade_pct,
         f"取 1 挡动力极限({max_grade_drive * 100:.1f}%)与附着极限({max_grade_adhesion * 100:.1f}%)较小值"),
        ("theory.phi0", "同步附着系数 φ0", "1", _finite(bc["phi_0"]),
         f"φ0=(Lβ−b)/hg；当前 μ={mu:.2f} 先抱死轴：{bc['first_lock_axle']}"),
        ("theory.brake_eff", "当前 μ 制动效率", "1", _finite(eff_at_mu),
         f"按固定制动力分配 β={bc['beta']:.2f} 在 μ={mu:.2f} 下的理论效率"),
        ("theory.stop_dist", "理论制动距离", "m", _finite(stop_dist),
         f"初速 {stop_speed_kph:g} km/h、μ={mu:.2f}、{'开启' if abs_flag else '关闭'}ABS 且计入滞后 τb"),
        ("theory.k_lin", "理论不足转向度 K_lin", "deg/g", _finite(hb["K_deg_per_g"]),
         "二自由度线性单轨理论（含已启用的悬架 K&C 跳动前束与外倾增量）"),
        ("theory.u_ch", "特征车速 u_ch", "km/h", _finite(hb["u_ch_kph"]),
         "仅 K_lin>0 时存在；对应横摆角速度增益最大值车速"),
        ("theory.k_sim", "扫点实算 K_sim", "deg/g", k_sim, qs_note),
        ("theory.k_delta", "实算与理论差 ΔK", "deg/g", k_delta,
         f"K_sim − K_lin；R²={us['r2']:.4f}" if us is not None and us["r2"] is not None else qs_note),
    )
    metrics_list = [metric(key, label, unit, val, note) for key, label, unit, val, note in items]

    pb_clean = {**pb, "max_grade_1st_drive": _finite(max_grade_drive)}
    bc_clean = {**bc, "stop_distance_100kph_m": _finite(bc["stop_distance_100kph_m"])}
    lock_label = {"front": "前轴先抱死", "rear": "后轴先抱死", "simultaneous": "前后同时抱死"}.get(
        bc["first_lock_axle"], bc["first_lock_axle"]
    )
    notes = (
        f"I–β 线在 μ={mu:.2f} 下判定：{lock_label}"
        + (f"（φ0={bc['phi_0']:.3f}）" if bc["phi_0"] is not None else "")
        + f"；理论制动按 {stop_speed_kph:g} km/h（{'ABS' if abs_flag else '无ABS'}）计算。"
        + (f" 准稳态拟合：{qs_note}。" if us is not None else "")
    )
    return {
        "metrics": metrics_list,
        "curves": {
            "power_balance": pb_clean,
            "fuel_economy": fuel,
            "braking": bc_clean,
            "handling": hb,
            "quasi_steady": us,
        },
        "notes": notes,
    }


def engineering_analysis(rows, snapshots, options, reason, *, config=None):
    # 原记录的刚体通道保持；新模型的制动距离/稳态速度取整车质量加权CG。
    resolved_config = _resolve_config(options, config)
    motion_rows, positions = [], []
    for row, snapshot in zip(rows, snapshots, strict=True):
        position, velocity = cg_motion(snapshot.player)
        motion_rows.append({**row, "horizontal_speed": math.hypot(*velocity[:2])}
                           if snapshot.player.unsprung_state is not None else row)
        positions.append(position)
    results = [mfdd(motion_rows, positions, options["maneuver"], reason),
               yaw_gain(motion_rows, options["maneuver"], options["onset"], reason)]
    for key, label, unit in (("beta", "峰值车身侧偏", "deg"), ("roll", "峰值车身侧倾", "deg"),
                             ("ltr_front", "峰值前轴左右轮荷差比", "1"), ("ltr_rear", "峰值后轴左右轮荷差比", "1")):
        values = [abs(row[key]) for row in rows if row[key] is not None]
        results.append(metric(key, label, unit, max(values) if values else None,
                              "全程仿真步绝对峰值；轮荷转移率定义为 (Fz,R − Fz,L)/(Fz,R + Fz,L)"))
    for wheel in WHEELS:
        values = [row[f"utilization_{wheel}"] for row in rows[1:] if row[f"utilization_{wheel}"] is not None]
        results.append(metric(f"utilization_{wheel}", f"峰值附着利用率 {wheel.upper()}", "1",
                              max(values) if values else None,
                              "末机械子步轮胎平面合力与当步附着上限之比 √(Fx²+Fy²)/D"))
    return {
        "version": VERSION,
        "metrics": results,
        "ride": ride_analysis(rows, snapshots, options, reason),
        "iso_ride": iso_ride_analysis(snapshots, options, reason, resolved_config),
        "theory": theory_analysis(motion_rows, options, reason, resolved_config),
    }


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
            issue = "左前与左后轮尚未完整通过凸起段，请延长试验时长或调整初速与凸起距离"
    window = {"start_s":rows[0]["time"],"end_s":rows[-1]["time"],
              "basis":"覆盖全部仿真步；世界 Z 轴惯性加速度（未加权）"}
    if issue is not None:
        return {"metrics":[metric(key,label,unit,None,issue,window) for key,label,unit in definitions]}
    complete = rows[1:]
    body = [float(r["sprung_az"]) for r in complete if r["sprung_az"] is not None]
    hubs = [abs(float(r[f"hub_az_{w}"])) for r in complete for w in WHEELS if r[f"hub_az_{w}"] is not None]
    if not body or not hubs:
        return {"metrics":[metric(key,label,unit,None,"记录未包含垂向加速度通道",window) for key,label,unit in definitions]}
    static = float(rows[0]["load_fl"])
    values = (math.sqrt(mean(v*v for v in body)),max(map(abs,body)),max(hubs),
              max(r[f"travel_{w}"] for r in complete for w in WHEELS),
              sum(r[f"load_{w}"]<=0. for r in complete for w in WHEELS)/(4*len(complete)),
              *(min(r[f"load_{w}"] for r in complete) for w in WHEELS),
              math.sqrt(mean((float(r["load_fl"])-static)**2 for r in complete))/static if static>0. else None)
    notes = ("簧上质心世界 Z 轴惯性加速度未加权均方根值",
             "簧上质心世界 Z 轴惯性加速度绝对峰值", "四轮轮心世界 Z 轴惯性加速度绝对峰值",
             "轮心相对车身导向机构的最大压缩行程", "四轮法向载荷为零的离散采样步占比",
             *("末机械子步轮胎法向接触载荷最小值" for _ in WHEELS),
             "左前轮法向载荷相对初始静载的均方根波动比")
    return {"metrics":[metric(key,label,unit,float(value) if value is not None else None,note,window)
                       for (key,label,unit),value,note in zip(definitions,values,notes,strict=True)]}
