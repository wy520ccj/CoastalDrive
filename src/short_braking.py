"""短距制动验车：入门速度受限，最大前进距离不能靠倒车缩短。"""

from dataclasses import replace

from braking_lesson import ENTRY_DISTANCE, HOLD_SECONDS, STOP_SPEED, TIME_LIMIT, BrakingResult

MAX_DISTANCE = 42.
MIN_KPH, MAX_KPH = 80., 85.


def medal_for(distance):
    return '金' if distance <= 33 else '银' if distance <= 36 else '铜' if distance <= MAX_DISTANCE else ''


class ShortBraking:
    def __init__(self, start_progress, scores):
        self.scores = scores
        self.snapshot = BrakingResult(start_progress=start_progress, short=True,
                                      best_distance=scores.best, save_notice=scores.notice)
        self.previous = self.previous_speed = self.maximum = 0.

    def update(self, progress, forward_speed, speed, elapsed, dt, *, collisions=0, reset=False, lateral=0., heading=0.):
        state = self.snapshot
        if state.finished:
            return state
        distance = progress-state.start_progress
        entry = state.entry_kph
        if entry is None and self.previous < ENTRY_DISTANCE <= distance:
            fraction = (ENTRY_DISTANCE-self.previous)/(distance-self.previous)
            entry = (self.previous_speed+(forward_speed-self.previous_speed)*fraction)*3.6
        self.previous, self.previous_speed = distance, forward_speed
        if entry is not None:
            self.maximum = max(self.maximum, distance-ENTRY_DISTANCE)
        held = state.hold_seconds+dt if entry is not None and speed < STOP_SPEED else 0.
        self.snapshot = replace(state, position=distance, entry_kph=entry, hold_seconds=held,
                                stopping_m=self.maximum if entry is not None else None)
        if collisions:
            self.stop('发生碰撞；重新验车。')
        elif reset:
            self.stop('车辆复位；重新从静止开始。')
        elif abs(lateral) > 1. or abs((heading+180)%360-180) > 5.:
            self.stop('驶离直行验车带；车身中心横向≤1米、车头偏角≤5°。')
        elif entry is not None and not MIN_KPH <= entry <= MAX_KPH:
            self.stop(f'入门{entry:.1f}km/h；须80–85km/h过100米门。')
        elif entry is not None and forward_speed < -.15:
            self.stop('出现倒车；松开S后保持停稳。')
        elif self.maximum > MAX_DISTANCE:
            self.stop('超过42米停车线；下次过门后更早制动，或比较制动分配。')
        elif elapsed > TIME_LIMIT:
            self.stop('验车超时；30秒内过门并停稳。')
        elif held >= HOLD_SECONDS-1e-9:
            medal = medal_for(self.maximum)
            self.scores.record(self.maximum)
            self.snapshot = replace(self.snapshot, medal=medal, best_distance=self.scores.best,
                                    save_notice=self.scores.notice)
            self.stop(f'{medal}牌 · 过门后{self.maximum:.2f}米，已停稳1秒', succeeded=True)
        return self.snapshot

    def stop(self, reason, *, succeeded=False):
        if not self.snapshot.finished:
            self.snapshot = replace(self.snapshot, finished=True, succeeded=succeeded, reason=reason)
