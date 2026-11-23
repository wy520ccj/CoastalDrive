"""连续左右过门的完成步规则；门线只作判定，不施加物理力。"""

import json
import math
from dataclasses import dataclass, replace
from itertools import pairwise
from pathlib import Path

from race import GameMode
from vehicle_config import body_center

ENTRY_DISTANCE = 80.
ENTRY_KPH = 40.
GATES = ((120., -2.), (160., 2.), (200., -2.), (240., 2.), (280., -2.), (320., 0.))
GATE_HALF_WIDTH = 2.
TIME_LIMIT = 40.
COURSE_HALF_WIDTH = 6.5
SLALOM_MODES = (GameMode.SLALOM_LESSON, GameMode.FAST_SLALOM, GameMode.SLALOM_PRACTICE)
FAST_MIN_KPH, FAST_MAX_KPH = 70., 80.


def medal_for(seconds, *, fast=False):
    if fast:
        return "金" if seconds <= 11.5 else "银" if seconds <= 12.5 else "铜" if seconds <= 14 else ""
    return "金" if seconds <= 15 else "银" if seconds <= 18 else "铜" if seconds <= 24 else ""


def checked_run(run, seconds):
    """逐门详情只能对应这一整次成功最佳，不拼接更快的单门。"""
    times, margins = run["gate_times"], run["clearances"]
    if (type(run["seconds"]) not in (int, float) or run["seconds"] != seconds
            or not isinstance(times, (list, tuple)) or not isinstance(margins, (list, tuple))
            or len(times) != len(GATES) or len(margins) != len(GATES)
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in (*times, *margins))
            or times[0] <= 0 or any(b <= a for a, b in pairwise(times))
            or times[-1] != seconds or any(value < 0 for value in margins)):
        raise ValueError("逐门详情与成功最佳不一致")
    return {"seconds": seconds, "gate_times": list(times), "clearances": list(margins)}


class SlalomScores:
    def __init__(self, path, key):
        self.path, self.key = Path(path), key
        self.notice = ""
        values, runs = self.read()
        self.best = values.get(key)
        self.best_run = self.read_run(runs)

    def read(self):
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(document, dict) or type(document["version"]) is not int or document["version"] != 1
                    or not isinstance(document["scores"], dict)
                    or any(not isinstance(key, str) or type(value) not in (int, float)
                           or not math.isfinite(value) or not 0 < value <= 24
                           for key, value in document["scores"].items())):
                raise ValueError("过门成绩格式错误")
            runs = document.get("runs", {})
            if not isinstance(runs, dict):
                self.notice = "历史逐门详情未读取，总成绩保留。"
                runs = {}
            return document["scores"], runs
        except FileNotFoundError:
            return {}, {}
        except (OSError, ValueError, KeyError, TypeError):
            self.notice = "历史过门成绩未读取，可继续练习。"
            return {}, {}

    def load(self):
        return self.read()[0]

    def read_run(self, runs):
        if self.key not in runs:
            return None
        try:
            return checked_run(runs[self.key], self.best)
        except (ValueError, KeyError, TypeError, IndexError):
            self.notice = "历史逐门详情未读取，总成绩保留。"
            return None

    def record(self, seconds, *, gate_times=(), clearances=()):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 24:
            raise ValueError("只能保存已通过课题的有限正用时")
        detail = checked_run({"seconds": seconds, "gate_times": gate_times, "clearances": clearances}, seconds) if gate_times or clearances else None
        values, runs = self.read()
        best = values.get(self.key)
        if best is not None and best <= seconds:
            self.best = best
            self.best_run = self.read_run(runs)
            return False
        values[self.key] = seconds
        if detail is None:
            runs.pop(self.key, None)
        else:
            runs[self.key] = detail
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"version": 1, "scores": values, "runs": runs}, ensure_ascii=False,
                                            indent=2, allow_nan=False), encoding="utf-8")
            temporary.replace(self.path)
        except (OSError, ValueError):
            self.notice = "本次过门成绩未保存，请检查存储目录。"
            return False
        self.best, self.best_run, self.notice = seconds, detail, ""
        return True


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
    gate_times: tuple = ()
    reference_times: tuple = ()
    medal: str = ""
    finished: bool = False
    succeeded: bool = False
    reason: str = ""
    best_seconds: float | None = None
    save_notice: str = ""
    new_best: bool = False
    fast: bool = False
    practice: bool = False
    zone_min_kph: float | None = None
    zone_max_kph: float | None = None
    zone_error_at: float | None = None


