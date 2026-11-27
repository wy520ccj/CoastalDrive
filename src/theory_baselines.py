"""《汽车理论》（余志生第 6 版）第 1/2/4/5 章解析基线与准稳态圆周试验对账。"""

import math
from collections.abc import Mapping

import numpy as np

from driveline_inertia import active_inertias
from fuel import ENERGY_PER_LITRE, fuel_efficiency
from powertrain import engine_torque

G = 9.81
_RPM_TO_RADPS = math.tau / 60.0


def _cg_distances(config) -> tuple[float, float]:
    """返回 (a_m, b_m)：质心到前轴距离 a 与质心到后轴距离 b。"""
    wheelbase = float(config.wheelbase)
    front_share = float(config.front_weight_share)
    b = wheelbase * front_share
    a = wheelbase * (1.0 - front_share)
    return a, b


def _axle_kc_gains(value) -> tuple[float, float]:
    """将 2 元或 4 元 K&C 增益统一规范为 (前轴平均, 后轴平均)。"""
    if value is None:
        return 0.0, 0.0
    seq = tuple(float(v) for v in value)
    if len(seq) == 2:
        return seq[0], seq[1]
    if len(seq) == 4:
        return 0.5 * (seq[0] + seq[1]), 0.5 * (seq[2] + seq[3])
    raise ValueError("K&C 增益须为 2 元（前/后）或 4 元（四角）序列")


def rotational_mass_factors(config) -> dict:
    """计算空挡、教材标准各挡及计入输入/下游转子后的精确旋转质量换算系数 δ。"""
    m = float(config.mass)
    r = float(config.wheel_radius)
    iw = float(config.wheel_inertia)
    ie = float(config.engine_inertia)
    i0 = float(config.final_drive)
    eta = float(config.drivetrain_efficiency)
    mr2 = m * r * r

    delta0 = 1.0 + 4.0 * iw / mr2
    gears_delta = tuple(
        delta0 + ie * (float(ig) * i0) ** 2 * eta / mr2
        for ig in config.gear_ratios
    )

    input_enabled = bool(getattr(config, "input_shaft_enabled", False))
    downstream_enabled = bool(getattr(config, "downstream_inertia_enabled", False))
    input_inertia = float(getattr(config, "input_shaft_inertia", 0.0)) if input_enabled else 0.0
    downstream_term = 0.0
    if input_enabled and downstream_enabled:
        j_out, j_f, j_r = active_inertias(config.downstream_inertias, config.front_drive_share)
        downstream_term = (j_out + j_f + j_r) * (i0 * i0) / mr2

    exact_gears_delta = tuple(
        delta0 + (ie + input_inertia) * (float(ig) * i0) ** 2 * eta / mr2 + downstream_term
        for ig in config.gear_ratios
    )
    return {
        "neutral_delta0": delta0,
        "gears_delta": gears_delta,
        "exact_gears_delta": exact_gears_delta,
    }


def _solve_max_adhesion_grade(config) -> float:
    """考虑坡道轴荷转移与从动轮滚动阻力，求 1 挡最大附着爬坡度 tan(α)。"""
    m = float(config.mass)
    L = float(config.wheelbase)
    a, b = _cg_distances(config)
    hg = float(config.center_of_mass_height)
    fr = float(config.rolling_coefficient)
    mu = float(config.road_friction)
    lam = float(config.front_drive_share)

    def margin(alpha: float) -> float:
        c, s = math.cos(alpha), math.sin(alpha)
        fz1 = max(0.0, m * G * (b * c - hg * s) / L)
        fz2 = max(0.0, m * G * (a * c + hg * s) / L)
        if lam <= 0.0:
            fx_avail = mu * fz2
            f_undriven = fr * fz1
        elif lam >= 1.0:
            fx_avail = mu * fz1
            f_undriven = fr * fz2
        else:
            fx_avail = min(mu * fz1 / lam, mu * fz2 / (1.0 - lam))
            f_undriven = 0.0
        return fx_avail - m * G * s - f_undriven

    if margin(0.0) <= 0.0:
        return 0.0
    low, high = 0.0, math.atan(5.0)
    if margin(high) >= 0.0:
        return math.tan(high)
    for _ in range(64):
        mid = 0.5 * (low + high)
        if margin(mid) >= 0.0:
            low = mid
        else:
            high = mid
    return math.tan(low)


