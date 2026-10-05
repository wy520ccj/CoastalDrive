import hashlib
import json
import math
from dataclasses import asdict, replace
from enum import Enum

from controls import Controller, KeyboardController
from driving_modes import DrivingMode
from highway_map import HIGHWAY_LENGTH
from highway_run import TRAFFIC_DENSITIES, HighwayRun
from race import GameMode, RaceTracker
from simulation import FIXED_DT, Control, Simulation, interpolate
from tracks import get_track


class Phase(Enum):
    MENU = "menu"
    LOADING = "loading"
    COUNTDOWN = "countdown"
    DRIVING = "driving"
    PAUSED = "paused"
    RESULTS = "results"


class FixedStepper:
    def __init__(self):
        self.reset()

    def reset(self):
        self.remainder = 0.0
        self.dropped_time = 0.0

    def advance(self, elapsed, tick):
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("Frame time must be finite and nonnegative")
        self.remainder += elapsed
        available = int((self.remainder + 1e-12) / FIXED_DT)
        count = min(available, 8)
        self.remainder = max(0.0, self.remainder - available * FIXED_DT)
        self.dropped_time += (available - count) * FIXED_DT
        for _ in range(count):
            tick()
        return count


class Session:
    def __init__(self, seed=0, *, track="coastal", scores=None, road_shape="straight",
                 driving_mode=DrivingMode.GAME, abs_enabled=None, tcs_enabled=None, esc_enabled=None,
                 vehicle_config=None):
        self.road_shape = road_shape
        self.traffic_density = "normal"
        self.driving_mode = driving_mode
        self.base_vehicle_config = vehicle_config
        self.vehicle_config = driving_mode.configured_vehicle(abs_enabled, tcs_enabled, esc_enabled,
                                                              base_config=vehicle_config)
        self.simulation = Simulation(
            seed, track=track, road_shape=road_shape,
            config=self.vehicle_config, input_config=driving_mode.input_config,
        )
        self.track = get_track(track)
        self.keyboard = KeyboardController()
        self.controller = self.keyboard
        self.stepper = FixedStepper()
        self.phase = Phase.MENU
        self.seed = seed
        self.countdown_ticks = 0
        self.camera_distance = 11.0
        self._resume_phase = Phase.DRIVING
        self._skip_frame = True
        self.mode = GameMode.FREE_DRIVE
        self.notice = ""
        self.race = RaceTracker(self.mode, scores=scores)
        self.highway = HighwayRun()
        self.sync_snapshots()

    def sync_snapshots(self):
        self.last_control = Control()
        self.current = self.simulation.snapshot()
        self.previous = self.current

    def set_driving_mode(self, mode):
        """菜单选择下一场驾驶配置；开始时重建权威物理世界。"""
        if self.phase != Phase.MENU:
            raise ValueError("驾驶模式只能在主菜单选择")
        self.driving_mode = mode
        self.vehicle_config = mode.configured_vehicle(self.abs_enabled, self.tcs_enabled, self.esc_enabled,
                                                      base_config=self.base_vehicle_config)

    def set_vehicle_config(self, config):
        """菜单确认硬件设计；保持电子开关，下一场重建唯一物理世界。"""
        if self.phase != Phase.MENU:
            raise ValueError("车辆硬件只能在主菜单选择")
        self.base_vehicle_config = config
        self.vehicle_config = self.driving_mode.configured_vehicle(
            self.abs_enabled, self.tcs_enabled, self.esc_enabled, base_config=config)

    @property
    def abs_enabled(self):
        return self.vehicle_config.braking.abs_enabled

    def set_abs_enabled(self, enabled):
        """菜单选择车辆电子配置；不替换正在运行的刚体参数。"""
        if self.phase != Phase.MENU:
            raise ValueError("车辆电子配置只能在主菜单选择")
        self.vehicle_config = self.driving_mode.configured_vehicle(enabled, self.tcs_enabled, self.esc_enabled,
                                                                   base_config=self.base_vehicle_config)

    @property
    def tcs_enabled(self):
        return self.vehicle_config.traction.tcs_enabled

    def set_tcs_enabled(self, enabled):
        """菜单选择驱动防滑配置；不替换正在运行的刚体参数。"""
        if self.phase != Phase.MENU:
            raise ValueError("车辆电子配置只能在主菜单选择")
        self.vehicle_config = self.driving_mode.configured_vehicle(self.abs_enabled, enabled, self.esc_enabled,
                                                                   base_config=self.base_vehicle_config)

    @property
    def esc_enabled(self):
        return self.vehicle_config.stability.esc_enabled

    def set_esc_enabled(self, enabled):
        """菜单选择横摆稳定配置；下一场起步应用。"""
        if self.phase != Phase.MENU:
            raise ValueError("车辆电子配置只能在主菜单选择")
        self.vehicle_config = self.driving_mode.configured_vehicle(
            self.abs_enabled, self.tcs_enabled, enabled, base_config=self.base_vehicle_config)

    def start(self, seed=None, *, countdown=True, mode=None, track=None):
        chosen_track = get_track(track) if track is not None else self.track
        chosen_mode = self.mode if mode is None else mode
        if chosen_mode == GameMode.TIME_TRIAL and chosen_track.circuit is None:
            raise ValueError("Time trial requires a circuit")
        if chosen_mode == GameMode.DISTANCE_CHALLENGE and chosen_track.id.value != "endless":
            raise ValueError("Distance challenge requires the endless highway")
        track = chosen_track.id.value
        self.phase = Phase.LOADING
        self.notice = ""
        traffic_count = 8 if chosen_mode == GameMode.FREE_DRIVE and track != "test" else 0
        density = TRAFFIC_DENSITIES[self.traffic_density]
        if track == "endless":
            traffic_count = density.cars
        if seed is not None:
            self.seed = seed
        if (track != self.simulation.track
                or self.simulation.config is not self.vehicle_config
                or self.simulation.input_config is not self.driving_mode.input_config):
            self.simulation.close()
            self.simulation = Simulation(
                self.seed, track=track, traffic_count=traffic_count,
                road_shape=self.road_shape, traffic_span=density.spawn_span,
                config=self.vehicle_config, input_config=self.driving_mode.input_config,
            )
            self.track = get_track(track)
        else:
            self.simulation.road_shape = self.road_shape
            self.simulation.traffic_count = traffic_count
            self.simulation.traffic_span = density.spawn_span
            self.simulation.reset(self.seed)
        self.mode = chosen_mode
        self.simulation.set_checkpoint_frames_enabled(self.mode == GameMode.TIME_TRIAL)
        self.race.start(
            self.mode, circuit=self.track.circuit,
            score_variant=self.score_variant(),
        )
        self.highway = HighwayRun(challenge=self.mode == GameMode.DISTANCE_CHALLENGE)
        self.keyboard.direction = 1
        self.keyboard.clear()
        self.controller = self.keyboard
        self.stepper.reset()
        self.countdown_ticks = 360 if countdown else 0
        self.phase = Phase.COUNTDOWN if countdown else Phase.DRIVING
        if not countdown:
            self.begin_driving()
        self._skip_frame = True
        self.sync_snapshots()

    def score_variant(self):
        """工程硬件与输入模式/电子开关共同隔离成绩。"""
        variant = self.driving_mode.score_variant(self.abs_enabled, self.tcs_enabled, self.esc_enabled)
        if self.base_vehicle_config is not None:
            data = json.dumps(asdict(self.vehicle_config), sort_keys=True, separators=(",", ":"))
            variant += ":hardware-"+hashlib.sha256(data.encode()).hexdigest()[:16]
        return variant

    def set_controller(self, controller: Controller):
        self.keyboard.clear()
        self.last_control = Control()
        self.controller = controller

    def highway_progress(self, state=None):
        if state is None:
            state = self.simulation.snapshot()
        distance, _ = self.simulation.road.locate(state.player)
        return distance if self.simulation.road.curve else distance + state.origin_y

    def begin_driving(self):
        if self.simulation.track == "endless":
            self.highway.start(
                self.highway_progress(), challenge=self.mode == GameMode.DISTANCE_CHALLENGE
            )
        else:
            self.race.begin()

    def tick(self):
        if self.phase == Phase.COUNTDOWN:
            self.countdown_ticks -= 1
            if self.countdown_ticks == 0:
                self.phase = Phase.DRIVING
                self.keyboard.clear()
                self.begin_driving()
        elif self.phase == Phase.DRIVING:
            self.previous = self.current
            self.last_control = self.controller.sample(self.current, FIXED_DT)
            self.simulation.step(self.last_control, FIXED_DT)
            self.current = self.simulation.snapshot()
            if "reset_blocked" in self.current.events:
                self.notice = "附近暂时没有安全空位，请稍后再试"
            if "player_reset" in self.current.events:
                self.notice = ""
                self.previous = self.current
                self.race.update(self.current, FIXED_DT, reset=True)
            else:
                self.race.update(self.current, FIXED_DT)
            if self.simulation.track == "endless":
                self.highway.update(
                    self.highway_progress(self.current), self.current.collisions, FIXED_DT,
                    reset="player_reset" in self.current.events,
                )
            if self.race.snapshot.finished or self.highway.snapshot.finished:
                self.phase = Phase.RESULTS
                self.keyboard.clear()
                self.previous = self.current
            elif (
                self.simulation.track == "highway"
                and self.current.player.position[1] >= HIGHWAY_LENGTH
            ):
                self.finish()

    def frame(self, elapsed):
        if self._skip_frame:
            elapsed = 0.0
            self._skip_frame = False
        collected = []
        epoch = self.current.contact_epoch
        frame_phase = self.phase

        def tick_and_collect():
            nonlocal epoch, collected
            before_tick = self.current.tick
            self.tick()
            latest = self.current
            if latest.contact_epoch != epoch:
                epoch = latest.contact_epoch
                collected = []
            if latest.tick > before_tick and latest.contact_epoch == epoch:
                collected.extend(latest.impacts)

        if self.phase in (Phase.DRIVING, Phase.COUNTDOWN):
            self.stepper.advance(elapsed, tick_and_collect)
        # 保留导致驾驶结束的最后一批事件；结果页后续帧自然没有新 tick。
        if (self.phase not in (Phase.DRIVING, Phase.RESULTS)
                or frame_phase in (Phase.PAUSED, Phase.MENU, Phase.RESULTS)):
            collected = []
        current = interpolate(self.previous, self.current, self.stepper.remainder / FIXED_DT)
        return replace(current, impacts=tuple(collected), contacts=self.current.contacts)

    def pause(self):
        if self.phase in (Phase.DRIVING, Phase.COUNTDOWN):
            self._resume_phase = self.phase
            self.phase = Phase.PAUSED
        self.keyboard.clear()
        self.stepper.remainder = 0.0
        self.sync_snapshots()

    def resume(self):
        if self.phase == Phase.PAUSED:
            self.phase = self._resume_phase
            self.keyboard.clear()
            self._skip_frame = True

    def focus_changed(self, foreground):
        if not foreground:
            self.pause()

    def reset_player(self):
        if not self.simulation.recover_player():
            self.notice = "附近暂时没有安全空位，请稍后再试"
            return
        self.notice = ""
        self.race.reset_player(self.simulation.snapshot())
        if self.simulation.track == "endless":
            self.highway.update(
                self.highway_progress(), self.simulation.player_collisions, 0, reset=True
            )
            if self.highway.snapshot.finished:
                self.phase = Phase.RESULTS
        self.keyboard.clear()
        self.stepper.remainder = 0.0
        self.sync_snapshots()

    def menu(self):
        self.phase = Phase.MENU
        self.mode = GameMode.FREE_DRIVE
        self.simulation.set_checkpoint_frames_enabled(False)
        self.race.start(self.mode)
        self.highway = HighwayRun()
        self.keyboard.clear()
        self.stepper.remainder = 0.0
        self.sync_snapshots()

    def finish(self):
        self.race.stop()
        self.highway.stop("挑战提前结束" if self.mode == GameMode.DISTANCE_CHALLENGE else "自由驾驶结束")
        self.phase = Phase.RESULTS
        self.keyboard.clear()
        self.stepper.remainder = 0.0
        self.sync_snapshots()

    def command(self, key):
        if key == "enter":
            if self.phase == Phase.MENU:
                self.start(mode=GameMode.TIME_TRIAL, track="coastal")
            elif self.phase == Phase.RESULTS:
                self.start(mode=self.mode, track=self.simulation.track)
            elif self.phase == Phase.PAUSED:
                self.resume()
        elif key == "escape":
            self.resume() if self.phase == Phase.PAUSED else self.pause()
        elif key == "r" and self.phase == Phase.DRIVING:
            self.reset_player()
        elif key == "c" and self.phase == Phase.DRIVING:
            self.camera_distance = 16.0 if self.camera_distance == 11.0 else 11.0

    def close(self):
        self.keyboard.clear()
        self.simulation.close()
