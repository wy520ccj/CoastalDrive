"""Highway trip statistics and the five-kilometre clean driving challenge."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class TrafficDensity:
    label: str
    cars: int
    spawn_span: float


TRAFFIC_DENSITIES = {
    "light": TrafficDensity("稀疏", 6, 720),
    "normal": TrafficDensity("普通", 12, 540),
    "busy": TrafficDensity("繁忙", 18, 480),
}


@dataclass(frozen=True)
class HighwayResult:
    challenge: bool = False
    running: bool = False
    finished: bool = False
    succeeded: bool = False
    reason: str = ""
    elapsed: float = 0.0
    distance: float = 0.0
    target: float = 5000.0
    collisions: int = 0


class HighwayRun:
    def __init__(self, *, challenge=False):
        self.snapshot = HighwayResult(challenge=challenge)
        self._start = 0.0

    def start(self, progress, *, challenge=False):
        self._start = progress
        self.snapshot = HighwayResult(challenge=challenge, running=True)

    def update(self, progress, collisions, dt, *, reset=False):
        state = self.snapshot
        if not state.running:
            return
        if reset:
            # Recovery moves the car to a safe spot; it never earns distance.
            self._start = progress - state.distance
        distance = max(state.distance, progress - self._start)
        self.snapshot = replace(
            state, elapsed=state.elapsed + dt, distance=distance, collisions=collisions
        )
        if state.challenge:
            if collisions:
                self.stop("发生碰撞")
            elif reset:
                self.stop("车辆复位")
            elif distance >= state.target:
                self.stop("完成 5 公里无碰撞挑战", succeeded=True)

    def stop(self, reason="驾驶已结束", *, succeeded=False):
        if not self.snapshot.finished:
            self.snapshot = replace(
                self.snapshot, running=False, finished=True, succeeded=succeeded, reason=reason
            )
