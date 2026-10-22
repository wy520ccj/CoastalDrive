"""生涯比赛判定：只读取权威车体状态，不修改物理参数或驾驶输入。"""

import math
from dataclasses import dataclass, replace

from career import EVENT_BY_ID

GATE_HALF_WIDTH = 2.6
ROAD_HALF_WIDTH = 8.5


@dataclass(frozen=True)
class CareerResult:
    event_id: str
    start_progress: float
    position: float = 0.
    elapsed: float = 0.
    passed: tuple = ()
    stopping_ticks: int = 0
    parking_error: float | None = None
    finished: bool = False
    succeeded: bool = False
    stars: int = 0
    reason: str = ''


class CareerRun:
    def __init__(self, event_id, start_progress, config):
        self.event, self.config = EVENT_BY_ID[event_id], config
        self.snapshot = CareerResult(event_id, start_progress)
        self.previous = (0., 0., 0.)

    def update(self, progress, elapsed, *, lateral, heading, speed, collisions, reset):
        state, event = self.snapshot, self.event
        if state.finished:
            return state
        distance = progress-state.start_progress
        py, px, ph = self.previous
        self.previous = distance, lateral, heading
        self.snapshot = replace(state, position=distance, elapsed=elapsed)
        angle = math.radians(heading)
        half = abs(math.cos(angle))*self.config.collision_half_width+abs(math.sin(angle))*self.config.collision_half_length
        if collisions or reset or abs(lateral)+half > ROAD_HALF_WIDTH:
            return self.stop('发生碰撞，请降低入弯速度。' if collisions else
                             '本次使用了复位，重试即可重新挑战。' if reset else '驶离赛道，请留在路面上。')
        if elapsed > event.limit:
            return self.stop('超过本场时限，重试时可以更早起步。')
        if event.kind == 'parking':
            error = abs(distance-event.distance)
            ticks = state.stopping_ticks+1 if error <= 20 and speed < .25 else 0
            self.snapshot = replace(self.snapshot, stopping_ticks=ticks, parking_error=error)
            if distance > event.distance+25:
                return self.stop('驶过停车区了，下次提前松油并刹车。')
            if ticks >= 60:
                return self.stop('车辆已在停车区停稳。', stars=3 if error <= 3 else 2 if error <= 10 else 1)
            return self.snapshot
        passed = list(state.passed)
        for index, (gate_y, center) in enumerate(event.gates):
            if index < len(passed) or not py < gate_y <= distance:
                continue
            fraction = (gate_y-py)/(distance-py)
            x, h = px+(lateral-px)*fraction, math.radians(ph+(heading-ph)*fraction)
            extent = abs(math.cos(h))*self.config.collision_half_width+abs(math.sin(h))*self.config.collision_half_length
            passed.append(abs(x-center)+extent <= GATE_HALF_WIDTH)
        self.snapshot = replace(self.snapshot, passed=tuple(passed))
        if distance >= event.distance:
            if event.kind == 'slalom':
                count = sum(passed)
                if count < 3:
                    return self.stop(f'通过{count}/5门；先放慢车速，争取通过3门。')
                stars = 3 if count == 5 and elapsed <= event.gold else 2 if count == 5 else 1
            else:
                stars = 3 if elapsed <= event.gold else 2 if elapsed <= event.silver else 1
            return self.stop('完成赛事。', stars=stars)
        return self.snapshot

    def stop(self, reason, *, stars=0):
        if not self.snapshot.finished:
            self.snapshot = replace(self.snapshot, finished=True, succeeded=stars > 0, stars=stars, reason=reason)
        return self.snapshot
