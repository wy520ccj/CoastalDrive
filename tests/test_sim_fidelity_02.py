"""SIM-FIDELITY-02 M1–M5 精益综合联调套件（内置四层二分定位提示，单批执行）。"""

import csv
import json
import math
from dataclasses import asdict, replace
from itertools import pairwise
from time import perf_counter

import numpy as np
import pytest

from chassis_observer import ChassisObserver
from iso_ride import (
    generate_iso_road_profile,
    iso2631_wk_gain,
    rough_road_ride_analysis,
)
from lab_experiment import LabExperiment, LabOptions
from parameter_help import explanation
from simulation import Simulation
from suspension_kc import wheel_kinematics
from theory_baselines import (
    braking_curves,
    constant_speed_fuel_curve,
    fit_quasi_steady_understeer,
    linear_handling_baseline,
    rotational_mass_factors,
)
from tire_aligning import brush_trail
from tire_calibration import FIELDS, fit_tire, load_bench, validate_fit_metadata
from tire_forces import tire_force
from tire_properties import tire_camber_stiffness, tire_grip, tire_stiffness
from unsprung_joint import unsprung_energy_ledger
from vehicle_config import CAR
from vehicle_designs import GR86_DESIGN, REFERENCE_DESIGN
from vehicle_parameters import grouped_parameters
from vehicle_state import VehicleCommand
from vehicle_unsprung import UnsprungAdvanceInput


def test_legacy_configs_remain_bit_exact_and_parameters_complete():
    # 层1：配置与说明层
    for name, cfg in (("CAR", CAR), ("REFERENCE_DESIGN", REFERENCE_DESIGN), ("GR86_DESIGN", GR86_DESIGN)):
        assert cfg.suspension_kc_enabled is False, f"[配置层] {name} 默认 K&C 应关闭"
        assert cfg.camber_stiffness == 0.0 and cfg.rear_camber_stiffness == 0.0, f"[配置层] {name} 默认外倾刚度应为 0"

    grouped = grouped_parameters(CAR)
    grouped_keys = {key for section in grouped.values() for key in section}
    assert grouped_keys == set(asdict(CAR)), "[配置层] grouped_parameters 未完整覆盖 VehicleConfig"

    for key in (*grouped_keys, "braking.response_time", "traction.target_slip", "stability.yaw_gain"):
        info = explanation(key)
        assert info.unit and info.formula and info.use, f"[说明层] {key} 缺少公式或中文定义"

    # 层2：单拍与 24 拍轨迹浮点逐位一致（关闭 K&C vs 开启但零增益）
    zero_kc = replace(
        REFERENCE_DESIGN,
        suspension_kc_enabled=True,
        static_camber_deg=(0.0, 0.0),
        static_toe_deg=(0.0, 0.0),
        camber_jounce_gains=(0.0, 0.0),
        camber_jounce_quad=(0.0, 0.0),
        camber_steer_gain=0.0,
        bump_steer_gains=(0.0, 0.0),
        camber_stiffness=0.0,
        rear_camber_stiffness=0.0,
    )
    traces = []
    for cfg in (REFERENCE_DESIGN, zero_kc):
        sim = Simulation(track="lab", traffic_count=0, config=cfg)
        try:
            sim.settle_initial()
            cmd = VehicleCommand(steering=3.0, throttle=0.3, direction=1)
            for _ in range(24):
                sim.step(cmd)
            snap = sim.snapshot().player
            traces.append((
                snap.position,
                snap.velocity,
                tuple((w.omega, w.fx, w.fy) for w in snap.wheel_dynamics),
            ))
        finally:
            sim.close()

    assert traces[0][0] == traces[1][0], "[轨迹层] 零增益 K&C 与关闭 K&C 位置不一致"
    assert traces[0][1] == traces[1][1], "[轨迹层] 零增益 K&C 与关闭 K&C 速度不一致"
    assert traces[0][2] == traces[1][2], "[本构层] 零增益 K&C 与关闭 K&C 轮速/轮胎力不一致"


