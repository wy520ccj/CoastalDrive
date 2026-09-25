"""只保存 Bullet 实际接触事实，并把离散冲击与持续接触分开。"""

import math
from dataclasses import dataclass
from itertools import count

_epochs = count(1)


def new_contact_epoch():
    return next(_epochs)


@dataclass(frozen=True)
class ImpactDetectionConfig:
    """6B-02 初始记录参数；须由人工驾驶数据继续校准。"""

    impulse_noise: float = 8.0
    normal_enter: float = 0.65
    normal_exit: float = 0.2
    excess_enter: float = 18.0
    excess_exit: float = 7.0
    baseline_seconds: float = 0.08
    release_ticks: int = 2


@dataclass(frozen=True)
class ImpactEvent:
    epoch: int
    tick: int
    index: int
    sources: tuple[int, ...]
    material: str
    raw_impulse: float
    excess_impulse: float
    normal_speed: float
    tangential_speed: float
    local_position: tuple[float, float, float]
    local_normal: tuple[float, float, float]
    zone: str
    contact_age_ticks: int

    @property
    def event_id(self):
        return f"{self.epoch}:{self.tick}:{self.index}"


@dataclass(frozen=True)
class ContactState:
    sources: tuple[int, ...]
    material: str
    tick: int
    raw_impulse: float
    normal_speed: float
    tangential_speed: float
    local_position: tuple[float, float, float]
    local_normal: tuple[float, float, float]
    zone: str
    contact_age_ticks: int


@dataclass(frozen=True)
class ContactSample:
    """聚合前的单个求解接触点。"""

    sources: tuple[int, ...]
    material: str
    barrier_side: str | None
    impulse: float
    distance: float
    lifetime: int
    normal_speed: float
    tangential_speed: float
    local_position: tuple[float, float, float]
    local_normal: tuple[float, float, float]
    zone: str


@dataclass(frozen=True)
class ContactCluster:
    sources: tuple[int, ...]
    material: str
    barrier_side: str | None
    raw_impulse: float
    normal_speed: float
    tangential_speed: float
    local_position: tuple[float, float, float]
    local_normal: tuple[float, float, float]
    zone: str
    point_count: int
    max_lifetime: int
    min_distance: float


def _unit(vector):
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        return (0.0, 0.0, 1.0)
    return tuple(value / length for value in vector)


def _weighted(values, weights):
    total = sum(weights)
    if total <= 1e-12:
        weights = [1.0] * len(values)
        total = len(values)
    return tuple(sum(row[i] * weight for row, weight in zip(values, weights)) / total
                 for i in range(len(values[0])))


NORMAL_COS_45 = math.sqrt(0.5)


def aggregate_contacts(samples, *, normal_cosine=NORMAL_COS_45,
                       barrier_distance=4.1):
    """按物体、材质、护栏逻辑侧和法线簇合并同 tick 接触点。"""
    groups = []
    ordered = sorted(samples, key=lambda p: (p.material, p.barrier_side or "", p.sources,
                                             p.local_position, p.local_normal))
    for sample in ordered:
        match = None
        for group in groups:
            first = group[0]
            if sample.material != first.material or sample.barrier_side != first.barrier_side:
                continue
            if sample.material != "metal_barrier" and sample.sources != first.sources:
                continue
            if sample.material == "metal_barrier" and not set(sample.sources).intersection(first.sources):
                distance = math.dist(sample.local_position, first.local_position)
                if distance > barrier_distance:
                    continue
            if sum(a * b for a, b in zip(sample.local_normal, first.local_normal)) < normal_cosine:
                continue
            match = group
            break
        if match is None:
            groups.append([sample])
        else:
            match.append(sample)
    clusters = []
    for group in groups:
        weights = [max(0.0, point.impulse) for point in group]
        sources = tuple(sorted({source for point in group for source in point.sources}))
        clusters.append(ContactCluster(
            sources=sources,
            material=group[0].material,
            barrier_side=group[0].barrier_side,
            raw_impulse=sum(weights),
            normal_speed=_weighted([(p.normal_speed,) for p in group], weights)[0],
            tangential_speed=_weighted([(p.tangential_speed,) for p in group], weights)[0],
            local_position=_weighted([p.local_position for p in group], weights),
            local_normal=_unit(_weighted([p.local_normal for p in group], weights)),
            zone=group[0].zone,
            point_count=len(group),
            max_lifetime=max(p.lifetime for p in group),
            min_distance=min(p.distance for p in group),
        ))
    return tuple(clusters)


