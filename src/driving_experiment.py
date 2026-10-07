"""20Hz直接执行器实验；每次请求推进同一Simulation的六个120Hz步。"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace

from panda3d.core import Vec3

from driving_modes import REFERENCE_CAR, DrivingMode
from sensor_run import SensingRun
from simulation import Simulation, Snapshot
from vehicle_contacts import read_wheel_contacts
from vehicle_state import VehicleCommand

CONTROL_TICKS = 6
RECORD_SCHEMA = "coastal-driving-experiment-v1"


@dataclass(frozen=True)
class ExperimentOptions:
    seed: int = 0
    track: str = "test"
    road_shape: str = "straight"
    traffic_count: int = 0
    maximum_control_steps: int = 1200
    terminate_on_collision: bool = True
    terminate_on_reset: bool = True
    initial_position: tuple | None = None
    initial_heading: float | None = None
    initial_pitch: float | None = None
    initial_speed: float = 0.

    def __post_init__(self):
        if not isinstance(self.maximum_control_steps, int) or self.maximum_control_steps < 1:
            raise ValueError("实验控制步数上限须为正整数")
        if not math.isfinite(self.initial_speed):
            raise ValueError("实验初始速度须为有限值m/s")


EXPERIMENT = ExperimentOptions()


@dataclass(frozen=True)
class ExperimentObservation:
    control_step: int
    snapshot: Snapshot
    events: tuple
    impacts: tuple
    sensing: tuple
    terminated: bool
    truncated: bool
    reason: str | None


def observation_digest(observation):
    """运行实例ID不属于物理重放结果；其余全部状态与测量进入精确摘要。"""
    document = asdict(observation)
    del document["snapshot"]["contact_epoch"]
    for impact in (*document["snapshot"]["impacts"], *document["impacts"]):
        del impact["epoch"]
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class DrivingExperiment:
    def __init__(self, vehicle_config=REFERENCE_CAR, options=EXPERIMENT,
                 *, mode=DrivingMode.SIMULATION, sensors=None, sensor_seed=100):
        self.vehicle_config, self.options, self.mode = vehicle_config, options, mode
        self.sensor_config, self.sensor_seed = sensors, sensor_seed
        self.simulation = Simulation(options.seed, track=options.track, road_shape=options.road_shape,
                                     traffic_count=options.traffic_count, config=vehicle_config,
                                     input_config=mode.input_config, traffic_input_config=mode.input_config)
        self._begin()

    def _begin(self):
        options = self.options
        initial = self.simulation.snapshot()
        if any(value is not None for value in (options.initial_position, options.initial_heading, options.initial_pitch)):
            position = initial.player.position if options.initial_position is None else options.initial_position
            heading = initial.player.heading if options.initial_heading is None else options.initial_heading
            pitch = initial.player.pitch if options.initial_pitch is None else options.initial_pitch
            self.simulation.reset_player(position, heading, pitch)
            initial = self.simulation.snapshot()
        if options.initial_speed:
            player = self.simulation.player
            direction = player._chassis.getTransform().getQuat().getForward()
            player._chassis.setLinearVelocity(Vec3(direction * options.initial_speed))
            player.tires.initialize_rolling(options.initial_speed)
            player.powertrain.initialize_rolling(options.initial_speed)
            player.tires.observe(player._chassis, read_wheel_contacts(player._vehicle, player.on_asphalt), initial.tick)
            initial = self.simulation.snapshot()
        self.initial = initial
        self.sensing = (SensingRun(initial, self.vehicle_config, self.sensor_config, self.sensor_seed)
                        if self.sensor_config is not None else None)
        self.control_step, self.done = 0, False
        self.records = []
        self.current = ExperimentObservation(0, initial, initial.events, initial.impacts, (), False, False, None)
        return self.current

    def reset(self, seed=None):
        if seed is not None:
            self.options = replace(self.options, seed=seed)
        self.simulation.reset(self.options.seed)
        return self._begin()

    def step(self, command: VehicleCommand):
        if self.done:
            raise RuntimeError("实验已结束；reset后再给新的控制请求")
        events, impacts, sensing = [], [], []
        before = self.current.snapshot
        reset_seen = collision_seen = False
        for _ in range(CONTROL_TICKS):
            self.simulation.step(command)
            snapshot = self.simulation.snapshot()
            events.extend(snapshot.events)
            impacts.extend(snapshot.impacts)
            reset_seen |= snapshot.contact_epoch != before.contact_epoch
            collision_seen |= snapshot.collisions > before.collisions
            if self.sensing is not None:
                sensing.append(self.sensing.observe(snapshot))
        self.control_step += 1
        collision = self.options.terminate_on_collision and collision_seen
        recovered = self.options.terminate_on_reset and reset_seen
        terminated = collision or recovered
        truncated = self.control_step >= self.options.maximum_control_steps
        reason = "collision" if collision else "reset" if recovered else "time_limit" if truncated else None
        self.current = ExperimentObservation(self.control_step, snapshot, tuple(events), tuple(impacts), tuple(sensing),
                                             terminated, truncated, reason)
        self.done = terminated or truncated
        self.records.append({"command": asdict(command), "observation": asdict(self.current),
                             "digest": observation_digest(self.current)})
        return self.current

    def close(self):
        self.simulation.close()
