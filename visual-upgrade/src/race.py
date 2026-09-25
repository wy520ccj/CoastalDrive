"""Fixed-step time trial rules. A lap requires crossing each gate on the road."""

import json
import math
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from paths import user_data
from tracks import COASTAL_CIRCUIT


class GameMode(Enum):
    FREE_DRIVE = "free_drive"
    TIME_TRIAL = "time_trial"
    DISTANCE_CHALLENGE = "distance_challenge"


@dataclass(frozen=True)
class RaceSnapshot:
    mode: GameMode = GameMode.FREE_DRIVE
    running: bool = False
    finished: bool = False
    invalidated: bool = False
    invalid_reason: str = ""
    elapsed: float = 0.0
    lap: int = 1
    checkpoints: int = 0
    next_checkpoint: int = 1
    progress: float = 0.0
    last_lap: float | None = None
    best_lap: float | None = None
    save_error: str = ""


def valid_time(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


class BestTimes:
    def __init__(self, path: Path | None = None):
        self.path = path or user_data() / "best-times.json"
        self.times = self._load()
        self.error = ""

    def _load(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    def get(self, mode, course_id="coastal-v2"):
        value = self.times.get(f"{course_id}:{mode.value}")
        return float(value) if valid_time(value) else None

    def record(self, mode, seconds, course_id="coastal-v2"):
        if not valid_time(seconds):
            raise ValueError("A lap time must be finite and positive")
        self.times.update(self._load())
        old = self.get(mode, course_id)
        if old is not None and old <= seconds:
            return old, False
        self.times[f"{course_id}:{mode.value}"] = seconds
        self.error = ""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.times, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            self.error = "成绩暂未保存，请检查存储空间或目录权限"
        return seconds, not self.error


class RaceTracker:
    def __init__(self, mode=GameMode.FREE_DRIVE, scores=None, circuit=COASTAL_CIRCUIT):
        self.scores = scores if scores is not None else BestTimes()
        self.circuit = circuit
        self.snapshot = RaceSnapshot(mode=mode)
        self.start(mode)

    def start(self, mode=None, circuit=None):
        if circuit is not None:
            self.circuit = circuit
        mode = self.snapshot.mode if mode is None else mode
        self.snapshot = RaceSnapshot(
            mode=mode, best_lap=self.scores.get(mode, self.circuit.score_id)
        )
        self._distance = self._furthest = 0.0
        self._previous_progress = 0.0
        self._previous_position = None

    def begin(self, progress=0.0):
        point = self.circuit.point_at(progress)
        self._previous_position = (point.x, point.y, point.z + 0.42)
        self._previous_progress = progress
        self._distance = self._furthest = 0.0
        self.snapshot = replace(self.snapshot, running=True, progress=progress)

    def _invalidate(self, reason):
        if not self.snapshot.invalidated:
            self.snapshot = replace(self.snapshot, invalidated=True, invalid_reason=reason)

    def reset_player(self, state=None):
        if self.snapshot.mode == GameMode.TIME_TRIAL and self.snapshot.running:
            self._invalidate("车辆复位")
        if state is not None and self.circuit is not None:
            self._previous_position = state.player.position
            self._previous_progress = self.circuit.project(*state.player.position[:2])[2]

    def _crossing(self, distance, position):
        gate = self.circuit.point_at(distance)
        angle = math.radians(gate.heading)
        forward = (-math.sin(angle), math.cos(angle))
        before = sum(
            (a - b) * d for a, b, d in zip(self._previous_position, (gate.x, gate.y), forward)
        )
        after = sum((a - b) * d for a, b, d in zip(position, (gate.x, gate.y), forward))
        if before >= 0 or after < 0:
            return None
        fraction = -before / (after - before)
        x, y, z = (a + (b - a) * fraction for a, b in zip(self._previous_position, position))
        lateral = (x - gate.x) * math.cos(angle) + (y - gate.y) * math.sin(angle)
        if abs(lateral) > self.circuit.half_width or not -0.2 <= z - gate.z <= 1.5:
            return None
        return fraction

    def update(self, state, dt, *, reset=False):
        if self.snapshot.mode != GameMode.TIME_TRIAL or not self.snapshot.running:
            return
        position = state.player.position
        point, lateral, progress = self.circuit.project(*position[:2])
        if reset:
            self.reset_player(state)
            self.snapshot = replace(
                self.snapshot, elapsed=self.snapshot.elapsed + dt, progress=progress
            )
            return
        length = self.circuit.length
        delta = (progress - self._previous_progress + length / 2) % length - length / 2
        moved = math.dist(position, self._previous_position)
        if max(abs(delta), moved) > max(1.2, abs(state.player.speed) * dt * 3 + 0.8):
            self._invalidate("路线进度异常")
        if lateral > self.circuit.road_limit + 0.2 or not -0.3 <= position[2] - point.z <= 2:
            self._invalidate("驶离赛道")
        self._distance += delta
        self._furthest = max(self._furthest, self._distance)
        passed = self.snapshot.checkpoints
        for index, distance in enumerate(self.circuit.checkpoints):
            if self._crossing(distance, position) is not None:
                if index == passed:
                    passed += 1
                elif index > passed:
                    self._invalidate("检查点不完整")
        self.snapshot = replace(
            self.snapshot, checkpoints=passed, next_checkpoint=passed + 1, progress=progress
        )
        finish = self._crossing(0, position)
        # Ignore the initial departure across the start line.
        if finish is not None and self._furthest > length / 2:
            if passed != len(self.circuit.checkpoints) or self._distance < length - 2:
                self._invalidate("检查点不完整")
            lap_time = self.snapshot.elapsed + dt * finish
            best = self.snapshot.best_lap
            if not self.snapshot.invalidated:
                best, _ = self.scores.record(self.snapshot.mode, lap_time, self.circuit.score_id)
            self.snapshot = replace(
                self.snapshot,
                running=False,
                finished=True,
                elapsed=lap_time,
                last_lap=lap_time,
                best_lap=best,
                save_error=self.scores.error,
            )
        else:
            self.snapshot = replace(self.snapshot, elapsed=self.snapshot.elapsed + dt)
        self._previous_position = position
        self._previous_progress = progress

    def stop(self):
        if self.snapshot.running and self.snapshot.mode == GameMode.TIME_TRIAL:
            self._invalidate("提前结束")
        self.snapshot = replace(self.snapshot, running=False)