def test_m1_automotive_theory_baselines_and_quasi_steady_sweep():
    # 层1：余志生《汽车理论》解析曲线
    factors = rotational_mass_factors(GR86_DESIGN)
    assert all(a > b for a, b in pairwise(factors["gears_delta"])), "[理论层] δ_k 应随挡位升高单调递减"

    brake_info = braking_curves(GR86_DESIGN)
    L = GR86_DESIGN.wheelbase
    b = L * GR86_DESIGN.front_weight_share
    hg = GR86_DESIGN.center_of_mass_height
    expected_phi0 = (L * GR86_DESIGN.front_brake_share - b) / hg
    assert brake_info["phi_0"] == pytest.approx(expected_phi0, rel=1e-12), "[理论层] 同步附着系数 φ0 公式偏差"
    assert 0.1 < expected_phi0 < 1.5
    assert braking_curves(replace(GR86_DESIGN, road_friction=max(0.1, expected_phi0 - 0.15)))["first_lock_axle"] == "front"
    assert braking_curves(replace(GR86_DESIGN, road_friction=expected_phi0 + 0.25))["first_lock_axle"] == "rear"

    fuel = constant_speed_fuel_curve(GR86_DESIGN)
    valid_qs = [q for q in fuel["best_l_per_100km"] if q is not None]
    assert len(valid_qs) >= 8
    min_idx = valid_qs.index(min(valid_qs))
    assert 0 < min_idx < len(valid_qs) - 1, "[理论层] 等速百公里油耗包络应呈典型 U 型"

    # 层2：线性化配置下的定半径准稳态扫点对账 K_sim vs K_lin
    linear_cfg = replace(
        REFERENCE_DESIGN,
        tire_peak_load_exponent=1.0,
        lateral_load_exponent=0.0,
        tire_aligning_enabled=False,
        lateral_stiffness=45000.0,
        rear_lateral_stiffness=60000.0,
    )
    k_lin = linear_handling_baseline(linear_cfg)["K_deg_per_g"]
    assert k_lin > 0.5, "[理论层] 显式 45k/60k 刚度配置应具有正不足转向度"

    run = LabExperiment(
        LabOptions(maneuver="quasi_steady_circle", radius_m=50.0, speed_kph=18.0, sweep_end_kph=52.0, duration=18.0),
        config=linear_cfg,
    )
    try:
        while not run.done:
            run.step()
        fit = fit_quasi_steady_understeer(run.samples, linear_cfg, radius_m=50.0)
    finally:
        run.close()

    assert fit["status"] == "available", f"[轨迹/指标层] 准稳态拟合失败：{fit['note']}"
    assert fit["K_sim_deg_per_g"] > 0.0, "[轨迹/指标层] K_sim 方向与正不足转向不一致"
    assert abs(fit["K_sim_deg_per_g"] - k_lin) <= 0.6, (
        f"[对账层] K_sim={fit['K_sim_deg_per_g']:.3f} vs K_lin={k_lin:.3f} deg/g 偏差超限"
    )


