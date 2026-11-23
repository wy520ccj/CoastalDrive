"""从权威完成步判安全超车；只读取快照，不控制交通或车辆。"""

import math
from dataclasses import dataclass, replace

from overtake_observations import GapIncident, TrafficReading, gap_incident, nearby
from overtake_routes import OVERTAKE_ROUTES
from race import GameMode
from vehicle_config import body_center

SEED = 17
DISTANCE_LIMIT = 2000.
TIME_LIMIT = 150.
PASS_TARGET = 2
SIDE_GAP = 1.
END_GAP = 10.
TARGETS = (("金", 85.), ("银", 110.), ("铜", 150.))
RULES = ("固定直线 · 原生12车 · 使用当前车辆\n"
         "2公里 / 150秒内，安全超越2辆即完成\n"
         "并行侧距至少1米；跟车/切回前后距至少10米\n"
         "从后方接近，整车超出10米才计数\n"
         "贴身/碰撞/越界/逆向/复位失败\n金85秒 · 银110秒 · 铜150秒")


def body(car, config):
    """道路坐标中的完整车身包络；不用交通感知的内收尺寸。"""
    angle = math.radians(car.heading)
    sine, cosine = math.sin(angle), math.cos(angle)
    cx, cy, _ = body_center(config)
    x, y, _ = car.position
    return (x+cx*cosine-cy*sine, y+cx*sine+cy*cosine,
            config.collision_half_width*abs(cosine)+config.collision_half_length*abs(sine),
            config.collision_half_length*abs(cosine)+config.collision_half_width*abs(sine))


def swept_close(previous, current, width, length):
    """线性相对轨迹是否进入间距禁区；相邻完成步间也不能跳过检查。"""
    low, high = 0., 1.
    for a, b, extent in zip(previous, current, (width, length), strict=True):
        if a == b:
            if abs(a) >= extent:
                return False
        else:
            first, last = sorted(((-extent-a)/(b-a), (extent-a)/(b-a)))
            low, high = max(low, first), min(high, last)
            if low >= high:
                return False
    return low < high


@dataclass(frozen=True)
class OvertakeResult:
    start_progress: float
    distance: float = 0.
    seconds: float = 0.
    passes: int = 0
    pass_times: tuple = ()
    pass_ids: tuple = ()
    pass_clearances: tuple = ()
    feedback: str = "观察车流，留好距离再择道"
    finished: bool = False
    succeeded: bool = False
    reason: str = ""
    medal: str = ""
    best_seconds: float | None = None
    reference_times: tuple = ()
    new_best: bool = False
    save_notice: str = ""
    route_id: str = GameMode.SAFE_OVERTAKE.value
    traffic_reading: TrafficReading | None = None
    incident: GapIncident | None = None


