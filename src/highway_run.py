"""Highway trip statistics and the five-kilometre clean driving challenge."""

import math
from dataclasses import dataclass, replace

from braking_lesson import TARGET_DISTANCE, BrakingLesson, BrakingResult
from career import EVENT_BY_ID
from career_run import CareerResult, CareerRun
from challenge_run import ChallengeStatus
from highway_map import ROAD_WIDTH
from overtake_run import OvertakeResult, OvertakeRun
from race import GameMode
from short_braking import MAX_DISTANCE, ShortBraking
from slalom_lesson import GATES, SlalomLesson, SlalomResult
from sprint_run import SprintResult, SprintRun
from vehicle_config import body_center


@dataclass(frozen=True)
class TrafficDensity:
    label: str
    cars: int
    spawn_span: float


TRAFFIC_DENSITIES = {
    "light": TrafficDensity("稀疏", 6, 720),
    "normal": TrafficDensity("普通", 12, 540),
    "busy": TrafficDensity("繁忙", 18, 480),
}


@dataclass(frozen=True)
class HighwayResult:
    challenge: bool = False
    running: bool = False
    finished: bool = False
    succeeded: bool = False
    reason: str = ""
    elapsed: float = 0.0
    distance: float = 0.0
    target: float = 5000.0
    collisions: int = 0
    braking: BrakingResult | None = None
    slalom: SlalomResult | None = None
    sprint: SprintResult | None = None
    overtake: OvertakeResult | None = None
    career: CareerResult | None = None
    engineering: ChallengeStatus | None = None