def _write_v2_bench(folder, truth_cfg):
    folder.mkdir(parents=True, exist_ok=True)
    csv_path = folder / "bench_v2.csv"
    fieldnames = (*FIELDS, "gamma_rad", "mz_Nm")
    speed = 20.0
    rows = []
    for split, loads in (("train", (2000.0, 3500.0, 5000.0)), ("validation", (2750.0, 4500.0))):
        for load in loads:
            grip = tire_grip(load, truth_cfg.road_friction, truth_cfg)
            cx, cy = tire_stiffness(load, truth_cfg)
            cgamma = tire_camber_stiffness(load, truth_cfg)
            for kind in ("longitudinal", "lateral"):
                for slip in (-0.30, -0.15, -0.08, -0.025, -0.002, 0.0, 0.002, 0.025, 0.08, 0.15, 0.30):
                    kappa, alpha = (slip, 0.0) if kind == "longitudinal" else (0.0, slip)
                    fx, fy = tire_force(kappa, alpha, load, truth_cfg.road_friction, truth_cfg, gamma_rad=0.0)
                    trail = brush_trail(
                        truth_cfg.tire_contact_half_length,
                        kappa,
                        alpha,
                        grip,
                        cx,
                        cy,
                        speed,
                        truth_cfg.static_contact_speed,
                        cgamma,
                        0.0,
                    )
                    rows.append({
                        "series": f"{split}-{kind}-{load}",
                        "split": split,
                        "kind": kind,
                        "fz_N": load,
                        "kappa": kappa,
                        "alpha_rad": alpha,
                        "fx_N": fx,
                        "fy_N": fy,
                        "gamma_rad": 0.0,
                        "mz_Nm": fy * trail,
                    })
            for gamma in (-0.06, -0.02, 0.02, 0.06):
                for alpha in (-0.05, 0.0, 0.05):
                    fx, fy = tire_force(0.0, alpha, load, truth_cfg.road_friction, truth_cfg, gamma_rad=gamma)
                    trail = brush_trail(
                        truth_cfg.tire_contact_half_length,
                        0.0,
                        alpha,
                        grip,
                        cx,
                        cy,
                        speed,
                        truth_cfg.static_contact_speed,
                        cgamma,
                        gamma,
                    )
                    rows.append({
                        "series": f"{split}-camber-{load}",
                        "split": split,
                        "kind": "camber",
                        "fz_N": load,
                        "kappa": 0.0,
                        "alpha_rad": alpha,
                        "fx_N": fx,
                        "fy_N": fy,
                        "gamma_rad": gamma,
                        "mz_Nm": fy * trail,
                    })
            if split == "validation":
                for kappa in (-0.12, -0.03, 0.03, 0.12):
                    for alpha in (-0.10, -0.03, 0.03, 0.10):
                        fx, fy = tire_force(kappa, alpha, load, truth_cfg.road_friction, truth_cfg, gamma_rad=0.02)
                        trail = brush_trail(
                            truth_cfg.tire_contact_half_length,
                            kappa,
                            alpha,
                            grip,
                            cx,
                            cy,
                            speed,
                            truth_cfg.static_contact_speed,
                            cgamma,
                            0.02,
                        )
                        rows.append({
                            "series": f"validation-combined-{load}",
                            "split": split,
                            "kind": "combined",
                            "fz_N": load,
                            "kappa": kappa,
                            "alpha_rad": alpha,
                            "fx_N": fx,
                            "fy_N": fy,
                            "gamma_rad": 0.02,
                            "mz_Nm": fy * trail,
                        })
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    conditions_path = folder / "conditions_v2.json"
    conditions_path.write_text(
        json.dumps({
            "tire_id": "synthetic-v2-camber-mz",
            "surface_id": "synthetic-flat",
            "pressure_kpa": 230.0,
            "temperature_c": 25.0,
            "speed_mps": speed,
            "slip_convention": "drive_positive_alpha_right",
            "camber_rad": 0.0,
            "camber_mode": "variable",
            "mz_validation": True,
            "source": "tests/test_sim_fidelity_02.py synthetic v2 bench",
            "source_kind": "synthetic",
            "measurement_mode": "steady_state",
            "installation": "same_tire_all_wheels",
        }, indent=2),
        encoding="utf-8",
    )
    return csv_path, conditions_path