class SlalomLesson:
    def __init__(self, start_progress, scores, config, *, fast=False, practice=False, record_scores=True):
        self.scores, self.config = scores, config
        self.record_scores = record_scores
        self.snapshot = SlalomResult(start_progress=start_progress, best_seconds=scores.best if record_scores else None, fast=fast, practice=practice,
            save_notice=scores.notice,
            reference_times=tuple(scores.best_run["gate_times"]) if record_scores and scores.best_run is not None else ())
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
        elif not state.practice and entry is not None and entry < (FAST_MIN_KPH if state.fast else ENTRY_KPH):
            self.stop(f"入门仅{entry:.1f}km/h；至少{'70' if state.fast else '40'}km/h通过80米入口。")
        if self.snapshot.finished or start is None:
            return self.snapshot
        if state.fast:
            self.check_speed_band(py, distance, pv, forward_speed)
            if self.snapshot.finished:
                return self.snapshot
        while len(self.snapshot.gate_times) < len(GATES):
            index = len(self.snapshot.gate_times)
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
                clearances=(*self.snapshot.clearances, clearance),
                gate_times=(*self.snapshot.gate_times, pt+(elapsed-pt)*fraction-start))
            if clearance < 0 and not state.practice:
                self.stop(f"错过第{index+1}门；车身超出门线{-clearance:.2f}m，提前回正/稍早减速。")
                break
            self.snapshot = replace(self.snapshot, gates=self.snapshot.gates+int(clearance >= 0))
            if index+1 == len(GATES):
                seconds = pt+(elapsed-pt)*fraction-start
                if state.practice:
                    self.snapshot = replace(self.snapshot, run_seconds=seconds)
                    self.stop(f'练习完成 · 通过{self.snapshot.gates}/6门；可回工坊调整前轮再试。', succeeded=True)
                    break
                medal = medal_for(seconds, fast=state.fast)
                self.snapshot = replace(self.snapshot, run_seconds=seconds, medal=medal)
                if medal:
                    improved = self.snapshot.best_seconds is None or seconds < self.snapshot.best_seconds
                    saved = (self.scores.record(seconds, gate_times=self.snapshot.gate_times,
                                               clearances=self.snapshot.clearances) if self.record_scores else False)
                    self.snapshot = replace(self.snapshot, best_seconds=self.scores.best if self.record_scores else None,
                                            save_notice=self.scores.notice, new_best=saved and improved)
                    self.stop(f"{medal}牌 · 连续通过全部6道门", succeeded=True)
                else:
                    self.stop(f"已过全部门但超过{'14' if state.fast else '24'}秒；尝试更流畅的转向节奏。")
        return self.snapshot

    def check_speed_band(self, previous, distance, old_speed, speed):
        """只检查入口至终点的真实完成步，跨越边界时插值，不检查终点之后。"""
        if distance <= previous:
            if ENTRY_DISTANCE <= previous < GATES[-1][0]:
                self.snapshot = replace(self.snapshot, zone_error_at=distance)
                self.stop('高速验车带内未向前；保持70–80km/h连续过门。')
            return
        begin, end = max(previous, ENTRY_DISTANCE), min(distance, GATES[-1][0])
        if end < begin:
            return
        for position in (begin, end):
            kph = (old_speed+(speed-old_speed)*(position-previous)/(distance-previous))*3.6
            state = self.snapshot
            self.snapshot = replace(state,
                zone_min_kph=kph if state.zone_min_kph is None else min(state.zone_min_kph, kph),
                zone_max_kph=kph if state.zone_max_kph is None else max(state.zone_max_kph, kph))
            if not FAST_MIN_KPH <= kph <= FAST_MAX_KPH:
                self.snapshot = replace(self.snapshot, zone_error_at=position)
                self.stop(f'高速验车{position:.1f}米处{kph:.1f}km/h；全段须保持70–80km/h。')
                return

    def stop(self, reason, *, succeeded=False):
        if not self.snapshot.finished:
            self.snapshot = replace(self.snapshot, finished=True, succeeded=succeeded, reason=reason)