def _solve_top_gear_vmax_kph(config, alpha: float) -> float | None:
    """在最高挡精确求驱动力与行驶阻力交点车速；红线仍有余力则截断到红线车速。"""
    m = float(config.mass)
    r = float(config.wheel_radius)
    i0 = float(config.final_drive)
    eta = float(config.drivetrain_efficiency)
    ig = float(config.gear_ratios[-1])
    rho = float(config.air_density)
    cda = float(config.drag_coefficient) * float(config.frontal_area)
    ff = m * G * float(config.rolling_coefficient) * math.cos(alpha)
    fi = m * G * math.sin(alpha)

    def net_force(rpm: float) -> tuple[float, float]:
        u_mps = rpm * _RPM_TO_RADPS * r / (ig * i0)
        ft = engine_torque(rpm, config) * ig * i0 * eta / r
        fw = 0.5 * rho * cda * u_mps * u_mps
        return ft - (ff + fw + fi), u_mps * 3.6

    n_min = float(config.idle_rpm)
    n_max = float(config.engine_redline_rpm)
    f_max, u_max_kph = net_force(n_max)
    if f_max >= 0.0:
        return u_max_kph

    grid = np.linspace(n_min, n_max, 240)
    vals = [net_force(float(n))[0] for n in grid]
    crossing = None
    for idx in range(len(grid) - 1, 0, -1):
        if vals[idx - 1] >= 0.0 > vals[idx]:
            crossing = (float(grid[idx - 1]), float(grid[idx]))
            break
    if crossing is None:
        return None
    low, high = crossing
    for _ in range(48):
        mid = 0.5 * (low + high)
        if net_force(mid)[0] >= 0.0:
            low = mid
        else:
            high = mid
    return net_force(0.5 * (low + high))[1]


def _integrate_0_100_s(config, deltas: tuple[float, ...]) -> float | None:
    """平路全油门理想换挡 0–100 km/h 图解数值积分。"""
    m = float(config.mass)
    r = float(config.wheel_radius)
    i0 = float(config.final_drive)
    eta = float(config.drivetrain_efficiency)
    rho = float(config.air_density)
    cda = float(config.drag_coefficient) * float(config.frontal_area)
    ff = m * G * float(config.rolling_coefficient)
    n_idle = float(config.idle_rpm)
    n_red = float(config.engine_redline_rpm)

    u_target = 100.0 / 3.6
    steps = 1000
    du = u_target / steps
    total_time = 0.0
    for step in range(steps):
        u = (step + 0.5) * du
        fw = 0.5 * rho * cda * u * u
        best_acc = 0.0
        for ig, delta in zip(config.gear_ratios, deltas, strict=True):
            rpm = (u / r) * float(ig) * i0 / _RPM_TO_RADPS
            if rpm > n_red:
                continue
            eval_rpm = max(n_idle, rpm)
            ft = engine_torque(eval_rpm, config) * float(ig) * i0 * eta / r
            acc = (ft - ff - fw) / (delta * m)
            best_acc = max(best_acc, acc)
        if best_acc <= 1e-6:
            return None
        total_time += du / best_acc
    return total_time