def test_m2_kc_kinematics_camber_thrust_and_tire_fit_v2(tmp_path):
    # 层1：运动学与本构层
    kc_cfg = replace(
        REFERENCE_DESIGN,
        suspension_kc_enabled=True,
        static_camber_deg=(-1.0, -1.5),
        static_toe_deg=(0.10, 0.15),
        camber_jounce_gains=(-15.0, -25.0),
        camber_jounce_quad=(0.0, 0.0),
        camber_steer_gain=0.10,
        bump_steer_gains=(0.0, 8.0),
        camber_stiffness=4500.0,
        rear_camber_stiffness=4500.0,
    )
    steer, camber, incl = wheel_kinematics(0.0, (0.02, 0.02, 0.02, 0.02), kc_cfg)
    assert steer[0] == pytest.approx(-steer[1], abs=1e-12) and steer[0] > 0.0, "[K&C 层] 左右轮正前束符号应反对称"
    assert camber[0] < -1.0 and camber[2] < -1.5, "[K&C 层] 正压缩下负外倾增益应使轮顶更内倾"
    assert incl[0] == pytest.approx(-incl[1], abs=1e-12), "[K&C 层] 零转向左右对称外倾的轮胎倾角应反号"

    _, fy_pos = tire_force(0.0, 0.0, 3000.0, 1.1, kc_cfg, gamma_rad=0.05)
    _, fy_neg = tire_force(0.0, 0.0, 3000.0, 1.1, kc_cfg, gamma_rad=-0.05)
    assert fy_pos > 100.0 and fy_neg == pytest.approx(-fy_pos, abs=1e-9), "[本构层] 纯外倾侧向推力方向/大小异常"

    fx_lim, fy_lim = tire_force(0.40, 0.35, 3000.0, 1.1, kc_cfg, gamma_rad=0.08)
    grip_lim = tire_grip(3000.0, 1.1, kc_cfg)
    assert math.hypot(fx_lim, fy_lim) <= grip_lim * (1.0 + 1e-12), "[本构层] 大滑移+外倾突破摩擦圆上界"

    # 静止静置 vx=0 时外倾推力平滑归零，无横向漂移
    sim_rest = Simulation(track="lab", traffic_count=0, config=kc_cfg)
    try:
        sim_rest.settle_initial()
        p0 = sim_rest.snapshot().player.position
        for _ in range(60):
            sim_rest.step(VehicleCommand(gear=0, clutch=0.0))
        p1 = sim_rest.snapshot().player
        assert abs(p1.speed) < 1e-3 and abs(p1.position[0] - p0[0]) < 1e-4, "[本构层] 静止平路存在伪外倾横向漂移"
    finally:
        sim_rest.close()

    # 层2：整车阶跃转向轨迹层（后轴跳动前束 Roll Understeer 应减小稳态横摆幅值）
    yaw_peaks = []
    for cfg in (REFERENCE_DESIGN, kc_cfg):
        run = LabExperiment(
            LabOptions(maneuver="step_steer", speed_kph=65.0, steering_deg=4.0, onset=0.2, duration=2.2),
            config=cfg,
        )
        try:
            while not run.done:
                run.step()
            yaw_peaks.append(float(np.mean([abs(row["yaw"]) for row in run.samples[-60:]])))
        finally:
            run.close()
    assert yaw_peaks[1] < yaw_peaks[0], "[轨迹层] 后轴正跳动前束 Roll Understeer 未产生可测不足转向减摆效果"

    # 层3：coastal-tire-fit-v2 外倾 + Mz 部件标定
    truth_v2 = replace(
        REFERENCE_DESIGN,
        road_friction=0.95,
        longitudinal_stiffness=76000.0,
        lateral_stiffness=61000.0,
        rear_lateral_stiffness=61000.0,
        tire_peak_load_exponent=0.86,
        longitudinal_load_exponent=0.78,
        lateral_load_exponent=0.80,
        camber_stiffness=4800.0,
        rear_camber_stiffness=4800.0,
        camber_load_exponent=0.82,
        tire_contact_half_length=0.086,
    )
    csv_path, cond_path = _write_v2_bench(tmp_path / "v2", truth_v2)
    bench = load_bench(csv_path, cond_path)
    fitted_cfg, report = fit_tire(bench, REFERENCE_DESIGN)
    assert report["schema"] == "coastal-tire-fit-v2", "[标定层] 未输出 v2 schema"
    assert report["rank"] == 8, f"[标定层] 期望满秩 8，实际 rank={report['rank']}"
    assert report["passed"] is True, f"[标定层] v2 留出校验未通过：{report['errors']}"
    assert fitted_cfg.camber_stiffness == pytest.approx(4800.0, rel=0.02)
    validate_fit_metadata({"tire_calibration": report})


