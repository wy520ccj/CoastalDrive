"""沿规则使用的道路车身包络读数；不改判定、车道或任何控制请求。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrafficReading:
    identity: tuple
    kind: str
    side_m: float
    end_m: float
    closing_kph: float
    seconds_to_limit: float | None
    warning: bool


@dataclass(frozen=True)
class GapIncident:
    identity: tuple
    kind: str
    side_m: float
    end_m: float
    seconds: float
    distance: float
    between_ticks: bool


def nearby(state, own, traffic, side_limit, end_limit):
    """聚焦并行或同路带近车；空读数不表示相邻车道可通行。"""
    readings = []
    for identity, other in traffic.items():
        car = state.traffic[identity[0]]
        if abs(car.heading) > 45 or car.velocity[1] < -.5:
            continue
        dx, dy = other[0]-own[0], other[1]-own[1]
        width, length = own[2]+other[2], own[3]+other[3]
        side, end = abs(dx)-width, abs(dy)-length
        closing = state.player.velocity[1]-car.velocity[1]
        seconds = (end-end_limit)/closing if dy > 0 and end >= end_limit and closing > 1e-6 else None
        if abs(dy) < length+end_limit and width <= abs(dx) < width+5.:
            kind = 'parallel' if end < 0 else 'clear' if dy < 0 else 'approach'
            reading = TrafficReading(identity, kind, side, end, closing*3.6, None, side < side_limit+.5)
            readings.append((0 if reading.warning else 2, side, identity, reading))
        elif dy > 0 and abs(dx) < width+side_limit and end <= 120.:
            reading = TrafficReading(identity, 'front', side, end, closing*3.6, seconds,
                                     end < end_limit or (seconds is not None and seconds <= 2.))
            readings.append((1 if reading.warning else 3, end, identity, reading))
    return min(readings, key=lambda item: item[:3])[3] if readings else None


def gap_incident(identity, previous, current, width, length, side_limit, end_limit,
                 before, now, continuous):
    """只在原扫掠已判失败后，取原禁区开区间内一点解释触发原因。"""
    low, high = 0., 1.
    for a, b, extent in zip(previous, current, (width+side_limit, length+end_limit), strict=True):
        if a != b:
            first, last = sorted(((-extent-a)/(b-a), (extent-a)/(b-a)))
            low, high = max(low, first), min(high, last)
    assert low < high
    between = continuous and previous != current
    fraction = (low+high)/2 if between else 1.
    dx, dy = (a+(b-a)*fraction for a, b in zip(previous, current, strict=True))
    side, end = abs(dx)-width, abs(dy)-length
    kind = 'parallel' if end < 0 else 'front' if dy >= 0 else 'clear'
    return GapIncident(identity, kind, side, end,
        before.seconds+(now.seconds-before.seconds)*fraction,
        before.distance+(now.distance-before.distance)*fraction, between)
