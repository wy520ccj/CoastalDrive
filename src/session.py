import hashlib
import json
import logging
import math
import os
from contextlib import nullcontext
from dataclasses import asdict, replace
from enum import Enum

from braking_lesson import BRAKING_MODES, BrakingScores
from career import EVENT_BY_ID
from career_run import CareerResult
from challenge_build import BuildDraft
from challenge_catalog import (
    ROAD_CHALLENGES,
    course_gates,
    course_key,
    course_track,
    distance_challenge_spec,
)
from challenge_run import ChallengeRun
from challenge_scores import ChallengeScores
from challenge_trace import ChallengeTrace
from controls import Controller, KeyboardController
from driving_modes import DrivingMode
from highway_map import HIGHWAY_LENGTH
from highway_run import TRAFFIC_DENSITIES, HighwayRun
from lap_ghost import GhostRecorder, ghost_context, load_ghost, record_context, save_ghost
from overtake_routes import OVERTAKE_ROUTES
from race import BestTimes, GameMode, RaceTracker
from sector_chase import CHASE_COURSES, CHASE_INPUT, CHASE_VERSION
from session_clock import SessionClock
from simulation import FIXED_DT, Control, Simulation, interpolate
from slalom_lesson import SLALOM_MODES, SlalomScores
from sprint_routes import SPRINT_ROUTES
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

    def advance(self, elapsed, tick, *, max_steps=8):
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("Frame time must be finite and nonnegative")
        self.remainder += elapsed
        available = int((self.remainder + 1e-12) / FIXED_DT)
        count = min(available, max_steps)
        for _ in range(count):
            # 每批限制步数只用于交还执行机会；未完成时间留到下一批真实计算，不能删掉。
            self.remainder = max(0.0, self.remainder - FIXED_DT)
            tick()
        return count

    @property
    def backlog_time(self):
        return int((self.remainder + 1e-12) / FIXED_DT) * FIXED_DT