def test_m3_unsprung_c_kernel_speed_energy_and_iso_rough_road(monkeypatch):
    # 层1：独立簧下 C 内核提速与能量守恒账本
    unsprung_cfg = replace(
        REFERENCE_DESIGN,
        unsprung_enabled=True,
        angular_damping=0.0,
        unsprung_masses=(35.0,) * 4,
        tire_radial_stiffness=(200000.0,) * 4,
        tire_radial_damping=(500.0,) * 4,
    )
    steps = []
    orig_solve = UnsprungAdvanceInput.solve

    def spy_solve(self, *, query_lock=None):
        result = orig_solve(self, query_lock=query_lock)
        steps.append(result)
        return result

    monkeypatch.setattr(UnsprungAdvanceInput, "solve", spy_solve)

    run = LabExperiment(
        LabOptions(maneuver="ride_bump", speed_kph=25.0, duration=1.5),
        config=unsprung_cfg,
    )
    try:
        t0 = perf_counter()
        while not run.done:
            run.step()
        wall_s = perf_counter() - t0
        ticks = len(run.samples) - 1
    finally:
        run.close()

    avg_ms = (wall_s / max(ticks, 1)) * 1000.0
    assert avg_ms < 25.0, f"[C 内核性能层] 平均单拍求解 {avg_ms:.2f} ms >= 25 ms"
    assert steps and max(abs(s.energy_error) for s in steps) < 1e-6, "[能量账层] 存在超限局部能量残差"
    ledger = unsprung_energy_ledger(steps)
    assert abs(ledger["cumulative_energy_error"]) < 1e-4, "[能量账层] 累计能量残差超限"

    # 层2：ISO 8608 A–D 级路谱比例与 W_k 滤波器
    rms_list = [
        generate_iso_road_profile(road_class=cls, seed=7)["measured_left_rms_m"]
        for cls in ("A", "B", "C", "D")
    ]
    for low, high in pairwise(rms_list):
        assert high / low == pytest.approx(2.0, rel=1e-6), "[ISO 路谱层] 相邻路面等级 RMS 应严格呈 2x 比例"

    wk_5hz = float(iso2631_wk_gain(np.array([5.0]))[0])
    assert wk_5hz == pytest.approx(1.04, abs=0.05), f"[ISO 滤波层] W_k(5 Hz)={wk_5hz:.4f} 偏离约 1.04"

    iso_run = LabExperiment(
        LabOptions(maneuver="iso_rough_road", road_class="C", speed_kph=65.0, duration=2.5),
        config=unsprung_cfg,
    )
    try:
        while not iso_run.done:
            iso_run.step()
        analysis = rough_road_ride_analysis(iso_run.samples, unsprung_cfg)
    finally:
        iso_run.close()

    assert analysis["status"] == "available"
    assert analysis["awz_rms_mps2"] > 0.0 and analysis["sprung_peak_hz"] is not None, "[ISO 指标层] 平顺性结果缺失"


def test_m5_chassis_observer_and_sensor_ekf_closed_loop():
    # 先验证独立观测器在制动高滑移下速度与附着估计特性，再做三路闭环对照
    results = {}
    cases = (
        ("open_loop", {"abs_enabled": False, "esc_enabled": False, "controller_mode": "native", "feedback_source": "truth"}),
        ("dyc_truth", {"abs_enabled": True, "esc_enabled": True, "controller_mode": "coord_abs_dyc", "feedback_source": "truth"}),
        ("dyc_ekf", {"abs_enabled": True, "esc_enabled": True, "controller_mode": "coord_abs_dyc", "feedback_source": "sensor_ekf"}),
        ("native_ekf", {"abs_enabled": True, "esc_enabled": True, "controller_mode": "native", "feedback_source": "sensor_ekf"}),
    )
    for label, kwargs in cases:
        run = LabExperiment(
            LabOptions(
                maneuver="mu_jump_cornering_braking",
                speed_kph=80.0,
                friction=0.85,
                right_friction=0.35,
                radius_m=80.0,
                onset=1.0,
                duration=3.0,
                **kwargs,
            )
        )
        try:
            observer = ChassisObserver(run.snapshots[0], run.config, seed=0) if kwargs["feedback_source"] == "truth" else None
            est_speeds, est_mus = [], []
            while not run.done:
                snap = run.step()
                if observer is not None:
                    est = observer.observe(snap)
                    est_speeds.append(est.vx_mps)
                    est_mus.append(est.mu_est)
            betas = [abs(row["beta"]) for row in run.samples if row["beta"] is not None]
            results[label] = {
                "reason": run.reason,
                "peak_beta": max(betas) if betas else 0.0,
                "samples": list(run.samples),
                "trace": list(run.controller_trace),
                "est_speeds": est_speeds,
                "est_mus": est_mus,
            }
        finally:
            run.close()

    for label in ("dyc_truth", "dyc_ekf", "native_ekf"):
        assert results[label]["reason"] != "failed", f"[闭环层] {label} 求解异常"
        assert results[label]["peak_beta"] < results["open_loop"]["peak_beta"] * 0.75, (
            f"[闭环层] {label} 峰值侧偏 {results[label]['peak_beta']:.2f}° 未显著优于无控 {results['open_loop']['peak_beta']:.2f}°"
        )

    for ekf_label in ("dyc_ekf", "native_ekf"):
        trace_rows = [row for row in results[ekf_label]["trace"] if row is not None]
        assert trace_rows, f"[观测器层] {ekf_label} 缺少控制器遥测"
        est_vx = [row["est_vx_mps"] for row in trace_rows]
        true_vx = [row["horizontal_speed"] for row in results[ekf_label]["samples"][1 : 1 + len(trace_rows)]]
        # 大滑移制动期间 EKF 车速应平滑跟随真实车速，不因四轮滑移而塌陷归零
        moving_errors = [abs(e - t) for e, t in zip(est_vx, true_vx, strict=True) if t > 3.0]
        assert moving_errors and max(moving_errors) < 3.5, f"[观测器层] {ekf_label} 车速估计在滑移期异常漂移/塌陷"
        est_mu = [row["est_mu"] for row in trace_rows]
        assert min(est_mu) < 0.72, f"[观测器层] {ekf_label} 附着估计未随路面突变下降（min={min(est_mu):.3f}）"


