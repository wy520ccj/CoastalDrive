"""CG处IMU、四轮编码器和GNSS；采样噪声与唯一物理世界分开。"""

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from estimation_rotation import conjugate, exp, log, matrix, multiply

DT = 1 / 120
GRAVITY = np.array((0., 0., -9.81))


@dataclass(frozen=True)
class SensorConfig:
    """白噪声为每个采样的标准差；偏置游走为对应单位/√s，延迟以120Hz拍计。"""
    wheel_period_ticks: int = 2
    gnss_period_ticks: int = 12
    gnss_delay_ticks: int = 12
    accel_sample_std: float = .035
    gyro_sample_std: float = .001
    accel_bias_walk: float = .002
    gyro_bias_walk: float = .00005
    initial_accel_bias: tuple = (.05, -.03, .02)
    initial_gyro_bias: tuple = (.0005, -.001, .0015)
    wheel_omega_std: float = .05
    steering_std_rad: float = math.radians(.05)
    gnss_position_std: tuple = (1., 1., 1.5)
    gnss_velocity_std: tuple = (.08, .08, .12)
    gnss_outages: tuple = ()

    def __post_init__(self):
        if any(not isinstance(value, int) for value in
               (self.wheel_period_ticks, self.gnss_period_ticks, self.gnss_delay_ticks)) or (
                self.wheel_period_ticks < 1 or self.gnss_period_ticks < 1 or self.gnss_delay_ticks < 0):
            raise ValueError("传感器采样周期须为正拍数、延迟须为非负拍数")
        vectors = (self.initial_accel_bias, self.initial_gyro_bias, self.gnss_position_std, self.gnss_velocity_std)
        if any(len(vector) != 3 or any(not math.isfinite(value) for value in vector) for vector in vectors):
            raise ValueError("传感器偏置及GNSS标准差须为三个有限值")
        if any(len(interval) != 2 or any(not isinstance(value, int) for value in interval)
               or not 0 <= interval[0] < interval[1] for interval in self.gnss_outages):
            raise ValueError("GNSS失联窗口须为非负起拍和更大的结束拍，采用左闭右开区间")
        noise = (self.accel_sample_std, self.gyro_sample_std, self.accel_bias_walk, self.gyro_bias_walk,
                 self.wheel_omega_std, self.steering_std_rad, *self.gnss_position_std, *self.gnss_velocity_std)
        if any(not math.isfinite(value) or value < 0. for value in noise):
            raise ValueError("传感器标准差须为有限非负值")


SENSORS = SensorConfig()


@dataclass(frozen=True)
class TruthSample:
    tick: int
    position: tuple
    velocity: tuple
    orientation: tuple
    wheel_omega: tuple
    wheel_steering: tuple


@dataclass(frozen=True)
class ImuSample:
    tick: int
    specific_force: tuple
    angular_velocity: tuple


@dataclass(frozen=True)
class WheelSample:
    tick: int
    omega: tuple
    steering: tuple


@dataclass(frozen=True)
class GnssSample:
    tick: int
    delivery_tick: int
    position: tuple
    velocity: tuple


@dataclass(frozen=True)
class SensorFrame:
    imu: ImuSample
    wheels: WheelSample | None
    gnss: tuple


class SensorSuite:
    def __init__(self, initial, config=SENSORS, seed=0):
        self.config = config
        self.reset(initial, seed)

    def reset(self, initial, seed=0):
        self.previous = initial
        seeds = np.random.SeedSequence(seed).spawn(3)
        self.imu_rng, self.wheel_rng, self.gnss_rng = (np.random.default_rng(item) for item in seeds)
        self.accel_bias = np.array(self.config.initial_accel_bias, dtype=float)
        self.gyro_bias = np.array(self.config.initial_gyro_bias, dtype=float)
        self.pending = deque()

    def sample(self, truth):
        config = self.config
        rotation = log(multiply(conjugate(self.previous.orientation), truth.orientation))
        midpoint = multiply(self.previous.orientation, exp(rotation / 2))
        acceleration = (np.asarray(truth.velocity) - self.previous.velocity) / DT
        specific = matrix(midpoint).T @ (acceleration - GRAVITY)
        self.accel_bias += self.imu_rng.normal(0., config.accel_bias_walk * math.sqrt(DT), 3)
        self.gyro_bias += self.imu_rng.normal(0., config.gyro_bias_walk * math.sqrt(DT), 3)
        imu = ImuSample(truth.tick,
                        tuple(specific + self.accel_bias + self.imu_rng.normal(0., config.accel_sample_std, 3)),
                        tuple(rotation / DT + self.gyro_bias + self.imu_rng.normal(0., config.gyro_sample_std, 3)))
        wheels = None
        if truth.tick % config.wheel_period_ticks == 0:
            wheels = WheelSample(truth.tick,
                tuple(np.asarray(truth.wheel_omega) + self.wheel_rng.normal(0., config.wheel_omega_std, 4)),
                tuple(np.asarray(truth.wheel_steering) + self.wheel_rng.normal(0., config.steering_std_rad, 4)))
        if truth.tick % config.gnss_period_ticks == 0 and not any(a <= truth.tick < b for a, b in config.gnss_outages):
            self.pending.append(GnssSample(truth.tick, truth.tick + config.gnss_delay_ticks,
                tuple(np.asarray(truth.position) + self.gnss_rng.normal(0., config.gnss_position_std)),
                tuple(np.asarray(truth.velocity) + self.gnss_rng.normal(0., config.gnss_velocity_std))))
        delivered = []
        while self.pending and self.pending[0].delivery_tick <= truth.tick:
            delivered.append(self.pending.popleft())
        self.previous = truth
        return SensorFrame(imu, wheels, tuple(delivered))