@dataclass
class _Pulse:
    age: int = 0
    baseline: float = 0.0
    ready: bool = True
    quiet_ticks: int = 0
    peak: float = 0.0
    last_tick: int = 0


class ImpactTracker:
    def __init__(self, config=None):
        self.config = config or ImpactDetectionConfig()
        self._states = {}

    @staticmethod
    def key(contact):
        normal = contact.local_normal
        axis = max(range(3), key=lambda index: abs(normal[index]))
        direction = (axis, 1 if normal[axis] >= 0 else -1)
        if contact.material == "metal_barrier" and contact.barrier_side:
            return (contact.material, contact.barrier_side, direction)
        return (contact.material, contact.sources, direction)

    def clear(self):
        self._states.clear()

    def update(self, clusters, tick, epoch, post_motion=None):
        contacts = []
        events = []
        seen = set()
        config = self.config
        alpha = 1.0 - math.exp(-1.0 / (config.baseline_seconds * 120.0))
        for index, contact in enumerate(clusters):
            key = self.key(contact)
            seen.add(key)
            if key not in self._states:
                base = key[:-1]
                previous = [state_key for state_key, state in self._states.items()
                            if state_key[:-1] == base and state.last_tick == tick - 1]
                if len(previous) == 1:
                    self._states[key] = self._states.pop(previous[0])
            state = self._states.setdefault(key, _Pulse(last_tick=tick - 1))
            if tick - state.last_tick > config.release_ticks:
                state = _Pulse(last_tick=tick - 1)
                self._states[key] = state
            state.age = state.age + 1 if state.last_tick == tick - 1 else 1
            state.quiet_ticks = state.quiet_ticks + 1 if (
                contact.normal_speed <= config.normal_exit and
                contact.raw_impulse <= config.impulse_noise + config.excess_exit
            ) else 0
            if state.quiet_ticks >= config.release_ticks:
                state.ready = True
                state.peak = 0.0
            excess = max(0.0, contact.raw_impulse - state.baseline)
            is_new = (
                contact.raw_impulse >= config.impulse_noise and
                contact.normal_speed >= config.normal_enter and
                excess >= config.excess_enter and state.ready
            )
            upgraded = (
                not state.ready and excess >= config.excess_enter and
                excess >= state.peak * 1.6 and contact.normal_speed >= config.normal_enter
            )
            if is_new or upgraded:
                events.append(ImpactEvent(
                    epoch, tick, index, contact.sources, contact.material,
                    contact.raw_impulse, excess, contact.normal_speed,
                    contact.tangential_speed, contact.local_position,
                    contact.local_normal, contact.zone, state.age,
                ))
                state.ready = False
                state.peak = excess
                state.quiet_ticks = 0
            elif not state.ready:
                state.peak = max(state.peak, excess)
            state.baseline += alpha * (contact.raw_impulse - state.baseline)
            state.last_tick = tick
            post_speed, post_tangent = (post_motion or {}).get(key, (
                max(0.0, contact.normal_speed), contact.tangential_speed
            ))
            contacts.append(ContactState(
                contact.sources, contact.material, tick, contact.raw_impulse,
                post_speed, post_tangent,
                contact.local_position, contact.local_normal, contact.zone, state.age,
            ))
        for key, state in tuple(self._states.items()):
            if key not in seen:
                state.quiet_ticks += 1
                state.last_tick = tick
                if state.quiet_ticks >= config.release_ticks:
                    state.ready = True
                    state.peak = 0.0
                if state.quiet_ticks >= config.release_ticks * 2:
                    del self._states[key]
        return tuple(events), tuple(contacts)
