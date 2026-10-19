"""沿权威道路坐标判定短途门序和用时；不创建或修改物理车辆。"""

import math
from dataclasses import dataclass, replace

from sprint_routes import SPRINT_ROUTES
from vehicle_config import body_center

TIME_LIMIT = 180.
ROAD_HALF_WIDTH = 6.5


@dataclass(frozen=True)
class SprintResult:
    route_id: str
    start_progress: float
    position: float = 0.
    seconds: float = 0.
    gates: int = 0
    gate_times: tuple = ()
    reference_times: tuple = ()
    clearances: tuple = ()
    medal: str = ""
    finished: bool = False
    succeeded: bool = False
    reason: str = ""
    best_seconds: float | None = None
    new_best: bool = False
    save_notice: str = ""


class SprintRun:
    def __init__(self, progress, mode, scores, variant, config):
        self.mode, self.scores, self.config = mode, scores, config
        self.route = SPRINT_ROUTES[mode]
        self.score_id = f"sprint-v1:{mode.value}:seed-{self.route.seed}:"+variant
        self.snapshot = SprintResult(mode.value, progress, best_seconds=scores.get(mode, self.score_id),
            reference_times=scores.get_splits(mode, self.score_id, len(self.route.gates)), save_notice=scores.notice)
        self.previous = (0., 0., 0., 0.)

    def update(self, progress, elapsed, *, lateral, heading, collisions=0, reset=False):
        state = self.snapshot
        if state.finished:
            return state
        position = progress-state.start_progress
        py, px, ph, pt = self.previous
        self.previous = position, lateral, heading, elapsed
        self.snapshot = replace(state, position=position, seconds=elapsed)
        if collisions:
            self.stop("发生碰撞；弯前减速，保留出弯空间。")
        elif reset:
            self.stop("车辆复位；重新出发再计时。")
        elif abs(lateral) > ROAD_HALF_WIDTH:
            self.stop("驶离赛事道路；提前看清弯势再加速。")
        if self.snapshot.finished:
            return self.snapshot
        while self.snapshot.gates < len(self.route.gates):
            index = self.snapshot.gates
            distance = self.route.gates[index]
            if not py < distance <= position:
                break
            fraction = (distance-py)/(position-py)
            seconds = pt+(elapsed-pt)*fraction
            yaw = math.radians(ph+((heading-ph+180)%360-180)*fraction)
            center = px+(lateral-px)*fraction-math.sin(yaw)*body_center(self.config)[1]
            span = (self.config.collision_half_width*abs(math.cos(yaw))
                    + self.config.collision_half_length*abs(math.sin(yaw)))
            clearance = ROAD_HALF_WIDTH-span-abs(center)
            if seconds > TIME_LIMIT:
                break
            self.snapshot = replace(self.snapshot, gate_times=(*self.snapshot.gate_times, seconds),
                                    clearances=(*self.snapshot.clearances, clearance))
            if clearance < 0:
                self.stop(f"错过第{index+1}道门；车身超出道路门线{-clearance:.2f}m。")
                break
            self.snapshot = replace(self.snapshot, gates=index+1)
            if index+1 == len(self.route.gates):
                best, saved = self.scores.record(self.mode, seconds, self.score_id, splits=self.snapshot.gate_times)
                medal = self.route.medal_for(seconds)
                self.snapshot = replace(self.snapshot, seconds=seconds, medal=medal, best_seconds=best,
                    new_best=saved and (state.best_seconds is None or seconds < state.best_seconds),
                    save_notice=self.scores.error or self.scores.notice)
                self.stop(f"{self.route.name} · "+(f"{medal}牌完成" if medal else "有效完成，继续争取铜牌"), succeeded=True)
        if not self.snapshot.finished and elapsed > TIME_LIMIT:
            self.stop("赛事超时；180秒内依次完成全部道路门。")
        return self.snapshot

    def stop(self, reason, *, succeeded=False):
        if not self.snapshot.finished:
            self.snapshot = replace(self.snapshot, finished=True, succeeded=succeeded, reason=reason)