class HighwayRun:
    def __init__(self, *, challenge=False):
        self.snapshot = HighwayResult(challenge=challenge)
        self._start = 0.0
        self.distance_vehicle = None
        self.braking = None
        self.slalom = None
        self.sprint = None
        self.overtake = None
        self.career = None

    def start(self, progress, *, challenge=False, braking_scores=None, slalom_scores=None, vehicle_config=None,
              sprint_mode=None, sprint_scores=None, sprint_rules_version='', score_variant="",
              overtake_initial=None, overtake_scores=None,
              overtake_mode=GameMode.SAFE_OVERTAKE, overtake_road=None, fast_slalom=False, short_braking=False,
              practice_slalom=False, career_event_id=None, record_scores=True):
        self._start = progress
        self.distance_vehicle = vehicle_config if challenge and not record_scores else None
        self.snapshot = HighwayResult(challenge=challenge, running=True)
        self.career = None if career_event_id is None else CareerRun(career_event_id, progress, vehicle_config)
        if self.career is not None:
            self.snapshot = replace(self.snapshot, challenge=True, target=EVENT_BY_ID[career_event_id].distance,
                                    career=self.career.snapshot)
        self.braking = None if braking_scores is None else BrakingLesson(progress, braking_scores, record_scores=record_scores)
        if braking_scores is not None and short_braking:
            self.braking = ShortBraking(progress, braking_scores, record_scores=record_scores)
        self.slalom = None if slalom_scores is None else SlalomLesson(progress, slalom_scores, vehicle_config,
                                                                   fast=fast_slalom, practice=practice_slalom, record_scores=record_scores)
        self.sprint = (None if sprint_mode is None else
                       SprintRun(progress, sprint_mode, sprint_scores, score_variant, vehicle_config,
                                 record_scores=record_scores, rules_version=sprint_rules_version))
        self.overtake = (None if overtake_initial is None else
                         OvertakeRun(overtake_initial, vehicle_config, overtake_scores, score_variant,
                                     mode=overtake_mode, road=overtake_road, record_scores=record_scores))
        if self.overtake is not None:
            self.snapshot = replace(self.snapshot, challenge=True, target=self.overtake.route.distance, overtake=self.overtake.snapshot)
        if self.sprint is not None:
            self.snapshot = replace(self.snapshot, challenge=True, target=self.sprint.route.gates[-1], sprint=self.sprint.snapshot)
        if self.braking is not None:
            self.snapshot = replace(self.snapshot, challenge=True, target=100.+MAX_DISTANCE if short_braking else TARGET_DISTANCE,
                                    braking=self.braking.snapshot)
        if self.slalom is not None:
            self.snapshot = replace(self.snapshot, challenge=True, target=GATES[-1][0], slalom=self.slalom.snapshot)

    def update(self, progress, collisions, dt, *, reset=False, forward_speed=0., speed=0., lateral=0., heading=0.,
               traffic_state=None, brake_request=None):
        state = self.snapshot
        if not state.running:
            return
        if self.career is not None:
            result = self.career.update(progress, state.elapsed+dt, lateral=lateral, heading=heading,
                                        speed=speed, collisions=collisions, reset=reset)
            self.snapshot = replace(state, elapsed=result.elapsed, distance=result.position, collisions=collisions,
                career=result, finished=result.finished, running=not result.finished,
                succeeded=result.succeeded, reason=result.reason)
            return
        if self.overtake is not None:
            result = self.overtake.update(traffic_state, state.elapsed+dt, reset=reset)
            self.snapshot = replace(state, elapsed=result.seconds, distance=result.distance, collisions=collisions,
                overtake=result, finished=result.finished, running=not result.finished,
                succeeded=result.succeeded, reason=result.reason)
            return
        if self.sprint is not None:
            result = self.sprint.update(progress, state.elapsed+dt, lateral=lateral, heading=heading,
                                        forward_speed=forward_speed, collisions=collisions, reset=reset,
                                        brake_request=brake_request)
            self.snapshot = replace(state, elapsed=state.elapsed+dt, distance=result.position, collisions=collisions,
                sprint=result, finished=result.finished, running=not result.finished,
                succeeded=result.succeeded, reason=result.reason)
            return
        if self.slalom is not None:
            elapsed = state.elapsed+dt
            result = self.slalom.update(progress, forward_speed, elapsed, lateral=lateral, heading=heading,
                                        collisions=collisions, reset=reset)
            self.snapshot = replace(state, elapsed=elapsed, distance=result.position, collisions=collisions,
                slalom=result, finished=result.finished, running=not result.finished,
                succeeded=result.succeeded, reason=result.reason)
            return
        if self.braking is not None:
            elapsed = state.elapsed + dt
            result = self.braking.update(progress, forward_speed, speed, elapsed, dt,
                                          collisions=collisions, reset=reset, lateral=lateral, heading=heading)
            self.snapshot = replace(state, elapsed=elapsed, distance=result.position,
                collisions=collisions, braking=result, finished=result.finished,
                running=not result.finished, succeeded=result.succeeded, reason=result.reason)
            return
        if reset:
            # Recovery moves the car to a safe spot; it never earns distance.
            self._start = progress - state.distance
        distance = max(state.distance, progress - self._start)
        self.snapshot = replace(
            state, elapsed=state.elapsed + dt, distance=distance, collisions=collisions
        )
        if state.challenge:
            if collisions:
                self.stop("发生碰撞")
            elif reset:
                self.stop("车辆复位")
            elif self.distance_vehicle is not None and self._outside_distance_road(lateral, heading):
                self.stop("车身越出行车道；请在车道内超车。")
            elif distance >= state.target:
                self.stop("完成 5 公里无碰撞挑战", succeeded=True)

    def _outside_distance_road(self, lateral, heading):
        config = self.distance_vehicle
        angle = math.radians(heading)
        sine, cosine = math.sin(angle), math.cos(angle)
        center = lateral-body_center(config)[1]*sine
        half_width = config.collision_half_width*abs(cosine)+config.collision_half_length*abs(sine)
        return abs(center)+half_width > ROAD_WIDTH/2

    def stop(self, reason="驾驶已结束", *, succeeded=False):
        if not self.snapshot.finished:
            if self.career is not None:
                self.career.stop(reason)
                self.snapshot = replace(self.snapshot, career=self.career.snapshot)
            if self.overtake is not None:
                self.overtake.stop(reason, succeeded=succeeded)
                self.snapshot = replace(self.snapshot, overtake=self.overtake.snapshot)
            if self.sprint is not None:
                self.sprint.stop(reason, succeeded=succeeded)
                self.snapshot = replace(self.snapshot, sprint=self.sprint.snapshot)
            if self.slalom is not None:
                self.slalom.stop(reason, succeeded=succeeded)
                self.snapshot = replace(self.snapshot, slalom=self.slalom.snapshot)
            if self.braking is not None:
                self.braking.stop(reason, succeeded=succeeded)
                self.snapshot = replace(self.snapshot, braking=self.braking.snapshot)
            self.snapshot = replace(
                self.snapshot, running=False, finished=True, succeeded=succeeded, reason=reason
            )
