"""固定步计时与门线分段；只有完整有效圈可以更新个人最佳。"""

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
    BRAKING_LESSON = "braking_lesson"
    SLALOM_LESSON = "slalom_lesson"


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
    splits: tuple[float, ...] = ()
    reference_splits: tuple[float, ...] = ()
    reference_lap: float | None = None
    new_best: bool = False
    score_notice: str = ""
    start_time: float | None = None
    ghost_notice: str = ""


def valid_time(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def valid_splits(values, seconds):
    return (isinstance(values, (list, tuple)) and bool(values)
            and all(valid_time(value) for value in values)
            and all(a < b for a, b in zip((0., *values), values))
            and valid_time(seconds) and math.isclose(values[-1], seconds, rel_tol=0., abs_tol=1e-9))


def valid_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


class BestTimes:
    def __init__(self, path: Path | None = None):
        self.path = path or user_data() / "best-times.json"
        self.error = ""
        self.notice = ""
        self.times = self._load()

    def _load(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            self.notice = "成绩文件未能读取，本次暂无可用参考；请检查存储目录。"
            return {}
        if not isinstance(value, dict):
            self.notice = "成绩文件格式无效，本次暂无可用参考。"
            return {}
        times = {}
        for key, seconds in value.items():
            if key in ("_splits_v1", "_ghosts_v1"):
                continue
            if valid_time(seconds):
                times[key] = seconds
            else:
                self.notice = "成绩文件含无效记录，已跳过；其余成绩保留。"
        splits = value.get("_splits_v1", {})
        if isinstance(splits, dict):
            times["_splits_v1"] = {}
            for key, row in splits.items():
                if valid_splits(row, times.get(key)):
                    times["_splits_v1"][key] = row
                else:
                    self.notice = "部分分段记录损坏，保留可用总成绩；请完成新最佳圈。"
        else:
            self.notice = "分段记录格式无效，保留可用总成绩；请完成新最佳圈。"
        ghosts = value.get("_ghosts_v1", {})
        times["_ghosts_v1"] = {}
        if isinstance(ghosts, dict):
            for key, digest in ghosts.items():
                if key in times and valid_digest(digest):
                    times["_ghosts_v1"][key] = digest
                else:
                    self.notice = "部分幽灵链接损坏，成绩保留；请完成新最佳圈。"
        else:
            self.notice = "幽灵链接格式无效，成绩保留；请完成新最佳圈。"
        return times

    def get(self, mode, course_id="coastal-v2"):
        value = self.times.get(f"{course_id}:{mode.value}")
        return float(value) if valid_time(value) else None

    def get_splits(self, mode, course_id, count):
        key = f"{course_id}:{mode.value}"
        values = self.times.get("_splits_v1", {}).get(key, ())
        if len(values) == count:
            return tuple(values)
        if values:
            self.notice = "历史分段数量与当前赛道不同；仅显示总成绩。"
        return ()

    def record(self, mode, seconds, course_id="coastal-v2", *, splits=None):
        if not valid_time(seconds):
            raise ValueError("圈速须为有限正数")
        if splits is not None and not valid_splits(splits, seconds):
            raise ValueError("分段须为递增门线时刻，并与整圈时间一致")
        self.error = ""
        self.times.update(self._load())
        old = self.get(mode, course_id)
        if old is not None and old <= seconds:
            return old, False
        previous = self.times
        self.times = {**previous, "_splits_v1": dict(previous.get("_splits_v1", {})),
                      "_ghosts_v1": dict(previous.get("_ghosts_v1", {}))}
        key = f"{course_id}:{mode.value}"
        self.times[key] = seconds
        self.times.setdefault("_ghosts_v1", {}).pop(key, None)
        recorded = self.times.setdefault("_splits_v1", {})
        if splits is None:
            recorded.pop(key, None)
        else:
            recorded[key] = tuple(splits)
        saved = self._save()
        if not saved:
            self.times = previous
        return self.get(mode, course_id), saved

    def _save(self):
        self.error = ""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.times, indent=2, allow_nan=False), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            self.error = "成绩暂未保存，请检查存储空间或目录权限"
        return not self.error

    def ghost_digest(self, mode, course_id):
        return self.times.get("_ghosts_v1", {}).get(f"{course_id}:{mode.value}")

    def attach_ghost(self, mode, course_id, seconds, splits, digest):
        """只给当前磁盘最佳整圈添加链接；旧总时长或分段不匹配则拒绝。"""
        if not valid_digest(digest):
            raise ValueError("幽灵内容摘要无效")
        current = self._load()
        key = f"{course_id}:{mode.value}"
        if current.get(key) != seconds or tuple(current.get("_splits_v1", {}).get(key, ())) != tuple(splits):
            raise ValueError("最佳成绩已改变，幽灵未关联")
        self.times = current
        self.times.setdefault("_ghosts_v1", {})[key] = digest
        if not self._save():
            self.times["_ghosts_v1"].pop(key, None)
            raise OSError("幽灵链接未保存")


class RaceTracker:
    def __init__(self, mode=GameMode.FREE_DRIVE, scores=None, circuit=COASTAL_CIRCUIT):
        self.scores = scores if scores is not None else BestTimes()
        self.circuit = circuit
        self.snapshot = RaceSnapshot(mode=mode)
        self.start(mode)

    def start(self, mode=None, circuit=None, *, score_variant=""):
        if circuit is not None:
            self.circuit = circuit
        mode = self.snapshot.mode if mode is None else mode
        self.score_id = self.circuit.score_id + (":" + score_variant if score_variant else "")
        self.snapshot = RaceSnapshot(
            mode=mode, best_lap=self.scores.get(mode, self.score_id),
            reference_lap=self.scores.get(mode, self.score_id),
            reference_splits=self.scores.get_splits(mode, self.score_id, len(self.circuit.checkpoints)+1),
            score_notice=self.scores.notice,
        )
        self._distance = self._furthest = 0.0
        self._previous_progress = 0.0
        self._previous_position = None

    def begin(self, progress=0.0, *, start_time=None):
        point = self.circuit.point_at(progress)
        self._previous_position = (point.x, point.y, point.z + 0.42)
        self._previous_progress = progress
        self._distance = self._furthest = 0.0
        self.snapshot = replace(self.snapshot, running=True, progress=progress, start_time=start_time)

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
        splits = self.snapshot.splits
        for index, distance in enumerate(self.circuit.checkpoints):
            crossing = self._crossing(distance, position)
            if crossing is not None:
                if index == passed:
                    passed += 1
                    splits += (self.snapshot.elapsed+dt*crossing,)
                elif index > passed:
                    self._invalidate("检查点不完整")
        self.snapshot = replace(
            self.snapshot, checkpoints=passed, next_checkpoint=passed + 1, progress=progress,
            splits=splits,
        )
        finish = self._crossing(0, position)
        # Ignore the initial departure across the start line.
        if finish is not None and self._furthest > length / 2:
            if passed != len(self.circuit.checkpoints) or self._distance < length - 2:
                self._invalidate("检查点不完整")
            lap_time = self.snapshot.elapsed + dt * finish
            splits += (lap_time,)
            best = self.snapshot.best_lap
            new_best = False
            if not self.snapshot.invalidated:
                best, saved = self.scores.record(self.snapshot.mode, lap_time, self.score_id, splits=splits)
                new_best = saved and best == lap_time and (self.snapshot.reference_lap is None
                                                or lap_time < self.snapshot.reference_lap)
            self.snapshot = replace(
                self.snapshot,
                running=False,
                finished=True,
                elapsed=lap_time,
                last_lap=lap_time,
                best_lap=best,
                save_error=self.scores.error,
                splits=splits,
                new_best=new_best,
            )
        else:
            self.snapshot = replace(self.snapshot, elapsed=self.snapshot.elapsed + dt)
        self._previous_position = position
        self._previous_progress = progress

    def stop(self):
        if self.snapshot.running and self.snapshot.mode == GameMode.TIME_TRIAL:
            self._invalidate("提前结束")
        self.snapshot = replace(self.snapshot, running=False)
