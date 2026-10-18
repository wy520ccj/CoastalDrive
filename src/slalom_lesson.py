"""连续左右过门的完成步规则；门线只作判定，不施加物理力。"""

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

from vehicle_config import body_center

ENTRY_DISTANCE = 80.
ENTRY_KPH = 40.
GATES = ((120., -2.), (160., 2.), (200., -2.), (240., 2.), (280., -2.), (320., 0.))
GATE_HALF_WIDTH = 2.
TIME_LIMIT = 40.
COURSE_HALF_WIDTH = 6.5


def medal_for(seconds):
    return "金" if seconds <= 15 else "银" if seconds <= 18 else "铜" if seconds <= 24 else ""


class SlalomScores:
    def __init__(self, path, key):
        self.path, self.key = Path(path), key
        self.notice = ""
        self.best = self.load().get(key)

    def load(self):
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(document, dict) or type(document["version"]) is not int or document["version"] != 1
                    or not isinstance(document["scores"], dict)
                    or any(not isinstance(key, str) or type(value) not in (int, float)
                           or not math.isfinite(value) or not 0 < value <= 24
                           for key, value in document["scores"].items())):
                raise ValueError("过门成绩格式错误")
            return document["scores"]
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, KeyError, TypeError):
            self.notice = "历史过门成绩未读取，可继续练习。"
            return {}

    def record(self, seconds):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 24:
            raise ValueError("只能保存已通过课题的有限正用时")
        values = self.load()
        best = values.get(self.key)
        if best is not None and best <= seconds:
            self.best = best
            return
        values[self.key] = seconds
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"version": 1, "scores": values}, ensure_ascii=False,
                                            indent=2, allow_nan=False), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            self.notice = "本次过门成绩未保存，请检查存储目录。"
            return
        self.best, self.notice = seconds, ""


@dataclass(frozen=True)
class SlalomResult:
    start_progress: float = 0.
    position: float = 0.
    entry_kph: float | None = None
    entry_time: float | None = None
    run_seconds: float = 0.
    gates: int = 0
    errors: tuple = ()
    clearances: tuple = ()
    medal: str = ""
    finished: bool = False
    succeeded: bool = False
    reason: str = ""
    best_seconds: float | None = None
    save_notice: str = ""


class SlalomLesson:
    def __init__(self, start_progress, scores, config):
        self.scores, self.config = scores, config
        self.snapshot = SlalomResult(start_progress=start_progress, best_seconds=scores.best,
                                     save_notice=scores.notice)
        self._previous = (0., 0., 0., 0., 0.)

    def update(self, progress, forward_speed, elapsed, *, lateral=0., heading=0., collisions=0, reset=False):
        state = self.snapshot
        if state.finished:
            return state
        distance = progress-state.start_progress
        py, px, ph, pv, pt = self._previous
        entry, start = state.entry_kph, state.entry_time
        if entry is None and py < ENTRY_DISTANCE <= distance:
            fraction = (ENTRY_DISTANCE-py)/(distance-py)
            entry = (pv+(forward_speed-pv)*fraction)*3.6
            start = pt+(elapsed-pt)*fraction
        self.snapshot = replace(state, position=distance, entry_kph=entry, entry_time=start,
                                run_seconds=elapsed-start if start is not None else 0.)
        self._previous = (distance, lateral, heading, forward_speed, elapsed)
        if collisions:
            self.stop("发生碰撞；减速并留在课题道路内。")
        elif reset:
            self.stop("车辆复位；重新挑战再计时。")
        elif abs(lateral) > COURSE_HALF_WIDTH:
            self.stop("驶离课题道路；提前看下一道门。")
        elif elapsed > TIME_LIMIT:
            self.stop("课题超时；40秒内完成，入口后最多24秒。")
        elif entry is not None and entry < ENTRY_KPH:
            self.stop(f"入门仅{entry:.1f}km/h；至少40km/h通过80米入口。")
        if self.snapshot.finished or start is None:
            return self.snapshot
        while self.snapshot.gates < len(GATES):
            index = self.snapshot.gates
            gate_y, gate_x = GATES[index]
            if not py < gate_y <= distance:
                break
            fraction = (gate_y-py)/(distance-py)
            x = px+(lateral-px)*fraction
            yaw = math.radians(ph+((heading-ph+180)%360-180)*fraction)
            # 按车身俯视矩形计宽，斜着过门也必须留出整车宽度。
            span = (self.config.collision_half_width*abs(math.cos(yaw))
                    +self.config.collision_half_length*abs(math.sin(yaw)))
            error = x-math.sin(yaw)*body_center(self.config)[1]-gate_x
            clearance = GATE_HALF_WIDTH-span-abs(error)
            self.snapshot = replace(self.snapshot, errors=(*self.snapshot.errors, error),
                                    clearances=(*self.snapshot.clearances, clearance))
            if clearance < 0:
                self.stop(f"错过第{index+1}门；车身超出门线{-clearance:.2f}m，提前回正/稍早减速。")
                break
            self.snapshot = replace(self.snapshot, gates=index+1)
            if index+1 == len(GATES):
                seconds = pt+(elapsed-pt)*fraction-start
                medal = medal_for(seconds)
                self.snapshot = replace(self.snapshot, run_seconds=seconds, medal=medal)
                if medal:
                    self.scores.record(seconds)
                    self.snapshot = replace(self.snapshot, best_seconds=self.scores.best,
                                            save_notice=self.scores.notice)
                    self.stop(f"{medal}牌 · 连续通过全部6道门", succeeded=True)
                else:
                    self.stop("已过全部门但超过24秒；尝试更流畅的转向节奏。")
        return self.snapshot

    def stop(self, reason, *, succeeded=False):
        if not self.snapshot.finished:
            self.snapshot = replace(self.snapshot, finished=True, succeeded=succeeded, reason=reason)
