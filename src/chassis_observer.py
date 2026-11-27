"""智能底盘状态与峰值附着观测器，以及 sensor_ekf 闭环快照适配器与控制包装。"""

import math
from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np
from wheel_contact_kernels import brakes_advance, stability_advance

from estimation_rotation import matrix
from sensor_run import SensingRun
from sensor_sampling import DT, GRAVITY, SENSORS
from tire_properties import tire_grip
from vehicle_brakes import BrakeState
from vehicle_config import wheel_hubs
from vehicle_stability import StabilityState
from vehicle_state import VehicleCommand

_G = 9.81


@dataclass(frozen=True)
class ChassisEstimate:
    tick: int
    vx_mps: float
    vy_right_mps: float
    speed_mps: float
    yaw_rate_radps: float
    sideslip_deg: float
    ax_mps2: float
    ay_right_mps2: float
    mu_est: float
    vx_std_mps: float
    beta_std_deg: float
    gnss_nis: float | None
    wheel_nis: float | None
    wheel_accepted: bool | None


class ChassisObserver:
    """融合 15 维误差状态 EKF、轮滑 NIS 门控与非对称峰值附着在线辨识。"""

    def __init__(self, initial_snapshot, vehicle_config, sensors=SENSORS, seed: int = 0):
        self.vehicle_config = vehicle_config
        self.hubs = np.asarray(wheel_hubs(vehicle_config), dtype=float)
        self.sensing = SensingRun(initial_snapshot, vehicle_config, sensors=sensors, seed=seed)
        self.mu_est = 0.85
        self._a_horiz_filt = 0.0
        self._last_wheel_omega = np.array([w.relative_omega for w in initial_snapshot.player.wheel_dynamics], dtype=float)
        self._last_wheel_steer = np.array([math.radians(w.steering) for w in initial_snapshot.player.wheel_dynamics], dtype=float)
        self._last_kappas = np.zeros(4, dtype=float)
        self._last_wheel_vx = np.full(4, float(initial_snapshot.player.speed), dtype=float)
        self._last_estimate = self._build_estimate(initial_snapshot, self.sensing.state)

    def reset(self, snapshot) -> ChassisEstimate:
        sensing_state = self.sensing.reset(snapshot)
        self.mu_est = 0.85
        self._a_horiz_filt = 0.0
        self._last_wheel_omega = np.array([w.relative_omega for w in snapshot.player.wheel_dynamics], dtype=float)
        self._last_wheel_steer = np.array([math.radians(w.steering) for w in snapshot.player.wheel_dynamics], dtype=float)
        self._last_kappas = np.zeros(4, dtype=float)
        self._last_wheel_vx = np.full(4, float(snapshot.player.speed), dtype=float)
        self._last_estimate = self._build_estimate(snapshot, sensing_state)
        return self._last_estimate

    def _estimate_wheel_slips(self, vx_mps: float, vy_right_mps: float, yaw_rate_radps: float) -> tuple[np.ndarray, np.ndarray]:
        v_body = np.array((vy_right_mps, vx_mps, 0.0), dtype=float)
        omega_body = np.array((0.0, 0.0, yaw_rate_radps), dtype=float)
        hub_vel = v_body + np.cross(omega_body, self.hubs)
        sin_s = np.sin(self._last_wheel_steer)
        cos_s = np.cos(self._last_wheel_steer)
        wheel_vx = hub_vel[:, 0] * sin_s + hub_vel[:, 1] * cos_s
        denom = np.maximum(np.abs(wheel_vx), float(self.vehicle_config.slip_speed))
        kappas = (float(self.vehicle_config.wheel_radius) * self._last_wheel_omega - wheel_vx) / denom
        return kappas, wheel_vx

    def _update_mu_estimate(self, ax_mps2: float, ay_right_mps2: float, speed_mps: float, kappas: np.ndarray, wheel_accepted: bool | None):
        a_horiz_g = math.hypot(ax_mps2, ay_right_mps2) / _G
        self._a_horiz_filt += (a_horiz_g - self._a_horiz_filt) * (1.0 - math.exp(-DT / 0.025))
        max_slip = float(np.max(np.abs(kappas)))
        significant_slip = (max_slip > 0.04) or (wheel_accepted is False)

        if self._a_horiz_filt > self.mu_est:
            gain = 1.0 - math.exp(-DT / 0.05)
            self.mu_est += gain * (self._a_horiz_filt - self.mu_est)
        elif significant_slip and speed_mps > 2.0 and self._a_horiz_filt < self.mu_est:
            tau_down = 0.07 if max_slip > 0.08 or wheel_accepted is False else 0.22
            gain = 1.0 - math.exp(-DT / tau_down)
            target = max(0.12, self._a_horiz_filt)
            self.mu_est += gain * (target - self.mu_est)
        self.mu_est = max(0.12, min(1.50, self.mu_est))

    def _build_estimate(self, snapshot, sensing_state) -> ChassisEstimate:
        est = sensing_state.estimate
        meas = sensing_state.measurements
        rot = matrix(est.orientation)
        v_body = rot.T @ np.asarray(est.velocity, dtype=float)
        vy_right_mps = float(v_body[0])
        vx_mps = float(v_body[1])
        speed_mps = math.hypot(vx_mps, vy_right_mps)

        if meas is not None:
            omega_corr = np.asarray(meas.imu.angular_velocity, dtype=float) - np.asarray(est.gyro_bias, dtype=float)
            spec_corr = np.asarray(meas.imu.specific_force, dtype=float) - np.asarray(est.accel_bias, dtype=float)
            a_world = rot @ spec_corr + GRAVITY
            a_body = rot.T @ a_world
            ay_right_mps2 = float(a_body[0])
            ax_mps2 = float(a_body[1])
            yaw_rate_radps = float(omega_corr[2])
            if meas.wheels is not None:
                self._last_wheel_omega = np.asarray(meas.wheels.omega, dtype=float)
                self._last_wheel_steer = np.asarray(meas.wheels.steering, dtype=float)
            kappas, wheel_vx = self._estimate_wheel_slips(vx_mps, vy_right_mps, yaw_rate_radps)
            self._last_kappas = kappas
            self._last_wheel_vx = wheel_vx
            self._update_mu_estimate(ax_mps2, ay_right_mps2, speed_mps, kappas, est.wheel_accepted)
        else:
            yaw_rate_radps = float(snapshot.player.dynamics.yaw_rate)
            ax_mps2 = float(snapshot.player.acceleration)
            ay_right_mps2 = float(snapshot.player.lateral_acceleration)
            self._last_kappas, self._last_wheel_vx = self._estimate_wheel_slips(vx_mps, vy_right_mps, yaw_rate_radps)

        if speed_mps <= 1.0:
            sideslip_deg = 0.0
        else:
            sideslip_deg = math.degrees(math.atan2(vy_right_mps, max(abs(vx_mps), 1.0)))

        var_world = np.asarray(est.covariance_diagonal[3:6], dtype=float)
        var_body = (rot.T ** 2) @ var_world
        var_vy_right = max(0.0, float(var_body[0]))
        var_vx = max(0.0, float(var_body[1]))
        vx_std_mps = math.sqrt(var_vx)
        if speed_mps <= 1.0:
            beta_std_deg = 0.0
        else:
            denom2 = max(vx_mps * vx_mps + vy_right_mps * vy_right_mps, 1.0)
            var_beta_rad2 = (vx_mps * vx_mps * var_vy_right + vy_right_mps * vy_right_mps * var_vx) / (denom2 * denom2)
            beta_std_deg = math.degrees(math.sqrt(max(0.0, var_beta_rad2)))

        return ChassisEstimate(
            tick=est.tick,
            vx_mps=vx_mps,
            vy_right_mps=vy_right_mps,
            speed_mps=speed_mps,
            yaw_rate_radps=yaw_rate_radps,
            sideslip_deg=sideslip_deg,
            ax_mps2=ax_mps2,
            ay_right_mps2=ay_right_mps2,
            mu_est=self.mu_est,
            vx_std_mps=vx_std_mps,
            beta_std_deg=beta_std_deg,
            gnss_nis=est.gnss_nis,
            wheel_nis=est.wheel_nis,
            wheel_accepted=est.wheel_accepted,
        )

    def observe(self, snapshot) -> ChassisEstimate:
        """推进传感器与 EKF（同拍调用幂等），返回 ChassisEstimate。"""
        if (
            self._last_estimate is not None
            and snapshot.tick == self.sensing.state.estimate.tick
            and snapshot.contact_epoch == self.sensing.epoch
        ):
            return self._last_estimate
        if snapshot.tick == self.sensing.state.estimate.tick:
            self._last_estimate = self._build_estimate(snapshot, self.sensing.state)
            return self._last_estimate
        sensing_state = self.sensing.observe(snapshot)
        if sensing_state.reset:
            self.mu_est = 0.85
            self._a_horiz_filt = 0.0
        self._last_estimate = self._build_estimate(snapshot, sensing_state)
        return self._last_estimate

    def adapt_snapshot(self, snapshot, estimate: ChassisEstimate | None = None):
        """生成仅含观测器估计状态的只读 Snapshot 副本，供下游闭环控制器复用。"""
        est = self.observe(snapshot) if estimate is None else estimate
        player = snapshot.player
        rot = matrix(player.orientation)
        v_orig = np.asarray(player.velocity, dtype=float)
        v_local = rot.T @ v_orig
        world_vel = tuple(map(float, rot @ np.array((est.vy_right_mps, est.vx_mps, float(v_local[2])))))

        dynamics = replace(
            player.dynamics,
            yaw_rate=est.yaw_rate_radps,
            sideslip=est.sideslip_deg,
        )

        unsprung = player.unsprung_state
        if unsprung is not None:
            world_acc = tuple(map(float, rot @ np.array((est.ay_right_mps2, est.ax_mps2, 0.0))))
            unsprung = replace(
                unsprung,
                total_center_velocity=world_vel,
                total_center_acceleration=world_acc,
            )

        updated_wheels = []
        for idx, wheel in enumerate(player.wheel_dynamics):
            force_grip = tire_grip(wheel.normal_load, est.mu_est, self.vehicle_config) if wheel.road_support else 0.0
            sample_load = (
                player.wheel_contacts[idx].normal_load
                if idx < len(player.wheel_contacts)
                else wheel.normal_load
            )
            sample_grip = tire_grip(sample_load, est.mu_est, self.vehicle_config) if wheel.sample_support else 0.0
            updated_wheels.append(replace(wheel, force_grip=force_grip, sample_grip=sample_grip))

        new_player = replace(
            player,
            velocity=world_vel,
            speed=est.vx_mps,
            acceleration=est.ax_mps2,
            lateral_acceleration=est.ay_right_mps2,
            dynamics=dynamics,
            unsprung_state=unsprung,
            wheel_dynamics=tuple(updated_wheels),
        )
        return replace(snapshot, player=new_player)


