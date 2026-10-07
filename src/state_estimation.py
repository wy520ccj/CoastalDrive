"""固定重力的15维局部误差状态EKF；测量只更新估计，不回写物理。"""

from dataclasses import dataclass

import numpy as np

from estimation_rotation import exp, matrix, multiply, right_jacobian, skew
from sensor_sampling import DT, GRAVITY, SENSORS


def imu_jacobians(orientation, specific, omega):
    """同一中点姿态积分的误差/噪声导数，含陀螺误差到位移的交叉项。"""
    half = omega * DT / 2
    midpoint = matrix(multiply(orientation, exp(half)))
    acceleration_angle = -midpoint @ skew(specific) @ matrix(exp(half)).T
    acceleration_gyro_bias = midpoint @ skew(specific) @ right_jacobian(half) * (DT / 2)
    transition = np.eye(15)
    transition[:3, 3:6] = np.eye(3) * DT
    transition[:3, 6:9] = .5 * acceleration_angle * DT**2
    transition[:3, 9:12] = -.5 * midpoint * DT**2
    transition[:3, 12:15] = .5 * acceleration_gyro_bias * DT**2
    transition[3:6, 6:9] = acceleration_angle * DT
    transition[3:6, 9:12] = -midpoint * DT
    transition[3:6, 12:15] = acceleration_gyro_bias * DT
    transition[6:9, 6:9] = matrix(exp(omega * DT)).T
    transition[6:9, 12:15] = -right_jacobian(omega * DT) * DT
    inputs = np.zeros((15, 12))
    inputs[:3, :3] = -.5 * midpoint * DT**2
    inputs[3:6, :3] = -midpoint * DT
    inputs[:3, 3:6] = .5 * acceleration_gyro_bias * DT**2
    inputs[3:6, 3:6] = acceleration_gyro_bias * DT
    inputs[6:9, 3:6] = -right_jacobian(omega * DT) * DT
    inputs[9:12, 6:9] = np.eye(3)
    inputs[12:15, 9:12] = np.eye(3)
    return transition, inputs


@dataclass(frozen=True)
class Estimate:
    tick: int
    position: tuple
    velocity: tuple
    orientation: tuple
    accel_bias: tuple
    gyro_bias: tuple
    covariance_diagonal: tuple
    gnss_nis: float | None
    wheel_nis: float | None
    wheel_accepted: bool | None


