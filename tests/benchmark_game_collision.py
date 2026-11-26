"""120Hz 游戏实时时钟下的滨海斜撞护栏和连环撞车基准。"""

import json
import logging
import math
from collections import defaultdict
from statistics import median, quantiles
from threading import Event
from time import perf_counter, sleep

from race import GameMode
from session import Session
from simulation import FIXED_DT, Control


class Driver:
    def __init__(self):
        self.request = Event()
        self.consumed_at = None

    def sample(self, state, dt):
        requested = self.request.is_set()
        if requested and self.consumed_at is None:
            self.consumed_at = perf_counter()
        return Control(steering=float(requested) * -.1)


class NumericsLog(logging.Handler):
    def __init__(self):
        super().__init__()
        self.arithmetic_errors = 0

    def emit(self, record):
        if record.exc_info and isinstance(record.exc_info[1], ArithmeticError):
            self.arithmetic_errors += 1


def set_speed(car, speed):
    body = car._chassis
    body.setLinearVelocity(body.getTransform().getQuat().getForward() * speed)
    car.tires.initialize_rolling(speed)


def run(case):
    session = Session(seed=17, track='coastal', independent_clock=True)
    logger = logging.getLogger('simulation')
    old_level = logger.level
    errors = NumericsLog()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(errors)
    try:
        session.start(mode=GameMode.FREE_DRIVE, countdown=False)
        sim = session.simulation
        rail = case == 'rail'
        if rail:
            sim.reset_player((95., 0., .55), -15.)
        else:
            for i, car in enumerate(sim.npcs[:3]):
                point = sim.road.sample_lateral(14. + 6. * i, 0.)
                car.reset((point.x, point.y, point.z + .55), point.heading, point.grade)
            point = sim.road.sample_lateral(0., 0.)
            sim.reset_player((point.x, point.y, point.z + .55), point.heading, point.grade)
        traffic_controls = (Control(brake=1.),) * len(sim.npcs)
        for _ in range(90):
            sim.step(Control(), traffic_controls=traffic_controls)
        set_speed(sim.player, 200. / 3.6)
        session.sync_snapshots()
        start_tick = session.current.tick
        driver = Driver()
        session.set_controller(driver)
        times, impacts = [], defaultdict(list)
        pairs = set()
        stalled, resumed_at = Event(), None
        step = sim.step

        def measured_step(control, dt):
            nonlocal resumed_at
            now = perf_counter()
            step(control, dt, traffic_controls=traffic_controls)
            times.append((perf_counter() - now) * 1000)
            for impact in sim._impact_events:
                impacts[impact.material].append(impact.raw_impulse)
            if not rail and (sim._impact_events or len(times) % 3 == 0):
                for manifold in sim._world.getManifolds():
                    names = tuple(sorted((manifold.getNode0().getName(), manifold.getNode1().getName())))
                    if names[0].startswith(('player-', 'traffic-')) and names[1].startswith('traffic-') and any(
                            point.getAppliedImpulse() > 0 for point in manifold.getManifoldPoints()):
                        pairs.add(names)
            if sim._impact_events and not stalled.is_set():
                stalled.set()
                sleep(.08)
                resumed_at = perf_counter()

        sim.step = measured_step
        session.frame(0.)
        deadline = perf_counter() + 7.
        last_time = completion = None
        backlog_ms = wall_lag_ms = rate = 0.
        submitted_at = visible_at = None
        while perf_counter() < deadline:
            now = perf_counter()
            if stalled.is_set() and submitted_at is None:
                submitted_at = now
                driver.request.set()
            frame = session.frame(0., sampled_at=now)
            assert all(math.isfinite(value) for value in (*frame.player.position, *frame.player.velocity))
            if submitted_at is not None and visible_at is None and abs(frame.player.steering) > .001:
                visible_at = now
            if last_time is not None:
                rate = max(rate, (frame.time - completion) / (now - last_time))
            completion, last_time = frame.time, now
            clock = session._clock
            with clock.output_lock:
                backlog_ms = max(backlog_ms, 1000 * clock.published_backlog)
                if clock.published_dropped:
                    wall_lag_ms = max(wall_lag_ms, 1000 * max(
                        0., now - clock.timeline_origin - (clock.published_dropped - clock.timeline_dropped)
                        - clock.current.time))
                if clock.current.tick >= start_tick + 180:
                    break
            sleep(1. / 120.)
        session.stop_clock()
        target = 'metal_barrier' if rail else 'vehicle'
        assert len(times) >= 180 and impacts[target], (case, len(times), impacts)
        if not rail:
            assert len(pairs) >= 2, pairs
        assert errors.arithmetic_errors == 0
        assert session.stepper.dropped_time >= .045 and session.stepper.remainder < 2 * FIXED_DT
        assert backlog_ms < 1000 * 2 * FIXED_DT and rate <= 1.01, (backlog_ms, rate)
        assert resumed_at is not None and submitted_at is not None and driver.consumed_at is not None and visible_at is not None
        return {
            "case": case, "entry_speed_kmh": 200, "ticks": len(times), "arithmetic_errors": errors.arithmetic_errors,
            "impact_count": len(impacts[target]), "peak_impact_ns": round(max(impacts[target]), 1),
            "vehicle_contact_pairs": sorted(pairs), "tick_median_ms": round(median(times), 3),
            "tick_p95_ms": round(quantiles(times, n=100)[94], 3), "tick_max_ms": round(max(times), 3),
            "max_backlog_ms": round(backlog_ms, 3), "post_reanchor_max_wall_lag_ms": round(wall_lag_ms, 3),
            "dropped_ms": round(session.stepper.dropped_time * 1000, 3),
            "max_presentation_rate": round(rate, 3),
            "input_wait_ms": round((driver.consumed_at - submitted_at) * 1000, 3),
            "input_after_resume_ms": round((driver.consumed_at - resumed_at) * 1000, 3),
            "input_visible_after_resume_ms": round((visible_at - resumed_at) * 1000, 3),
        }
    finally:
        session.close()
        logger.removeHandler(errors)
        logger.setLevel(old_level)


if __name__ == '__main__':
    for scenario in ('rail', 'pileup'):
        print(json.dumps(run(scenario), ensure_ascii=False), flush=True)
