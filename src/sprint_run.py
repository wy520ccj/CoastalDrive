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
    gate_kph: tuple = ()
    forward_kph: float = 0.
    zone_min_kph: float | None = None
    zone_max_kph: float | None = None
    zone_error_at: float | None = None
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
        self.previous = (0., 0., 0., 0., 0.)

    def update(self, progress, elapsed, *, lateral, heading, forward_speed=0., collisions=0, reset=False):
        state = self.snapshot
        if state.finished:
            return state
        position = progress-state.start_progress
        py, px, ph, pt, pv = self.previous
        kph = forward_speed*3.6
        self.previous = position, lateral, heading, elapsed, kph
        self.snapshot = replace(state, position=position, seconds=elapsed, forward_kph=kph)
        if collisions:
            self.stop("发生碰撞；弯前减速，保留出弯空间。")
        elif reset:
            self.stop("车辆复位；重新出发再计时。")
        elif abs(lateral) > ROAD_HALF_WIDTH:
            self.stop("驶离赛事道路；提前看清弯势再加速。")
        if self.snapshot.finished:
            return self.snapshot
        zone = self.route.speed_zone
        if zone is not None:
            low, high = max(min(py, position), zone.start), min(max(py, position), zone.end)
            if low <= high:
                # 只检查本拍轨迹与限速带的交集；进出边界插值，区外速度不带入。
                samples = ((low, pv+(kph-pv)*(low-py)/(position-py)),
                           (high, pv+(kph-pv)*(high-py)/(position-py))) if position != py else ((position, pv), (position, kph))
                values = tuple(value for _, value in samples)
                minimum, maximum = min(values), max(values)
                self.snapshot = replace(self.snapshot,
                    zone_min_kph=minimum if state.zone_min_kph is None else min(state.zone_min_kph, minimum),
                    zone_max_kph=maximum if state.zone_max_kph is None else max(state.zone_max_kph, maximum))
                if minimum < zone.minimum_kph or maximum > zone.maximum_kph:
                    where, wrong = next((where, value) for where, value in samples
                                        if value < zone.minimum_kph or value > zone.maximum_kph)
                    kind = f"低于{zone.minimum_kph:g}" if wrong < zone.minimum_kph else f"超过{zone.maximum_kph:g}"
                    self.snapshot = replace(self.snapshot, zone_error_at=where)
                    self.stop(f"限速带{where:.1f}米：{wrong:.2f}km/h，{kind}；全段须保持"
                              f"{zone.minimum_kph:g}–{zone.maximum_kph:g}km/h。")
                    return self.snapshot
        while self.snapshot.gates < len(self.route.gates):
            index = self.snapshot.gates
            distance = self.route.gates[index]
            if not py < distance <= position:
                break
            fraction = (distance-py)/(position-py)
            seconds = pt+(elapsed-pt)*fraction
            gate_kph = pv+(kph-pv)*fraction
            yaw = math.radians(ph+((heading-ph+180)%360-180)*fraction)
            center = px+(lateral-px)*fraction-math.sin(yaw)*body_center(self.config)[1]
            span = (self.config.collision_half_width*abs(math.cos(yaw))
                    + self.config.collision_half_length*abs(math.sin(yaw)))
            clearance = ROAD_HALF_WIDTH-span-abs(center)
            if seconds > TIME_LIMIT:
                break
            self.snapshot = replace(self.snapshot, gate_times=(*self.snapshot.gate_times, seconds),
                                    gate_kph=(*self.snapshot.gate_kph, gate_kph),
                                    clearances=(*self.snapshot.clearances, clearance))
            if index == 0 and self.route.entry_kph > 0 and gate_kph < self.route.entry_kph:
                self.stop(f"测速门仅{gate_kph:.1f}km/h；{distance:g}米门至少{self.route.entry_kph:g}km/h。")
                break
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