def power_balance_curves(config, *, grade: float = 0.0, points: int = 120) -> dict:
    """计算各前进挡驱动力/行驶阻力/动力因数/后备功率曲线及动力性汇总指标。"""
    if points < 2:
        raise ValueError("points 须至少为 2")
    m = float(config.mass)
    r = float(config.wheel_radius)
    i0 = float(config.final_drive)
    eta = float(config.drivetrain_efficiency)
    rho = float(config.air_density)
    cda = float(config.drag_coefficient) * float(config.frontal_area)
    fr = float(config.rolling_coefficient)
    alpha = math.atan(float(grade))
    ff = m * G * fr * math.cos(alpha)
    fi = m * G * math.sin(alpha)
    deltas = rotational_mass_factors(config)["gears_delta"]

    rpms = np.linspace(float(config.idle_rpm), float(config.engine_redline_rpm), points)
    gears = []
    for gear_idx, (ig, delta) in enumerate(zip(config.gear_ratios, deltas, strict=True), 1):
        ig_f = float(ig)
        u_mps_arr = rpms * _RPM_TO_RADPS * r / (ig_f * i0)
        u_kph_arr = u_mps_arr * 3.6
        tq_arr = np.array([engine_torque(float(n), config) for n in rpms], dtype=float)
        ft_arr = tq_arr * ig_f * i0 * eta / r
        fw_arr = 0.5 * rho * cda * (u_mps_arr ** 2)
        fres_arr = ff + fw_arr + fi
        d_arr = (ft_arr - fw_arr) / (m * G)
        pres_arr = (ft_arr - fres_arr) * u_mps_arr / (1000.0 * eta)
        gears.append({
            "gear": gear_idx,
            "ratio": ig_f,
            "delta": delta,
            "rpm": tuple(map(float, rpms)),
            "u_mps": tuple(map(float, u_mps_arr)),
            "u_kph": tuple(map(float, u_kph_arr)),
            "ft_n": tuple(map(float, ft_arr)),
            "ff_n": tuple(ff for _ in rpms),
            "fw_n": tuple(map(float, fw_arr)),
            "fi_n": tuple(fi for _ in rpms),
            "f_res_n": tuple(map(float, fres_arr)),
            "d_factor": tuple(map(float, d_arr)),
            "p_res_kw": tuple(map(float, pres_arr)),
        })

    d1_max = max(gears[0]["d_factor"])
    denom_grade = math.hypot(1.0, fr)
    if d1_max <= fr:
        max_grade_drive = 0.0
    elif d1_max >= denom_grade:
        max_grade_drive = float("inf")
    else:
        alpha_max = math.asin(d1_max / denom_grade) - math.atan(fr)
        max_grade_drive = math.tan(max(0.0, alpha_max))

    return {
        "grade": float(grade),
        "alpha_rad": alpha,
        "gears": tuple(gears),
        "v_max_kph": _solve_top_gear_vmax_kph(config, alpha),
        "max_grade_1st_drive": max_grade_drive,
        "max_grade_1st_adhesion": _solve_max_adhesion_grade(config),
        "time_0_100_s": _integrate_0_100_s(config, deltas),
    }


def constant_speed_fuel_curve(config, *, speeds_kph=None) -> dict:
    """复用 src/fuel.py 效率图谱，计算平路各挡等速百公里油耗 Qs（L/100km）及经济挡包络。"""
    speeds = tuple(range(20, 145, 5)) if speeds_kph is None else tuple(float(s) for s in speeds_kph)
    m = float(config.mass)
    r = float(config.wheel_radius)
    i0 = float(config.final_drive)
    eta = float(config.drivetrain_efficiency)
    rho = float(config.air_density)
    cda = float(config.drag_coefficient) * float(config.frontal_area)
    ff = m * G * float(config.rolling_coefficient)
    n_idle = float(config.idle_rpm)
    n_red = float(config.engine_redline_rpm)
    rpm_span = max(n_red - n_idle, 1.0)

    gear_curves = {}
    for gear_idx, ig in enumerate(config.gear_ratios, 1):
        ig_f = float(ig)
        qs_list = []
        for u_kph in speeds:
            if u_kph <= 0.0:
                qs_list.append(None)
                continue
            u_mps = u_kph / 3.6
            rpm = (u_mps / r) * ig_f * i0 / _RPM_TO_RADPS
            if rpm < n_idle or rpm > n_red:
                qs_list.append(None)
                continue
            f_total = ff + 0.5 * rho * cda * u_mps * u_mps
            tq_req = f_total * r / (ig_f * i0 * eta)
            tq_full = engine_torque(rpm, config)
            if tq_full <= 1e-12 or tq_req > tq_full:
                qs_list.append(None)
                continue
            load = tq_req / tq_full
            eff = fuel_efficiency(rpm / n_red, load)
            p_engine = f_total * u_mps / eta
            no_load_lph = 0.7 + 1.8 * max(0.0, (rpm - n_idle) / rpm_span)
            rate_lph = max(no_load_lph, p_engine * 3600.0 / (eff * ENERGY_PER_LITRE))
            qs_list.append(rate_lph / u_kph * 100.0)
        gear_curves[gear_idx] = tuple(qs_list)

    best_qs = []
    best_gear = []
    for idx in range(len(speeds)):
        candidates = [
            (gear_idx, gear_curves[gear_idx][idx])
            for gear_idx in gear_curves
            if gear_curves[gear_idx][idx] is not None
        ]
        if not candidates:
            best_qs.append(None)
            best_gear.append(None)
        else:
            g_min, q_min = min(candidates, key=lambda item: item[1])
            best_gear.append(g_min)
            best_qs.append(q_min)

    return {
        "speeds_kph": speeds,
        "gears": gear_curves,
        "best_l_per_100km": tuple(best_qs),
        "best_gear": tuple(best_gear),
    }