class Session:
    def __init__(self, seed=0, *, track="coastal", scores=None, road_shape="straight",
                 driving_mode=DrivingMode.GAME, abs_enabled=None, tcs_enabled=None, esc_enabled=None,
                 vehicle_config=None, physics_workers=0, independent_clock=False):
        self.independent_clock = independent_clock
        self._clock = None
        self.physics_workers = physics_workers
        self.road_shape = road_shape
        self.traffic_density = "normal"
        self.driving_mode = driving_mode
        self.base_vehicle_config = vehicle_config
        self.vehicle_config = driving_mode.configured_vehicle(abs_enabled, tcs_enabled, esc_enabled,
                                                              base_config=vehicle_config)
        self.simulation = Simulation(
            seed, track=track, road_shape=road_shape,
            config=self.vehicle_config, input_config=driving_mode.input_config,
            physics_workers=self.physics_worker_count(),
        )
        self.track = get_track(track)
        self.keyboard = KeyboardController(self.driving_mode.input_config)
        self.controller = self.keyboard
        self.stepper = FixedStepper()
        self.phase = Phase.MENU
        self.seed = seed
        self.countdown_ticks = 0
        self._settling_initial = False
        self.camera_distance = 11.0
        self._resume_phase = Phase.DRIVING
        self._skip_frame = True
        self.mode = GameMode.FREE_DRIVE
        self.career_event_id = None
        self.challenge_spec = self.challenge_build = self.engineering = None
        self.sector_chase, self.practice_sector = False, None
        self._challenge_original = None
        self._pending_score_stores = []
        self.notice = ""
        self.race = RaceTracker(self.mode, scores=scores)
        self.reference_ghost = None
        self.ghost_recording = None
        self.ghost_conditions = None
        self._coastal_source = None
        self._coastal_challenge_scores = None
        self.highway = HighwayRun()
        self.sync_snapshots()

    def physics_worker_count(self):
        """窗口自动选择：正常模式只求完整玩家，困难模式仍并行全部车辆。"""
        if self.physics_workers is not None:
            return self.physics_workers
        if self.driving_mode == DrivingMode.GAME:
            return 0
        return min(9, max(0, (os.process_cpu_count() or 1) - 1))

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

    def start(self, seed=None, *, countdown=True, mode=None, track=None, settle_initial=False, career_event_id=None,
              challenge_spec=None, build=None, sector_chase=False, practice_sector=None):
        self.stop_clock()
        chosen_track = get_track(track) if track is not None else self.track
        chosen_mode = self.mode if mode is None else mode
        same_event = chosen_mode != GameMode.CAREER or career_event_id in (None, self.career_event_id)
        if challenge_spec is None and self.challenge_spec is not None and chosen_mode == self.mode and same_event:
            challenge_spec = self.challenge_spec
            build = self.challenge_build if build is None else build
            sector_chase, practice_sector = self.sector_chase, self.practice_sector
        if sector_chase:
            chase = CHASE_COURSES.get(chosen_mode)
            group = self.driving_mode.score_variant(self.abs_enabled, self.tcs_enabled, self.esc_enabled)
            if (chase is None or challenge_spec != ROAD_CHALLENGES[chosen_mode]
                    or group != CHASE_INPUT or chosen_mode == GameMode.TIME_TRIAL and seed not in (None, 0)):
                raise ValueError('追时须使用指定赛道、车辆和游戏驾驶辅助')
            if practice_sector is not None and (type(practice_sector) is not int
                                               or not 0 <= practice_sector < len(chase.reference)):
                raise ValueError('练习赛段不存在')
            seed = 0 if chosen_mode == GameMode.TIME_TRIAL else SPRINT_ROUTES[chosen_mode].seed
        elif practice_sector is not None:
            raise ValueError('单段练习须指定追时赛事')
        if challenge_spec is not None:
            event_id = career_event_id if career_event_id is not None else self.career_event_id
            key = course_key(chosen_mode, event_id)
            expected = ROAD_CHALLENGES.get(key)
            if (expected is None or challenge_spec.id != expected.id
                    or challenge_spec.distance_m != expected.distance_m
                    or chosen_track.id.value != course_track(key)):
                raise ValueError('工程挑战与实际驾驶路线不一致')
            if chosen_mode == GameMode.DISTANCE_CHALLENGE:
                seed = 0 if seed is None else seed
                challenge_spec = distance_challenge_spec(self.road_shape, self.traffic_density, seed)
            build = BuildDraft() if build is None else build
            candidate = challenge_spec.configuration(build)
            actual = self.driving_mode.configured_vehicle(base_config=candidate)
            if actual != candidate:
                raise ValueError('挑战原车须使用本次实际驾驶的机械细分配置')
            if self._challenge_original is None:
                self._challenge_original = self.base_vehicle_config, self.vehicle_config
            self.base_vehicle_config = self.vehicle_config = candidate
            self._end_challenge_run('重新准备车辆')
        else:
            if build is not None:
                raise ValueError('改装方案须指定所属挑战')
            self.leave_challenge()
        self.challenge_spec, self.challenge_build = challenge_spec, build
        self.sector_chase, self.practice_sector = sector_chase, practice_sector
        self.engineering = None
        self.career_event_id = (career_event_id if career_event_id is not None else self.career_event_id
                                if chosen_mode == GameMode.CAREER else None)
        if chosen_mode == GameMode.CAREER:
            if self.career_event_id not in EVENT_BY_ID:
                raise ValueError('生涯赛事未指定')
            event = EVENT_BY_ID[self.career_event_id]
            self.road_shape, seed = event.shape, event.seed
        if chosen_mode == GameMode.TIME_TRIAL and chosen_track.circuit is None:
            raise ValueError("Time trial requires a circuit")
        if (chosen_mode in (GameMode.CAREER, GameMode.DISTANCE_CHALLENGE, *BRAKING_MODES, *SLALOM_MODES, *OVERTAKE_ROUTES)
                or chosen_mode in SPRINT_ROUTES) and chosen_track.id.value != "endless":
            raise ValueError("Distance challenge requires the endless highway")
        if chosen_mode in (*BRAKING_MODES, *SLALOM_MODES) and self.road_shape != "straight":
            raise ValueError("驾驶课题需要直线道路")
        if chosen_mode in SPRINT_ROUTES:
            route = SPRINT_ROUTES[chosen_mode]
            self.road_shape = challenge_spec.road_shape if challenge_spec is not None and challenge_spec.road_shape else route.shape
            seed = route.seed
        if chosen_mode in OVERTAKE_ROUTES:
            route = OVERTAKE_ROUTES[chosen_mode]
            self.road_shape, seed = route.shape, route.seed
        track = chosen_track.id.value
        self.phase = Phase.LOADING
        self.notice = ""
        traffic_count = 8 if chosen_mode == GameMode.FREE_DRIVE and track != "test" else 0
        density = TRAFFIC_DENSITIES[self.traffic_density]
        if chosen_mode in OVERTAKE_ROUTES:
            density = TRAFFIC_DENSITIES["normal"]
        if (track == "endless" and chosen_mode not in (GameMode.CAREER, *BRAKING_MODES, *SLALOM_MODES)
                and chosen_mode not in SPRINT_ROUTES):
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
                physics_workers=self.physics_worker_count(),
            )
            self.track = get_track(track)
        else:
            self.simulation.road_shape = self.road_shape
            self.simulation.traffic_count = traffic_count
            self.simulation.traffic_span = density.spawn_span
            self.simulation.reset(self.seed)
        if settle_initial:
            settled = self.simulation.settle_initial(loading_ticks=60 if countdown else None)
            self._settling_initial = settled is None
        else:
            self.simulation.prepare_physics(background=countdown)
            self._settling_initial = False
        self.mode = chosen_mode
        self.simulation.set_checkpoint_frames_enabled(self.mode == GameMode.TIME_TRIAL)
        self.race.start(
            self.mode, circuit=self.track.circuit,
            score_variant=self.score_variant(), record_scores=challenge_spec is None,
        )
        self.reference_ghost = None
        self.ghost_recording = None
        self.ghost_conditions = None
        self._coastal_source = None
        self._coastal_challenge_scores = None
        if self.mode == GameMode.TIME_TRIAL and not self.sector_chase:
            self.prepare_coastal_ghost()
        self.highway = HighwayRun(challenge=self.mode == GameMode.DISTANCE_CHALLENGE)
        if self.mode == GameMode.CAREER:
            self.highway.snapshot = replace(self.highway.snapshot, challenge=True,
                target=EVENT_BY_ID[self.career_event_id].distance,
                career=CareerResult(self.career_event_id, self.highway_progress()))
        self.keyboard.direction = 1
        self.keyboard.input_config = self.driving_mode.input_config
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
        data = json.dumps(asdict(self.vehicle_config), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return variant+":splits-v1:hardware-"+hashlib.sha256(data.encode()).hexdigest()

    def challenge_scores(self, source=None):
        group = self.driving_mode.score_variant(self.abs_enabled, self.tcs_enabled, self.esc_enabled)
        if self.mode == GameMode.DISTANCE_CHALLENGE:
            # 可选路况各自保存完赛和标定样本。
            sim = self.simulation
            group += f':road-{sim.road_shape}:traffic-{sim.traffic_count}-{sim.traffic_span:g}'
        if self.sector_chase:
            group += ':'+CHASE_VERSION
        source = ghost_context(self.seed) if source is None else source
        scores = ChallengeScores(self.race.scores.path.with_name('challenge-best.json'),
                                 self.challenge_spec, group, record_context(source, self.mode))
        if not any(pending.key == scores.key for pending in self._pending_score_stores):
            scores.recover_pending()
        return scores

    def prepare_coastal_ghost(self):
        reference = self.race.snapshot
        try:
            self._coastal_source = ghost_context(self.seed)
            if self.challenge_spec is None:
                self.ghost_conditions = record_context(self._coastal_source, self.mode)
                self.reference_ghost = load_ghost(self.race.scores, self.mode, self.race.score_id,
                    self.ghost_conditions, reference.reference_lap, reference.reference_splits)
                has_best = reference.reference_lap is not None
            else:
                scores = self._coastal_challenge_scores = self.challenge_scores(self._coastal_source)
                best = scores.completed.get('fastest')
                has_best = best is not None
                if has_best:
                    self.reference_ghost = load_ghost(scores, self.mode, best['run_id'], scores.context['physics'],
                        best['seconds'], tuple(row['seconds'] for row in best.get('splits', ())))
            if self.reference_ghost is None and has_best:
                self.race.snapshot = replace(reference, ghost_notice="最佳圈暂无幽灵；新最佳圈将自动记录。")
        except (OSError, ValueError, KeyError, TypeError) as error:
            logging.getLogger(__name__).warning("幽灵载入失败: %s", error)
            self.race.snapshot = replace(reference, ghost_notice="幽灵缺失、损坏或版本不兼容；成绩保留。")

    def set_controller(self, controller: Controller):
        self.stop_clock()
        self.keyboard.clear()
        self.last_control = Control()
        self.controller = controller
        if self.engineering is not None and controller is not self.keyboard:
            self.engineering.player_driven = False
            self.engineering.scores = None
            self.ghost_recording = None
            if self.engineering.trace is not None:
                self.engineering.trace.controller = type(controller).__module__+'.'+type(controller).__name__

    def highway_progress(self, state=None):
        if state is None:
            state = self.simulation.snapshot()
        distance, _ = self.simulation.road.locate(state.player)
        return distance if self.simulation.road.curve else distance + state.origin_y

    def begin_driving(self):
        if self.simulation.track == "endless":
            self.highway.start(
                self.highway_progress(), challenge=self.mode == GameMode.DISTANCE_CHALLENGE,
                braking_scores=(BrakingScores(self.race.scores.path.with_name(
                                    "short-braking-best.json" if self.mode == GameMode.SHORT_BRAKING else "braking-best.json"),
                                    ("short-braking-v1:" if self.mode == GameMode.SHORT_BRAKING else "braking-v1:")+self.score_variant(),
                                    maximum=42 if self.mode == GameMode.SHORT_BRAKING else 10)
                                if self.mode in BRAKING_MODES else None),
                slalom_scores=(SlalomScores(self.race.scores.path.with_name("slalom-best.json"),
                                             ("practice-slalom-v1:" if self.mode == GameMode.SLALOM_PRACTICE else
                                              "fast-slalom-v1:" if self.mode == GameMode.FAST_SLALOM else "slalom-v1:")+self.score_variant())
                                if self.mode in SLALOM_MODES else None),
                short_braking=self.mode == GameMode.SHORT_BRAKING,
                vehicle_config=self.vehicle_config, fast_slalom=self.mode == GameMode.FAST_SLALOM,
                practice_slalom=self.mode == GameMode.SLALOM_PRACTICE,
                sprint_mode=self.mode if self.mode in SPRINT_ROUTES else None,
                sprint_scores=BestTimes(self.race.scores.path.with_name("sprint-best.json")) if self.mode in SPRINT_ROUTES else None,
                sprint_rules_version='' if self.challenge_spec is None else self.challenge_spec.version,
                score_variant=self.score_variant(),
                overtake_initial=self.simulation.snapshot() if self.mode in OVERTAKE_ROUTES else None,
                overtake_scores=BestTimes(self.race.scores.path.with_name("overtake-best.json")) if self.mode in OVERTAKE_ROUTES else None,
                overtake_mode=self.mode, overtake_road=self.simulation.road,
                career_event_id=self.career_event_id,
                record_scores=self.challenge_spec is None,
            )
        else:
            state = self.simulation.snapshot()
            self.race.begin(start_time=state.time)
            if self.mode == GameMode.TIME_TRIAL and self.ghost_conditions is not None:
                self.ghost_recording = GhostRecorder(state, self.ghost_conditions)
        if self.challenge_spec is not None:
            initial = self.simulation.snapshot()
            train = initial.player.powertrain_state
            source = self._coastal_source if self._coastal_source is not None else ghost_context(self.seed)
            scores = None if self.practice_sector is not None else self._coastal_challenge_scores or self.challenge_scores(source)
            self.engineering = ChallengeRun(self.challenge_spec, self.challenge_build,
                None if train is None else train.fuel,
                gates=(self.highway.sprint.route.gates if self.highway.sprint is not None
                       else course_gates(course_key(self.mode, self.career_event_id))), scores=scores,
                chase=CHASE_COURSES[self.mode] if self.sector_chase else None, practice_sector=self.practice_sector)
            if self.practice_sector is not None and train is not None and train.fuel is not None:
                self.simulation.player.powertrain.fuel.samples = None
            if scores is not None and train is not None and train.fuel is not None:
                self.simulation.player.powertrain.fuel.samples = []
                self.engineering.trace = ChallengeTrace(self.race.scores.path.parent/'challenge-runs',
                    self.challenge_spec, self.challenge_build, initial,
                    source, 'keyboard', scores.context['input'],
                    circuit=self.mode == GameMode.TIME_TRIAL)
                if self._coastal_challenge_scores is not None and self.controller is self.keyboard:
                    self.ghost_recording = GhostRecorder(initial, scores.context['physics'])
            if self.controller is not self.keyboard:
                self.engineering.player_driven = False
                self.engineering.scores = None
                if self.engineering.trace is not None:
                    self.engineering.trace.controller = type(self.controller).__module__+'.'+type(self.controller).__name__
            self.highway.snapshot = replace(self.highway.snapshot, engineering=self.engineering.snapshot)

    def tick(self):
        if self.phase == Phase.COUNTDOWN:
            self.countdown_step(1)
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
            finish_context = None
            if self.simulation.track == "endless":
                # 弯道门和五公里车道边界都按权威道路的局部标架判定。
                road, player = self.simulation.road, self.current.player
                location = road.locate(player)
                progress = location[0] if road.curve else location[0]+self.current.origin_y
                car = (road.lane_frame(player, location) if self.mode in SPRINT_ROUTES
                       or self.mode in (GameMode.CAREER, GameMode.DISTANCE_CHALLENGE) else player)
                self.highway.update(
                    progress, self.current.collisions, FIXED_DT,
                    reset="player_reset" in self.current.events,
                    forward_speed=car.velocity[1],
                    speed=math.hypot(*self.current.player.velocity[:2]),
                    lateral=car.position[0],
                    heading=car.heading,
                    brake_request=self.last_control.brake,
                    traffic_state=self.current if self.mode in OVERTAKE_ROUTES else None,
                )
            if self.engineering is not None:
                road = self.highway.snapshot
                crossing_times = None
                if self.mode == GameMode.TIME_TRIAL:
                    lap = self.race.snapshot
                    progress = self.race.distance
                    seconds = self.current.time-lap.start_time
                    finished, succeeded = lap.finished, lap.finished and not lap.invalidated
                    reason = lap.invalid_reason if lap.invalidated else '完成滨海环路'
                    if self.sector_chase and (lap.invalidated or self.current.collisions):
                        finished, succeeded = True, False
                        reason = lap.invalid_reason or '发生碰撞'
                    crossing_times = lap.splits if succeeded or not lap.finished else lap.splits[:lap.checkpoints]
                    passed = len(crossing_times)
                else:
                    progress, seconds = road.distance, road.elapsed
                    finished, succeeded, reason = road.finished, road.succeeded, road.reason
                    passed = (road.sprint.gates if road.sprint is not None else
                              sum(distance <= progress for distance in self.engineering.gates))
                    passed = max(len(self.engineering.splits), passed)
                if 'player_reset' in self.current.events:
                    self.engineering.stop('车辆复位')
                else:
                    if self.engineering.trace is not None and not self.engineering.trace.closed:
                        meter = self.simulation.player.powertrain.fuel
                        self.engineering.trace.append(self.current, self.last_control, progress, meter.samples)
                        meter.samples.clear()
                    train = self.current.player.powertrain_state
                    metric = None
                    if self.challenge_spec.assessment != 'road':
                        if road.career is not None:
                            metric = (road.career.parking_error if self.challenge_spec.assessment == 'lower'
                                      else sum(road.career.passed))
                        elif road.braking is not None:
                            metric = (road.braking.stopping_m if self.mode == GameMode.SHORT_BRAKING
                                      else abs(road.braking.error_m) if road.braking.error_m is not None else None)
                        elif road.slalom is not None:
                            metric = road.slalom.run_seconds
                    self.engineering.sample(None if train is None else train.fuel, progress, seconds,
                        passed=passed, finished=finished, succeeded=succeeded, reason=reason,
                        metric_value=metric, crossing_times=crossing_times)
                if (self.practice_sector is not None and self.engineering.result is None
                        and len(self.engineering.splits) > self.practice_sector):
                    self.engineering.stop('本段练习完成', succeeded=True,
                                          seconds=self.engineering.splits[self.practice_sector].seconds)
                if self.engineering.result is not None:
                    finish_context = ghost_context(self.seed)
                    self.engineering.save_trace(finish_context)
                    if self.sector_chase:
                        result = self.engineering.result
                        road = replace(road, finished=True, running=False, succeeded=result.valid, reason=result.notice)
                self.highway.snapshot = replace(road, engineering=self.engineering.snapshot)
            self.record_ghost_step(finish_context)
            if self.race.snapshot.finished or self.highway.snapshot.finished:
                self.phase = Phase.RESULTS
                self.keyboard.clear()
                self.previous = self.current
            elif (
                self.simulation.track == "highway"
                and self.current.player.position[1] >= HIGHWAY_LENGTH
            ):
                self.finish()

    def record_ghost_step(self, finish_context=None):
        recorder = self.ghost_recording
        if recorder is None:
            return
        race = self.race.snapshot
        if race.invalidated:
            self.ghost_recording = None
            return
        recorder.append(self.current)
        if recorder.notice:
            self.race.snapshot = replace(race, ghost_notice=recorder.notice)
            self.ghost_recording = None
            return
        if not race.finished:
            return
        if self.engineering is not None and self.engineering.score_pending and finish_context == self._coastal_source:
            return
        self.ghost_recording = None
        self._save_finished_ghost(recorder, finish_context)

    def _save_finished_ghost(self, recorder, finish_context=None):
        race = self.race.snapshot
        engineering = self.engineering
        if engineering is None and race.save_error:
            self.race.snapshot = replace(race, ghost_notice="成绩未保存，本次幽灵未关联。")
            return
        if engineering is None and not race.new_best:
            return
        if engineering is not None and ('完赛', 'fastest') not in engineering.record_updates:
            return
        try:
            if (finish_context if finish_context is not None else ghost_context(self.seed)) != self._coastal_source:
                raise ValueError("试跑期间版本改变，成绩保留但未保存幽灵；请重开程序。")
            if engineering is None:
                lap = recorder.finish(self.race.score_id, race)
                save_ghost(lap, self.race.scores, self.mode)
                self.race.snapshot = replace(race, ghost_notice="最佳圈幽灵已保存，下次挑战可对照。")
            else:
                scores = engineering.scores
                best = scores.completed['fastest']
                lap = recorder.finish_lap(best['run_id'], engineering.result.seconds,
                                          tuple(row.seconds for row in engineering.splits))
                save_ghost(lap, scores, self.mode)
                self.race.snapshot = replace(race, ghost_notice='')
        except (OSError, ValueError, KeyError, TypeError) as error:
            logging.getLogger(__name__).warning("幽灵保存失败: %s", error)
            self.race.snapshot = replace(race, ghost_notice="幽灵未保存，成绩保留；请检查存储目录或版本。")

    def retry_challenge_score(self):
        engineering = self.engineering
        if self.phase != Phase.RESULTS or engineering is None or not engineering.score_pending:
            return
        engineering.retry_score()
        if not engineering.score_pending and self.ghost_recording is not None:
            recorder, self.ghost_recording = self.ghost_recording, None
            self._save_finished_ghost(recorder)
        self.highway.snapshot = replace(self.highway.snapshot, engineering=engineering.snapshot)

    def countdown_step(self, ticks):
        """未开放驾驶时只结算起步节拍，不施力、不记圈速。"""
        ready = self.simulation.physics_ready()
        self.countdown_ticks = max(0,self.countdown_ticks-ticks)
        if ready and self._settling_initial:
            for _ in range(min(ticks,8)):
                self.previous = self.current
                self._settling_initial = not self.simulation.settle_initial_step()
                self.current = self.simulation.snapshot()
                if not self._settling_initial:
                    break
        if self.countdown_ticks == 0 and ready and not self._settling_initial:
            self.phase = Phase.DRIVING
            self.keyboard.clear()
            self.begin_driving()

    def advance_countdown(self, elapsed):
        """倒计时按真实经过时间显示；物理追帧上限不应把三秒拖成四秒。"""
        if not math.isfinite(elapsed) or elapsed<0:
            raise ValueError("Frame time must be finite and nonnegative")
        self.stepper.remainder += elapsed
        ticks = int((self.stepper.remainder+1e-12)/FIXED_DT)
        self.stepper.remainder = max(0.,self.stepper.remainder-ticks*FIXED_DT)
        self.countdown_step(ticks)

    def frame(self, elapsed, *, sampled_at=None):
        if self.independent_clock:
            self._skip_frame = False
            if self._clock is None and self.phase in (Phase.DRIVING,Phase.COUNTDOWN):
                self._clock = SessionClock(self)
                self._clock.start()
            return self._clock.frame(sampled_at) if self._clock is not None else self.current
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

        if self.phase == Phase.COUNTDOWN:
            self.advance_countdown(elapsed)
        elif self.phase == Phase.DRIVING:
            self.stepper.advance(elapsed, tick_and_collect)
        # 保留导致驾驶结束的最后一批事件；结果页后续帧自然没有新 tick。
        if (self.phase not in (Phase.DRIVING, Phase.RESULTS)
                or frame_phase in (Phase.PAUSED, Phase.MENU, Phase.RESULTS)):
            collected = []
        current = interpolate(self.previous, self.current, min(1., self.stepper.remainder / FIXED_DT))
        return replace(current, impacts=tuple(collected), contacts=self.current.contacts)

    def pause(self):
        self.stop_clock()
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
        self.stop_clock()
        if not self.simulation.recover_player():
            self.notice = "附近暂时没有安全空位，请稍后再试"
            return
        self.notice = ""
        self.race.reset_player(self.simulation.snapshot())
        if self.simulation.track == "endless":
            self.highway.update(
                self.highway_progress(), self.simulation.player_collisions, 0, reset=True,
                traffic_state=self.simulation.snapshot() if self.mode in OVERTAKE_ROUTES else None,
            )
            if self.highway.snapshot.finished:
                self.phase = Phase.RESULTS
        if self.engineering is not None:
            self.engineering.stop('车辆复位')
            self.engineering.save_trace(ghost_context(self.seed))
            self.highway.snapshot = replace(self.highway.snapshot, engineering=self.engineering.snapshot)
        self.keyboard.clear()
        self.stepper.remainder = 0.0
        self.sync_snapshots()

    def menu(self):
        self.stop_clock()
        self.leave_challenge()
        self.phase = Phase.MENU
        self.mode = GameMode.FREE_DRIVE
        self.simulation.set_checkpoint_frames_enabled(False)
        self.race.start(self.mode)
        self.reference_ghost = self.ghost_recording = None
        self.highway = HighwayRun()
        self.keyboard.clear()
        self.stepper.remainder = 0.0
        self.sync_snapshots()

    def finish(self):
        self.stop_clock()
        if self.engineering is not None:
            self.engineering.stop('挑战提前结束')
            self.engineering.save_trace(ghost_context(self.seed))
            self.highway.snapshot = replace(self.highway.snapshot, engineering=self.engineering.snapshot)
        self.race.stop()
        self.ghost_recording = None
        self.highway.stop("挑战提前结束" if (self.mode in (GameMode.CAREER, GameMode.DISTANCE_CHALLENGE, *BRAKING_MODES, *SLALOM_MODES, *OVERTAKE_ROUTES)
                                           or self.mode in SPRINT_ROUTES) else "自由驾驶结束")
        self.phase = Phase.RESULTS
        self.keyboard.clear()
        self.stepper.remainder = 0.0
        self.sync_snapshots()

    def _end_challenge_run(self, reason):
        pending, self._pending_score_stores = self._pending_score_stores, []
        for scores in pending:
            scores.retry_pending()
            if scores.pending_score is not None:
                self._pending_score_stores.append(scores)
        if self.engineering is not None:
            self.engineering.stop(reason)
            if self.engineering.score_pending:
                self.retry_challenge_score()
                if self.engineering.score_pending:
                    self._pending_score_stores.append(self.engineering.scores)
            self.engineering.save_trace(ghost_context(self.seed))

    def leave_challenge(self):
        """本关候选只在驾驶会话生效；不覆写玩家工程车或原电子设置。"""
        self._end_challenge_run('已退出本次挑战')
        if self.engineering is not None:
            self.simulation.player.powertrain.fuel.samples = None
        if self._challenge_original is not None:
            self.base_vehicle_config, self.vehicle_config = self._challenge_original
        self._challenge_original = None
        self._coastal_challenge_scores = None
        self.challenge_spec = self.challenge_build = self.engineering = None
        self.sector_chase, self.practice_sector = False, None

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
        self.stop_clock()
        self.leave_challenge()
        self.keyboard.clear()
        self.simulation.close()

    def stop_clock(self):
        if self._clock is not None and self._clock.stop():
            self._clock = None

    def render_segments(self):
        if self._clock is not None:
            return self._clock.visible_segments
        stream = self.simulation.stream
        return tuple(stream.segments) if stream is not None else ()

    def render_origin(self):
        return self._clock.visible_origin if self._clock is not None else self.current.origin_y

    def camera_position(self, start, end, origin_y):
        """世界查询与推进互斥；重定位期间将当帧相机转换到当前世界再转回。"""
        clock = self._clock
        with clock.world_lock if clock is not None else nullcontext():
            offset = origin_y-self.simulation.origin_y
            start,end = type(start)(start),type(end)(end)
            start.y += offset
            end.y += offset
            result = self.simulation.camera_position(start,end)
            result.y -= offset
            return result
