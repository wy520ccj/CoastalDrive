"""定点刹停的完成步规则与成绩；不施力、不维护车辆状态。"""

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

from race import GameMode

ENTRY_DISTANCE = 100.
TARGET_DISTANCE = 170.
ENTRY_KPH = 80.
TIME_LIMIT = 30.
STOP_SPEED = .15
HOLD_SECONDS = 1.
COURSE_HALF_WIDTH = 6.5
BRAKING_MODES = (GameMode.BRAKING_LESSON, GameMode.SHORT_BRAKING)


def medal_for(error):
    """以车身中心的停车绝对误差评奖。"""
    return "金" if error <= 2 else "银" if error <= 5 else "铜" if error <= 10 else ""


def valid_error(value, maximum=10):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


class BrakingScores:
    def __init__(self, path: Path, key: str, *, maximum=10):
        self.path, self.key = path, key
        self.maximum = maximum
        self.notice = ""
        self.values = self.load()
        self.best = self.values.get(key)

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1
                    or not isinstance(data.get("scores"), dict)
                    or any(not isinstance(key, str) or not valid_error(value, self.maximum)
                           for key, value in data["scores"].items())):
                raise ValueError("刹停成绩格式错误")
            return data["scores"]
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            self.notice = "历史刹停成绩未能读取；可继续练习。"
            return {}

    def record(self, error):
        """只保存成功且更准的停车误差；写入失败保留已显示的驾驶结果。"""
        if not valid_error(error, self.maximum):
            raise ValueError("只能保存成功的有限停车误差")
        values = self.load()
        best = values.get(self.key)
        if best is not None and best <= error:
            self.best = best
            return
        values[self.key] = error
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"version": 1, "scores": values}, ensure_ascii=False,
                                            sort_keys=True, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            self.notice = "本次成绩未保存；请检查存储目录，可继续练习。"
            return
        self.values, self.best = values, error
        self.notice = ""


@dataclass(frozen=True)
class BrakingResult:
    start_progress: float = 0.
    position: float = 0.
    entry_kph: float | None = None
    error_m: float | None = None
    hold_seconds: float = 0.
    medal: str = ""
    finished: bool = False
    succeeded: bool = False
    reason: str = ""
    best_error: float | None = None
    save_notice: str = ""
    short: bool = False
    stopping_m: float | None = None
    best_distance: float | None = None


class BrakingLesson:
    def __init__(self, start_progress, scores, *, record_scores=True):
        self.scores = scores
        self.record_scores = record_scores
        self.snapshot = BrakingResult(start_progress=start_progress, best_error=scores.best if record_scores else None,
                                      save_notice=scores.notice)
        self._previous_distance = 0.
        self._previous_forward_speed = 0.

    def update(self, progress, forward_speed, speed, elapsed, dt, *, collisions=0, reset=False, lateral=0., heading=0.):
        state = self.snapshot
        if state.finished:
            return state
        distance = progress - state.start_progress
        entry = state.entry_kph
        if entry is None and self._previous_distance < ENTRY_DISTANCE <= distance:
            fraction = (ENTRY_DISTANCE - self._previous_distance) / (distance - self._previous_distance)
            entry = (self._previous_forward_speed + (forward_speed-self._previous_forward_speed)*fraction) * 3.6
        held = state.hold_seconds + dt if entry is not None and speed < STOP_SPEED else 0.
        self.snapshot = replace(state, position=distance, entry_kph=entry, hold_seconds=held)
        self._previous_distance, self._previous_forward_speed = distance, forward_speed
        if collisions:
            self.stop("发生碰撞；重新挑战时留在道路内。")
        elif reset:
            self.stop("车辆复位；重新挑战从静止开始。")
        elif abs(lateral) > COURSE_HALF_WIDTH:
            self.stop("驶离练习道路；请把车身中心保持在三车道标记内。")
        elif entry is not None and entry < ENTRY_KPH:
            self.stop(f"入门仅{entry:.1f}km/h；先加速至80km/h再过门。")
        elif distance > TARGET_DISTANCE + 10:
            self.stop("驶过停车区；下次提前开始制动。")
        elif elapsed > TIME_LIMIT:
            self.stop("练习超时；在30秒内完成测速与停车。")
        elif held >= HOLD_SECONDS - 1e-9:
            error = distance - TARGET_DISTANCE
            medal = medal_for(abs(error))
            self.snapshot = replace(self.snapshot, error_m=error, medal=medal)
            if medal:
                if self.record_scores:
                    self.scores.record(abs(error))
                self.stop(f"{medal}牌 · 已停稳1秒", succeeded=True)
                self.snapshot = replace(self.snapshot, best_error=self.scores.best if self.record_scores else None,
                                        save_notice=self.scores.notice)
            else:
                self.stop("停得过早；下次稍晚开始制动。" if error < 0 else "停车误差超过10米。")
        return self.snapshot

    def stop(self, reason, *, succeeded=False):
        if not self.snapshot.finished:
            self.snapshot = replace(self.snapshot, finished=True, succeeded=succeeded, reason=reason)