def _braking_efficiency_at(phi: float, beta: float, a: float, b: float, L: float, hg: float) -> tuple[float | None, float | None, float | None]:
    """计算给定附着系数 φ 下的前轴、后轴及整车制动效率。"""
    denom_f = beta - phi * hg / L
    denom_r = (1.0 - beta) + phi * hg / L
    ef = (b / L) / denom_f if denom_f > 1e-12 else None
    er = (a / L) / denom_r if denom_r > 1e-12 else None
    valid = [v for v in (ef, er) if v is not None]
    eff = min(valid) if len(valid) == 2 else (valid[0] if valid else None)
    return ef, er, eff


def theoretical_stop_distance(speed_kph: float, mu: float, config, *, abs_enabled: bool | None = None) -> float:
    """计入制动器一阶响应时间常数 τ_b 修正的平路理论制动距离（m）。"""
    v0 = max(0.0, float(speed_kph)) / 3.6
    if v0 <= 0.0:
        return 0.0
    mu_val = max(0.0, float(mu))
    if mu_val <= 0.0:
        return float("inf")
    use_abs = bool(config.braking.abs_enabled) if abs_enabled is None else bool(abs_enabled)
    cap_decel = float(config.brake_torque) / (float(config.mass) * float(config.wheel_radius))
    if use_abs:
        a_max = min(mu_val * G, cap_decel)
    else:
        a, b = _cg_distances(config)
        _, _, eff = _braking_efficiency_at(
            mu_val, float(config.front_brake_share), a, b, float(config.wheelbase), float(config.center_of_mass_height)
        )
        eff_val = 1.0 if eff is None else max(0.05, min(1.0, eff))
        a_max = min(mu_val * eff_val * G, cap_decel)
    if a_max <= 1e-9:
        return float("inf")
    tau_b = max(0.0, float(config.braking.response_time))
    # 一阶滞后 a(t) = a_max * (1 - exp(-t / tau_b)) 在充分制动下等效全滞后时间 tau_b。
    if tau_b == 0.0:
        return v0 * v0 / (2.0 * a_max)
    # 若极低速在纯滞后段内即刹停，数值求解 v(t)=0。
    if v0 <= a_max * tau_b:
        t = 0.0
        v = v0
        s = 0.0
        dt = min(1e-4, tau_b / 200.0)
        while v > 0.0 and t < 60.0:
            acc = a_max * (1.0 - math.exp(-t / tau_b))
            v_next = max(0.0, v - acc * dt)
            s += 0.5 * (v + v_next) * dt
            v = v_next
            t += dt
        return s
    return v0 * tau_b + v0 * v0 / (2.0 * a_max) - 0.5 * a_max * tau_b * tau_b


