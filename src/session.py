import math
from enum import Enum

from controls import Controller, KeyboardController
from highway_map import HIGHWAY_LENGTH
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
    def __init__(self, seed=0, *, track="coastal", scores=None, road_shape="straight"):
        self.road_shape = road_shape
        self.simulation = Simulation(seed, track=track, road_shape=road_shape)
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
        self.sync_snapshots()

    def sync_snapshots(self):
        self.last_control = Control()
        self.current = self.simulation.snapshot()
        self.previous = self.current

    def start(self, seed=None, *, countdown=True, mode=None, track=None):
        chosen_track = get_track(track) if track is not None else self.track
        chosen_mode = self.mode if mode is None else mode
        if chosen_mode == GameMode.TIME_TRIAL and chosen_track.circuit is None:
            raise ValueError("Time trial requires a circuit")
        track = chosen_track.id.value
        self.phase = Phase.LOADING
        self.notice = ""
        traffic_count = 8 if chosen_mode == GameMode.FREE_DRIVE and track != "test" else 0
        if chosen_mode == GameMode.FREE_DRIVE and track == "endless":
            traffic_count = 12
        if seed is not None:
            self.seed = seed
        if track is not None and track != self.simulation.track:
            self.simulation.close()
            self.simulation = Simulation(self.seed, track=track, traffic_count=traffic_count, road_shape=self.road_shape)
            self.track = get_track(track)
        else:
            self.simulation.road_shape = self.road_shape
            self.simulation.traffic_count = traffic_count
            self.simulation.reset(self.seed)
        self.mode = chosen_mode
        self.simulation.set_checkpoint_frames_enabled(self.mode == GameMode.TIME_TRIAL)
        self.race.start(self.mode, circuit=self.track.circuit)
        self.keyboard.clear()
        self.controller = self.keyboard
        self.stepper.reset()
        self.countdown_ticks = 360 if countdown else 0
        self.phase = Phase.COUNTDOWN if countdown else Phase.DRIVING
        if not countdown:
            self.race.begin()
        self._skip_frame = True
        self.sync_snapshots()

    def set_controller(self, controller: Controller):
        self.keyboard.clear()
        self.last_control = Control()
        self.controller = controller

    def tick(self):
        if self.phase == Phase.COUNTDOWN:
            self.countdown_ticks -= 1
            if self.countdown_ticks == 0:
                self.phase = Phase.DRIVING
                self.keyboard.clear()
                self.race.begin()
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
            if self.race.snapshot.finished:
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
        if self.phase in (Phase.DRIVING, Phase.COUNTDOWN):
            self.stepper.advance(elapsed, self.tick)
        return interpolate(self.previous, self.current, self.stepper.remainder / FIXED_DT)

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
        self.keyboard.clear()
        self.stepper.remainder = 0.0
        self.sync_snapshots()

    def menu(self):
        self.phase = Phase.MENU
        self.mode = GameMode.FREE_DRIVE
        self.simulation.set_checkpoint_frames_enabled(False)
        self.race.start(self.mode)
        self.keyboard.clear()
        self.stepper.remainder = 0.0
        self.sync_snapshots()

    def finish(self):
        self.race.stop()
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