class VehicleEstimator:
    def __init__(self, position, velocity, orientation, wheel_radius, wheel_hubs,
                 noise=SENSORS, *, tick=0, wheel_model_std=.25):
        self.tick = tick
        self.position = np.array(position, dtype=float)
        self.velocity = np.array(velocity, dtype=float)
        self.orientation = np.asarray(orientation, dtype=float) / np.linalg.norm(orientation)
        self.accel_bias = np.zeros(3)
        self.gyro_bias = np.zeros(3)
        self.covariance = np.diag(np.array((2.,) * 3 + (.3,) * 3 + (.1,) * 3 + (.15,) * 3 + (.02,) * 3)**2)
        self.wheel_radius, self.wheel_hubs = wheel_radius, np.asarray(wheel_hubs)
        self.noise, self.wheel_model_std = noise, wheel_model_std
        self.gnss_nis = self.wheel_nis = self.wheel_accepted = None
        self.angular_measurement = np.zeros(3)

    def predict(self, sample):
        omega = np.asarray(sample.angular_velocity) - self.gyro_bias
        specific = np.asarray(sample.specific_force) - self.accel_bias
        transition, inputs = imu_jacobians(self.orientation, specific, omega)
        midpoint = matrix(multiply(self.orientation, exp(omega * DT / 2)))
        acceleration = midpoint @ specific + GRAVITY
        self.position += self.velocity * DT + .5 * acceleration * DT**2
        self.velocity += acceleration * DT
        self.orientation = multiply(self.orientation, exp(omega * DT))
        self.orientation /= np.linalg.norm(self.orientation)
        noise = np.array((self.noise.accel_sample_std**2,) * 3 + (self.noise.gyro_sample_std**2,) * 3
                        + (self.noise.accel_bias_walk**2 * DT,) * 3 + (self.noise.gyro_bias_walk**2 * DT,) * 3)
        self.covariance = transition @ self.covariance @ transition.T + (inputs * noise) @ inputs.T
        self.tick = sample.tick
        self.angular_measurement = np.asarray(sample.angular_velocity)

    def _update(self, residual, observation, variance, gate=None):
        innovation_covariance = observation @ self.covariance @ observation.T + np.diag(variance)
        nis = float(residual @ np.linalg.solve(innovation_covariance, residual))
        if gate is not None and nis > gate:
            return nis, False
        gain = np.linalg.solve(innovation_covariance, observation @ self.covariance).T
        correction = gain @ residual
        identity = np.eye(15) - gain @ observation
        self.covariance = identity @ self.covariance @ identity.T + (gain * variance) @ gain.T
        self.position += correction[:3]
        self.velocity += correction[3:6]
        self.orientation = multiply(self.orientation, exp(correction[6:9]))
        self.orientation /= np.linalg.norm(self.orientation)
        self.accel_bias += correction[9:12]
        self.gyro_bias += correction[12:15]
        reset = np.eye(15)
        reset[6:9, 6:9] = right_jacobian(correction[6:9])
        self.covariance = reset @ self.covariance @ reset.T
        self.covariance = (self.covariance + self.covariance.T) / 2
        return nis, True

    def update_gnss(self, sample):
        observed = np.array((*sample.position, *sample.velocity))
        prediction = np.r_[self.position, self.velocity]
        observation = np.zeros((6, 15))
        observation[:, :6] = np.eye(6)
        variance = np.array((*self.noise.gnss_position_std, *self.noise.gnss_velocity_std))**2
        self.gnss_nis, _accepted = self._update(observed - prediction, observation, variance)

    def update_wheels(self, sample):
        rotation = matrix(self.orientation)
        body_velocity = rotation.T @ self.velocity
        angular = self.angular_measurement - self.gyro_bias
        steering = np.asarray(sample.steering)
        tangents = np.column_stack((np.sin(steering), np.cos(steering), np.zeros(4)))
        point_velocity = body_velocity + np.cross(angular, self.wheel_hubs)
        predicted = np.sum(tangents * point_velocity, axis=1)
        observation = np.zeros((4, 15))
        observation[:, 3:6] = tangents @ rotation.T
        observation[:, 6:9] = tangents @ skew(body_velocity)
        observation[:, 12:15] = np.array([tangent @ skew(hub) for tangent, hub in zip(tangents, self.wheel_hubs)])
        direction_derivative = np.column_stack((np.cos(steering), -np.sin(steering), np.zeros(4)))
        steering_variance = (np.sum(direction_derivative * point_velocity, axis=1) * self.noise.steering_std_rad)**2
        variance = ((self.wheel_radius * self.noise.wheel_omega_std)**2
                    + self.wheel_model_std**2 + steering_variance)
        # 轮滑只通过测量创新识别，不读取真值滑移/接触力，也不强制车身横向速度为零。
        self.wheel_nis, self.wheel_accepted = self._update(
            self.wheel_radius * np.asarray(sample.omega) - predicted, observation, variance, gate=16.)

    def snapshot(self):
        return Estimate(self.tick, tuple(self.position), tuple(self.velocity), tuple(self.orientation),
                        tuple(self.accel_bias), tuple(self.gyro_bias), tuple(np.diag(self.covariance)),
                        self.gnss_nis, self.wheel_nis, self.wheel_accepted)

    def save_state(self):
        return (self.snapshot(), self.covariance.copy(), self.angular_measurement.copy())

    def restore_state(self, state):
        saved, covariance, angular = state
        self.tick = saved.tick
        self.position, self.velocity, self.orientation, self.accel_bias, self.gyro_bias = (
            np.array(value) for value in (saved.position, saved.velocity, saved.orientation, saved.accel_bias, saved.gyro_bias))
        self.covariance, self.angular_measurement = covariance.copy(), angular.copy()
        self.gnss_nis, self.wheel_nis, self.wheel_accepted = saved.gnss_nis, saved.wheel_nis, saved.wheel_accepted


class EstimatorTimeline:
    def __init__(self, estimator, history_ticks=120):
        if history_ticks < estimator.noise.gnss_delay_ticks:
            raise ValueError("估计历史窗不能短于声明GNSS延迟")
        self.estimator, self.history_ticks = estimator, history_ticks
        self.history = {estimator.tick: estimator.save_state()}
        self.measurements = {estimator.tick: (None, None, [])}

    def advance(self, frame):
        estimator = self.estimator
        tick = frame.imu.tick
        self.measurements[tick] = (frame.imu, frame.wheels, [])
        estimator.predict(frame.imu)
        if frame.wheels is not None:
            estimator.update_wheels(frame.wheels)
        self.history[tick] = estimator.save_state()
        for sample in frame.gnss:
            estimator.restore_state(self.history[sample.tick])
            estimator.update_gnss(sample)
            self.measurements[sample.tick][2].append(sample)
            self.history[sample.tick] = estimator.save_state()
            for replay_tick in range(sample.tick + 1, tick + 1):
                imu, wheels, gnss = self.measurements[replay_tick]
                estimator.predict(imu)
                if wheels is not None:
                    estimator.update_wheels(wheels)
                for old in gnss:
                    estimator.update_gnss(old)
                self.history[replay_tick] = estimator.save_state()
        floor = tick - self.history_ticks
        for old in tuple(self.history):
            if old < floor:
                del self.history[old]
                del self.measurements[old]
        return estimator.snapshot()