def braking_curves(config, *, phi_grid=None) -> dict:
    """对齐余志生第 6 版第 4 章：I/β 线组、同步附着系数 φ0、利用附着系数与制动效率。"""
    L = float(config.wheelbase)
    a, b = _cg_distances(config)
    hg = float(config.center_of_mass_height)
    weight = float(config.mass) * G
    beta = float(config.front_brake_share)
    mu = float(config.road_friction)

    if phi_grid is None:
        phis = tuple(round(0.1 + 0.05 * i, 4) for i in range(23))
    else:
        phis = tuple(float(p) for p in phi_grid)

    phi_0 = (L * beta - b) / hg if hg > 0.0 else None

    ideal_front_n, ideal_rear_n = [], []
    actual_front_n, actual_rear_n = [], []
    phi_f, phi_r = [], []
    eff_f_list, eff_r_list, eff_list = [], [], []

    for z in phis:
        fz1 = max(0.0, weight * (b + z * hg) / L)
        fz2 = max(0.0, weight * (a - z * hg) / L)
        ideal_front_n.append(z * fz1)
        ideal_rear_n.append(z * fz2)
        fb1 = beta * z * weight
        fb2 = (1.0 - beta) * z * weight
        actual_front_n.append(fb1)
        actual_rear_n.append(fb2)
        phi_f.append(fb1 / fz1 if fz1 > 1e-12 else None)
        phi_r.append(fb2 / fz2 if fz2 > 1e-12 else None)
        ef, er, eff = _braking_efficiency_at(z, beta, a, b, L, hg)
        eff_f_list.append(ef)
        eff_r_list.append(er)
        eff_list.append(eff)

    ef_mu, er_mu, _ = _braking_efficiency_at(mu, beta, a, b, L, hg)
    if ef_mu is not None and er_mu is not None:
        if abs(ef_mu - er_mu) <= 1e-6:
            first_lock = "simultaneous"
        elif ef_mu < er_mu:
            first_lock = "front"
        else:
            first_lock = "rear"
    elif ef_mu is not None:
        first_lock = "front"
    elif er_mu is not None:
        first_lock = "rear"
    else:
        first_lock = "simultaneous"

    return {
        "phi_grid": phis,
        "beta": beta,
        "mu": mu,
        "phi_0": phi_0,
        "ideal_front_n": tuple(ideal_front_n),
        "ideal_rear_n": tuple(ideal_rear_n),
        "actual_front_n": tuple(actual_front_n),
        "actual_rear_n": tuple(actual_rear_n),
        "phi_f": tuple(phi_f),
        "phi_r": tuple(phi_r),
        "efficiency_front": tuple(eff_f_list),
        "efficiency_rear": tuple(eff_r_list),
        "efficiency": tuple(eff_list),
        "first_lock_axle": first_lock,
        "stop_distance_100kph_m": theoretical_stop_distance(100.0, mu, config),
    }