class EstimatedNativeStabilityController:
    """以 ChassisObserver 估计量驱动原生 ABS / ESC 算法，避免直读仿真真值。"""

    def __init__(self, sensors=SENSORS, seed: int = 0):
        self.sensors = sensors
        self.seed = int(seed)
        self.observer: ChassisObserver | None = None
        self.config = None
        self.brake_config = None
        self.stability_config = None
        self.brake_states = tuple(BrakeState() for _ in range(4))
        self.stability_state = StabilityState()
        self.last_estimate: ChassisEstimate | None = None
        self.last_telemetry: dict = {}

    def reset(self, config, options, initial_snapshot):
        self.config = config
        self.brake_config = replace(config.braking, abs_enabled=bool(options.abs_enabled))
        self.stability_config = replace(config.stability, esc_enabled=bool(options.esc_enabled))
        self.observer = ChassisObserver(initial_snapshot, config, sensors=self.sensors, seed=self.seed)
        self.brake_states = tuple(BrakeState() for _ in range(4))
        self.stability_state = StabilityState()
        self.last_estimate = self.observer.observe(initial_snapshot)
        self.last_telemetry = {}

    def _estimated_normal_loads(self, est: ChassisEstimate) -> tuple[float, float, float, float]:
        cfg = self.config
        m = float(cfg.mass)
        L = float(cfg.wheelbase)
        hg = float(cfg.center_of_mass_height)
        tf, tr = cfg.wheel_track_widths
        ks = cfg.suspension_spring_rates
        karb = cfg.suspension_antiroll_rates
        k_phi_f = (ks[0] + ks[1] + 4.0 * karb[0]) * ((tf * 0.5) ** 2)
        k_phi_r = (ks[2] + ks[3] + 4.0 * karb[1]) * ((tr * 0.5) ** 2)
        roll_share_f = k_phi_f / max(k_phi_f + k_phi_r, 1.0)

        total_w = m * _G
        front_axle = max(0.0, min(total_w, total_w * float(cfg.front_weight_share) - m * hg * est.ax_mps2 / L))
        rear_axle = total_w - front_axle
        # 右偏横向加速度 ay_right > 0 使外侧（左侧）减载还是增载：右转时离心力向左，左侧增载。
        df = m * hg * est.ay_right_mps2 * roll_share_f / tf
        dr = m * hg * est.ay_right_mps2 * (1.0 - roll_share_f) / tr
        fl = max(0.0, min(front_axle, 0.5 * front_axle + df))
        fr = front_axle - fl
        rl = max(0.0, min(rear_axle, 0.5 * rear_axle + dr))
        rr = rear_axle - rl
        return fl, fr, rl, rr

    def compute(self, snapshot, base_command: VehicleCommand, elapsed: float, dt: float) -> VehicleCommand:
        if self.observer is None:
            raise RuntimeError("EstimatedNativeStabilityController 尚未 reset")
        est = self.observer.observe(snapshot)
        self.last_estimate = est
        cfg = self.config
        hubs = self.observer.hubs
        wheel_omegas = self.observer._last_wheel_omega
        wheel_steers = self.observer._last_wheel_steer
        wheel_vx = self.observer._last_wheel_vx

        base_requests = (
            tuple(float(v) for v in base_command.wheel_brakes)
            if base_command.wheel_brakes is not None
            else (float(base_command.brake),) * 4
        )
        loads = self._estimated_normal_loads(est)
        player = snapshot.player
        supports = tuple(
            w.sample_support if i < len(player.wheel_dynamics) else True
            for i, w in enumerate(player.wheel_dynamics)
        ) if len(player.wheel_dynamics) == 4 else (True, True, True, True)

        capacities, limits, arms = [], [], []
        grip_budget = 0.0
        for idx in range(4):
            share = float(cfg.front_brake_share) if idx < 2 else (1.0 - float(cfg.front_brake_share))
            cap = float(cfg.brake_torque) * share / (2.0 * float(cfg.wheel_radius))
            capacities.append(cap)
            if not supports[idx]:
                limits.append(0.0)
                arms.append(0.0)
                continue
            grip = tire_grip(loads[idx], est.mu_est, cfg)
            grip_budget += grip
            limits.append(min(cap, grip))
            hx, hy = float(hubs[idx, 0]), float(hubs[idx, 1])
            tx, ty = math.sin(float(wheel_steers[idx])), math.cos(float(wheel_steers[idx]))
            arms.append(-math.copysign(1.0, float(wheel_vx[idx])) * (hx * ty - hy * tx))

        supported = any(supports)
        tf, _ = cfg.wheel_track_widths
        yaw_inertia = (
            float(cfg.body_inertia[2])
            if cfg.body_inertia is not None
            else float(cfg.mass) * (float(cfg.wheelbase) ** 2 + tf ** 2) / 12.0
        )
        inertia = yaw_inertia if abs(est.vx_mps) >= self.stability_config.minimum_speed and supported else 0.0
        steering_deg = float(np.degrees(0.5 * (wheel_steers[0] + wheel_steers[1])))

        self.stability_state = stability_advance(
            self.stability_config,
            cfg,
            self.stability_state,
            base_requests,
            est.vx_mps,
            est.yaw_rate_radps,
            math.radians(est.sideslip_deg),
            inertia,
            steering_deg,
            dt,
            tuple(capacities),
            tuple(limits),
            tuple(arms),
            grip_budget,
            supported,
            est.tick,
        )
        esc_requests = self.stability_state.brake_requests

        est_wheels = tuple(
            SimpleNamespace(
                sample_support=supports[idx],
                rolling_radius=None,
                longitudinal_speed=float(wheel_vx[idx]),
                omega=float(wheel_omegas[idx]),
                sample_tick=est.tick,
            )
            for idx in range(4)
        )
        self.brake_states, pressures = brakes_advance(
            self.brake_config,
            self.brake_states,
            est_wheels,
            esc_requests,
            float(cfg.wheel_radius),
            dt,
        )
        # Simulation 内部仍执行一次 response_time 一阶滞后，此处输出调节后的目标制动指令。
        wheel_cmds = tuple(float(state.commanded) for state in self.brake_states)
        throttle = float(base_command.throttle) * float(self.stability_state.torque_scale)

        self.last_telemetry = {
            "est_vx_mps": est.vx_mps,
            "est_vy_right_mps": est.vy_right_mps,
            "est_yaw_rate_radps": est.yaw_rate_radps,
            "est_sideslip_deg": est.sideslip_deg,
            "est_mu": est.mu_est,
            "vx_std_mps": est.vx_std_mps,
            "beta_std_deg": est.beta_std_deg,
            "gnss_nis": est.gnss_nis,
            "wheel_nis": est.wheel_nis,
            "wheel_accepted": est.wheel_accepted,
            "esc_active": self.stability_state.active,
            "abs_active": any(s.abs_active for s in self.brake_states),
            "esc_reference_yaw_rate": self.stability_state.reference_yaw_rate,
            "esc_target_moment": self.stability_state.desired_brake_moment,
            "esc_allocated_moment": self.stability_state.allocated_brake_moment,
            "wheel_brakes": wheel_cmds,
            "wheel_pressures": tuple(float(p) for p in pressures),
        }
        return replace(base_command, throttle=throttle, wheel_brakes=wheel_cmds)

    def telemetry(self) -> dict:
        return dict(self.last_telemetry)
