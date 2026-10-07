"""Snapshot之后的独立采样/估计；Simulation与电子控制不依赖本模块。"""

import math
from dataclasses import dataclass

import numpy as np

from sensor_sampling import SENSORS, SensorFrame, SensorSuite, TruthSample
from state_estimation import Estimate, EstimatorTimeline, VehicleEstimator
from vehicle_config import wheel_hubs


def truth_sample(snapshot):
    player = snapshot.player
    x, y, z = player.position
    orientation = np.asarray(player.orientation)
    return TruthSample(snapshot.tick, (x, y + snapshot.origin_y, z), player.velocity,
                       tuple(orientation / np.linalg.norm(orientation)),
                       tuple(wheel.relative_omega for wheel in player.wheel_dynamics),
                       tuple(math.radians(wheel.steering) for wheel in player.wheel_dynamics))


@dataclass(frozen=True)
class SensingState:
    measurements: SensorFrame | None
    estimate: Estimate
    reset: bool


class SensingRun:
    def __init__(self, initial, vehicle_config, sensors=SENSORS, seed=0):
        self.vehicle_config, self.sensor_config, self.seed = vehicle_config, sensors, seed
        self.reset(initial)

    def reset(self, snapshot):
        """reset工况的已知初始位姿/速度只用于初始化；运行中估计不读取真值更新。"""
        initial = truth_sample(snapshot)
        self.epoch = snapshot.contact_epoch
        self.sensors = SensorSuite(initial, self.sensor_config, self.seed)
        estimator = VehicleEstimator(initial.position, initial.velocity, initial.orientation,
                                     self.vehicle_config.wheel_radius, wheel_hubs(self.vehicle_config),
                                     self.sensor_config, tick=snapshot.tick)
        self.timeline = EstimatorTimeline(estimator)
        self.state = SensingState(None, estimator.snapshot(), True)
        return self.state

    def observe(self, snapshot):
        if snapshot.contact_epoch != self.epoch:
            return self.reset(snapshot)
        measured = self.sensors.sample(truth_sample(snapshot))
        self.state = SensingState(measured, self.timeline.advance(measured), False)
        return self.state