def linear_handling_baseline(config) -> dict:
    """二自由度线性单轨理论：轮胎不足转向梯度、可选 K&C 增量、特征/临界车速与横摆增益。"""
    m = float(config.mass)
    L = float(config.wheelbase)
    a, b = _cg_distances(config)
    fz1_0 = 0.5 * m * G * (b / L)
    fz2_0 = 0.5 * m * G * (a / L)
    ref_load = float(config.tire_reference_load)
    exp_lat = float(config.lateral_load_exponent)

    c_alpha_f = 2.0 * float(config.lateral_stiffness) * ((fz1_0 / ref_load) ** exp_lat)
    c_alpha_r = 2.0 * float(config.rear_lateral_stiffness) * ((fz2_0 / ref_load) ** exp_lat)

    # K = (m / L) * (b / C_af - a / C_ar), 单位 rad/(m/s²)
    k_tire = (m / L) * (b / c_alpha_f - a / c_alpha_r)

    tf, tr = config.wheel_track_widths
    ks = tuple(float(v) for v in config.suspension_spring_rates)
    karb = tuple(float(v) for v in config.suspension_antiroll_rates)
    k_phi_f = (ks[0] + ks[1] + 4.0 * karb[0]) * ((tf * 0.5) ** 2)
    k_phi_r = (ks[2] + ks[3] + 4.0 * karb[1]) * ((tr * 0.5) ** 2)
    k_phi = max(k_phi_f + k_phi_r, 1.0)
    roll_grad_rad_per_mps2 = m * float(config.center_of_mass_height) / k_phi
    roll_grad_deg_per_g = roll_grad_rad_per_mps2 * G * (180.0 / math.pi)

    k_kc = 0.0
    if bool(getattr(config, "suspension_kc_enabled", False)):
        bs_f, bs_r = (math.radians(v) for v in _axle_kc_gains(getattr(config, "bump_steer_gains", (0.0, 0.0))))
        cg_f, cg_r = (math.radians(v) for v in _axle_kc_gains(getattr(config, "camber_jounce_gains", (0.0, 0.0))))
        exp_cam = float(getattr(config, "camber_load_exponent", exp_lat))
        # 后轴正跳动前束增加不足转向度，前轴正跳动前束减小不足转向度。
        k_bs = (-bs_f * (tf * 0.5) + bs_r * (tr * 0.5)) * roll_grad_rad_per_mps2
        c_camber_f = 2.0 * float(getattr(config, "camber_stiffness", 0.0)) * ((fz1_0 / ref_load) ** exp_cam)
        c_camber_r = 2.0 * float(getattr(config, "rear_camber_stiffness", 0.0)) * ((fz2_0 / ref_load) ** exp_cam)
        k_camber = 0.0
        if c_camber_f != 0.0 or c_camber_r != 0.0:
            k_camber = (
                (c_camber_f / c_alpha_f) * (1.0 + cg_f * (tf * 0.5))
                - (c_camber_r / c_alpha_r) * (1.0 + cg_r * (tr * 0.5))
            ) * roll_grad_rad_per_mps2
        k_kc = k_bs + k_camber

    k_lin = k_tire + k_kc
    k_deg_per_g = k_lin * G * (180.0 / math.pi)
    stability_factor = k_lin / L

    u_ch_mps = math.sqrt(L / k_lin) if k_lin > 1e-12 else None
    u_cr_mps = math.sqrt(-L / k_lin) if k_lin < -1e-12 else None

    speeds_kph = tuple(range(10, 165, 5))
    speeds_mps = tuple(u / 3.6 for u in speeds_kph)
    yaw_gains = tuple(
        (u / L) / (1.0 + stability_factor * u * u) if (1.0 + stability_factor * u * u) > 1e-6 else None
        for u in speeds_mps
    )

    return {
        "a_m": a,
        "b_m": b,
        "c_alpha_f": c_alpha_f,
        "c_alpha_r": c_alpha_r,
        "K_tire_rad_per_mps2": k_tire,
        "K_kc_rad_per_mps2": k_kc,
        "K_rad_per_mps2": k_lin,
        "K_deg_per_g": k_deg_per_g,
        "stability_factor_s2_m2": stability_factor,
        "u_ch_mps": u_ch_mps,
        "u_ch_kph": None if u_ch_mps is None else u_ch_mps * 3.6,
        "u_cr_mps": u_cr_mps,
        "u_cr_kph": None if u_cr_mps is None else u_cr_mps * 3.6,
        "roll_gradient_deg_per_g": roll_grad_deg_per_g,
        "speeds_kph": speeds_kph,
        "speeds_mps": speeds_mps,
        "yaw_rate_gain_1_per_s": yaw_gains,
    }


def _linear_fit(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float, float]:
    """最小二乘一元线性回归 y = intercept + slope * x，返回 (intercept, slope, r2)。"""
    x_mean = float(np.mean(xs))
    y_mean = float(np.mean(ys))
    dx = xs - x_mean
    dy = ys - y_mean
    sxx = float(np.dot(dx, dx))
    if sxx <= 1e-15:
        return y_mean, 0.0, 0.0
    slope = float(np.dot(dx, dy) / sxx)
    intercept = y_mean - slope * x_mean
    syy = float(np.dot(dy, dy))
    if syy <= 1e-15:
        r2 = 1.0
    else:
        res = ys - (intercept + slope * xs)
        r2 = 1.0 - float(np.dot(res, res)) / syy
    return intercept, slope, r2