class OvertakeRun:
    def __init__(self, initial, config, scores, variant, *, mode=GameMode.SAFE_OVERTAKE, road=None,
                 record_scores=True):
        self.config, self.scores = config, scores
        self.mode, self.route, self.road = mode, OVERTAKE_ROUTES[mode], road
        self.record_scores = record_scores
        if not record_scores:
            self.route = replace(self.route, finish_at_end=True)
        if self.route.shape != "straight" and road is None:
            raise ValueError("弯坡车流需要本次权威道路的只读坐标接口")
        initial = self.local_state(initial)
        self.score_id = (f"{self.route.score_prefix}:{self.route.shape}:seed-{self.route.seed}:"
                         f"12-540:{self.route.passes}-in-{self.route.distance:g}:1-10:"+variant)
        self.snapshot = OvertakeResult(initial.player.position[1]+initial.origin_y,
            best_seconds=scores.get(mode, self.score_id) if record_scores else None,
            reference_times=(scores.get_splits(mode, self.score_id, self.route.passes+int(self.route.finish_at_end))
                             if record_scores else ()),
            save_notice=scores.notice, route_id=mode.value)
        self.previous = self.geometry(initial)
        self.candidates = {}
        self.seen = set()

    def local_state(self, state):
        """弯坡沿权威道路投影；只构造本拍规则输入，不写回物理快照。"""
        if self.route.shape == "straight":
            return state
        return replace(state, player=self.road.lane_frame(state.player),
                       traffic=tuple(self.road.lane_frame(car) for car in state.traffic), origin_y=0.)

    def geometry(self, state):
        own = body(state.player, self.config)
        return own, {(slot, car.generation): body(car, self.config)
                     for slot, car in enumerate(state.traffic) if car.active}

    def update(self, state, elapsed, *, reset=False):
        result = self.snapshot
        if result.finished:
            return result
        state = self.local_state(state)
        distance = state.player.position[1]+state.origin_y-result.start_progress
        self.snapshot = replace(result, distance=distance, seconds=elapsed)
        own, traffic = self.geometry(state)
        self.snapshot = replace(self.snapshot, traffic_reading=nearby(state, own, traffic, SIDE_GAP, END_GAP))
        old_own, old_traffic = self.previous
        self.previous = own, traffic
        if state.collisions:
            self.stop("发生碰撞；留足空间再超车。")
        elif reset:
            self.stop("车辆复位；重新出发再挑战。")
        elif abs(own[0])+own[2] > 6.5:
            self.stop("车身驶离道路；在车道内完成超越。")
        elif state.player.velocity[1] < -.5 or abs(state.player.heading) > 45:
            self.stop("逆向行驶；本挑战须沿车流前进。")
        if self.snapshot.finished:
            return self.snapshot
        at_end = distance >= self.route.distance
        finish = deadline = 1.
        if not self.record_scores:
            if at_end and result.distance < self.route.distance:
                finish = (self.route.distance-result.distance)/(distance-result.distance)
            if elapsed > self.route.seconds:
                deadline = (self.route.seconds-result.seconds)/(elapsed-result.seconds)
        pass_window = min(finish, deadline)
        # 只比较同一槽位同一代次。回收/消失后不延续旧候选或跨位置插值。
        self.candidates = {key: value for key, value in self.candidates.items() if key in traffic and key in old_traffic}
        completed = []
        eligible = {(slot, car.generation) for slot, car in enumerate(state.traffic)
                    if car.active and abs(car.heading) <= 45 and car.velocity[1] >= -.5}
        self.candidates = {key: value for key, value in self.candidates.items() if key in eligible}
        for key, other in traffic.items():
            dx, dy = other[0]-own[0], other[1]-own[1]
            width, length = own[2]+other[2], own[3]+other[3]
            old = old_traffic.get(key)
            previous = (dx, dy) if old is None else (old[0]-old_own[0], old[1]-old_own[1])
            swept_width = width if old is None else max(width, old_own[2]+old[2])
            swept_length = length if old is None else max(length, old_own[3]+old[3])
            if swept_close(previous, (dx, dy), swept_width+SIDE_GAP, swept_length+END_GAP):
                incident = gap_incident(key, previous, (dx, dy),
                    swept_width, swept_length, SIDE_GAP, END_GAP, result, self.snapshot, old is not None)
                self.snapshot = replace(self.snapshot, incident=incident)
                label, gap, minimum = (("并行侧距", incident.side_m, SIDE_GAP) if incident.kind == 'parallel'
                    else ("前方净距" if incident.kind == 'front' else "后方净距", incident.end_m, END_GAP))
                self.stop(f"与#{key[0]+1}间距不足 · {label}{gap:.2f}m，至少{minimum:g}m")
                return self.snapshot
            if key in eligible and key not in self.seen and dy >= length+END_GAP:
                self.candidates.setdefault(key, math.inf)
            if key in self.candidates:
                # 记录实际并排区的最小完整车身侧距；两侧远离时不制造虚假余量。
                if abs(dy) < length:
                    self.candidates[key] = min(self.candidates[key], abs(dx)-width)
                if dy <= -length-END_GAP and previous[1] > -swept_length-END_GAP:
                    clearance = self.candidates.pop(key)
                    pass_seconds = elapsed
                    if pass_window < 1.:
                        # 在终点或截止时刻采样完整车身净距，之后才达到10米的超车不计入。
                        old_gap = -previous[1]-old_own[3]-old[3]
                        gain = -dy-length-old_gap
                        gap = old_gap+gain*pass_window
                        if gap < END_GAP:
                            continue
                        fraction = (END_GAP-old_gap)/gain if old_gap < END_GAP else 0.
                        pass_seconds = result.seconds+(elapsed-result.seconds)*fraction
                    completed.append((pass_seconds, key, clearance))
        # 先检查所有车辆，再授予本拍超车；同拍别处贴身不能获得成功成绩。
        for pass_seconds, key, clearance in sorted(completed):
            if self.snapshot.passes >= self.route.passes:
                break
            self.seen.add(key)
            if not math.isfinite(clearance):
                continue
            now = self.snapshot
            self.snapshot = replace(now, passes=now.passes+1, pass_times=(*now.pass_times, pass_seconds),
                pass_ids=(*now.pass_ids, key), pass_clearances=(*now.pass_clearances, clearance),
                feedback=f"安全超车 {now.passes+1}/{self.route.passes} · 并排最小侧距{clearance:.2f}米")
            if self.snapshot.passes == self.route.passes:
                break
        if distance > self.route.distance and not self.route.finish_at_end:
            self.stop(f"已到{self.route.distance/1000:g}公里，仅安全超越{self.snapshot.passes}/{self.route.passes}辆；提前观察慢车与空车道。")
        elif elapsed > self.route.seconds and not (not self.record_scores and at_end and finish <= deadline):
            self.stop(f"超过{self.route.seconds:g}秒；保持节奏，在安全空隙完成超越。")
        elif at_end and self.route.finish_at_end and self.snapshot.passes < self.route.passes:
            self.stop(f"已到{self.route.distance/1000:g}公里，仅安全超越{self.snapshot.passes}/{self.route.passes}辆；提前观察慢车与空车道。")
        elif self.snapshot.passes == self.route.passes and (not self.route.finish_at_end or at_end):
            times = (*self.snapshot.pass_times, elapsed) if self.route.finish_at_end else self.snapshot.pass_times
            # 两辆同拍完成时保留真实相同时间；旧最佳格式只接受严格递增分段。
            splits = times if all(a < b for a, b in zip((0., *times), times)) else None
            best, saved = (self.scores.record(self.mode, elapsed, self.score_id, splits=splits)
                           if self.record_scores else (None, False))
            medal = next(m for m, t in self.route.targets if elapsed <= t) if self.record_scores else ''
            self.snapshot = replace(self.snapshot, medal=medal,
                best_seconds=best, new_best=saved and (result.best_seconds is None or elapsed < result.best_seconds),
                save_notice=self.scores.error or self.scores.notice)
            award = f" · {medal}牌完成" if medal else ""
            self.stop(f"安全超越{self.route.passes}辆"+award, succeeded=True)
        return self.snapshot

    def stop(self, reason, *, succeeded=False):
        if not self.snapshot.finished:
            self.snapshot = replace(self.snapshot, finished=True, succeeded=succeeded, reason=reason)