@pytest.mark.ui
def test_vehicle_lab_unified_ui_export_and_reload(tmp_path):
    from lab_application import MANEUVERS, VehicleLab

    app = VehicleLab(offscreen=True, output=tmp_path)
    app.engine.taskMgr.remove("lab-update")
    try:
        # 1. 切换新增工况与下拉菜单（quasi_steady_circle, iso_rough_road, road_class_menu, feedback_menu）
        qsc_label = MANEUVERS["quasi_steady_circle"]
        iso_label = MANEUVERS["iso_rough_road"]
        app.maneuver_menu.set(app.maneuver_menu["items"].index(qsc_label))
        app.maneuver_menu.set(app.maneuver_menu["items"].index(iso_label))
        c_idx = next(i for i, item in enumerate(app.road_class_menu["items"]) if "C" in str(item))
        app.road_class_menu.set(c_idx)

        # 2. 运行真值短制动 -> 固定 A -> 切换 sensor_ekf 运行 B -> 检验 ·EKF 标签
        app.set_options(LabOptions(maneuver="braking", speed_kph=50.0, duration=0.4, abs_enabled=True, esc_enabled=True, feedback_source="truth"))
        app.start_experiment()
        while not app.run_state.done:
            app.run_state.step()
        app.run_state.paused = True
        app.pin_baseline()

        ekf_idx = next(
            (i for i, item in enumerate(app.feedback_menu["items"])
             if any(tok in str(item).lower() for tok in ("ekf", "观测", "估计"))),
            1,
        )
        app.feedback_menu.set(ekf_idx)
        app.set_options(LabOptions(maneuver="braking", speed_kph=50.0, duration=0.4, abs_enabled=True, esc_enabled=True, feedback_source="sensor_ekf"))
        app.start_experiment()
        while not app.run_state.done:
            app.run_state.step()
        app.run_state.paused = True
        app.present_summary(app.run_state.summary())
        assert "EKF" in app.candidate_label.getText(), "[UI 层] sensor_ekf 结果缺少 ·EKF 标签"

        # 3. 工程指标面板切换全部 4 个分组
        app.show_engineering()
        for group_name in ("操稳 / 制动", "乘坐 / 接地", "ISO 平顺性", "理论—仿真对账"):
            app.engineering_panel.show(group=group_name)
        app.engineering_panel.hide()

        # 4. 切换新增曲线组与 F1 参数说明
        for plot_name in ("K&C 外倾 / 转角", "状态估计对比"):
            app.set_plot_group(plot_name)
        app.hovered_parameter = "camber_stiffness"
        app.show_parameter_help()
        assert not app.parameter_help.root.isHidden(), "[UI 层] F1 参数说明面板未打开"
        app.parameter_help.hide()

        # 5. 导出、读回与复算闭环
        app.export()
        assert app.last_report is not None and app.last_report.is_file(), "[导出层] report.html 未生成"
        export_dir = app.last_report.parent
        assert (export_dir / "engineering.json").is_file(), "[导出层] engineering.json 未生成"

        assert app.import_record(export_dir) is True, "[读回层] import_record 失败"
        app.recalculate_record()
        assert app.record is not None, "[复算层] recalculate_record 后记录为空"
    finally:
        app.close_game()