def fit_quasi_steady_understeer(samples, config, *, radius_m: float | None = None, ay_band: tuple[float, float] = (0.6, 3.5)) -> dict:
    """从缓增车速定圆试验样本拟合实算不足转向梯度 K_sim 并与理论 K_lin 对账。"""
    baseline = linear_handling_baseline(config)
    k_theory_deg_per_g = baseline["K_deg_per_g"]
    ay_min, ay_max = float(ay_band[0]), float(ay_band[1])

    all_abs_ay = []
    band_ay, band_delta_rad, band_roll_deg = [], [], []
    for row in samples:
        if not isinstance(row, Mapping):
            continue
        ax = row.get("cg_ax")
        if ax is None:
            ax = row.get("ax")
        ay = row.get("cg_ay")
        if ay is None:
            ay = row.get("ay")
        speed = row.get("horizontal_speed")
        if speed is None and row.get("speed") is not None:
            speed = float(row["speed"]) / 3.6
        steer_deg = row.get("steering")
        roll_deg = row.get("roll")
        if None in (ax, ay, speed, steer_deg):
            continue
        ax_f, ay_f, v_f, steer_f = float(ax), float(ay), float(speed), float(steer_deg)
        if not all(math.isfinite(v) for v in (ax_f, ay_f, v_f, steer_f)):
            continue
        abs_ay = abs(ay_f)
        all_abs_ay.append(abs_ay)
        if abs(ax_f) <= 0.65 and v_f > 2.0 and ay_min <= abs_ay <= ay_max:
            band_ay.append(abs_ay)
            band_delta_rad.append(abs(math.radians(steer_f)))
            if roll_deg is not None and math.isfinite(float(roll_deg)):
                band_roll_deg.append(abs(float(roll_deg)))
            else:
                band_roll_deg.append(0.0)

    peak_ay_g = max(all_abs_ay) / G if all_abs_ay else None
    count = len(band_ay)
    if count < 10 or (max(band_ay) - min(band_ay)) <= 0.2:
        return {
            "status": "unavailable",
            "note": "准稳态拟合窗口内样本不足或侧向加速度跨度不足 0.2 m/s²",
            "K_sim_rad_per_mps2": None,
            "K_sim_deg_per_g": None,
            "K_theory_deg_per_g": k_theory_deg_per_g,
            "K_delta_deg_per_g": None,
            "r2": None,
            "roll_gradient_deg_per_g": None,
            "peak_ay_g": peak_ay_g,
            "sample_count": count,
        }

    xs = np.asarray(band_ay, dtype=float)
    ys = np.asarray(band_delta_rad, dtype=float)
    delta0_rad, k_sim, r2 = _linear_fit(xs, ys)
    k_sim_deg_per_g = k_sim * G * (180.0 / math.pi)

    roll_grad = None
    if any(v > 0.0 for v in band_roll_deg):
        _, roll_grad, _ = _linear_fit(xs / G, np.asarray(band_roll_deg, dtype=float))

    note = f"在 |ay|∈[{ay_min:g}, {ay_max:g}] m/s²、|ax|≤0.65 m/s² 内线性拟合"
    if radius_m is not None and radius_m > 0.0:
        ackermann_deg = math.degrees(float(config.wheelbase) / float(radius_m))
        note += f"（理论阿克曼角 {ackermann_deg:.3f}°，拟合截距 {math.degrees(delta0_rad):.3f}°）"

    return {
        "status": "available",
        "note": note,
        "K_sim_rad_per_mps2": k_sim,
        "K_sim_deg_per_g": k_sim_deg_per_g,
        "K_theory_deg_per_g": k_theory_deg_per_g,
        "K_delta_deg_per_g": k_sim_deg_per_g - k_theory_deg_per_g,
        "r2": r2,
        "roll_gradient_deg_per_g": roll_grad,
        "peak_ay_g": peak_ay_g,
        "sample_count": count,
    }
