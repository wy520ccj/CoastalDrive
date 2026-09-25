"""Visible, wall-clock endurance run for the endless highway."""

import argparse
import ctypes
import json
import os
import statistics
import sys
import time
from ctypes import wintypes
from pathlib import Path

from panda3d.core import Filename

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from application import CoastalDrive
from highway_driver import HighwayDriver
from race import GameMode
from simulation import Control


def working_set_bytes():
    """Return this process' working set without requiring psutil."""
    if os.name != "nt":
        return None
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("page_fault_count", ctypes.c_ulong),
                    ("peak_ws", ctypes.c_size_t), ("ws", ctypes.c_size_t),
                    ("quota_peak_paged", ctypes.c_size_t), ("quota_paged", ctypes.c_size_t),
                    ("quota_peak_nonpaged", ctypes.c_size_t), ("quota_nonpaged", ctypes.c_size_t),
                    ("pagefile", ctypes.c_size_t), ("peak_pagefile", ctypes.c_size_t)]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    process = ctypes.windll.kernel32.GetCurrentProcess()
    api = ctypes.windll.psapi.GetProcessMemoryInfo
    api.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    api.restype = wintypes.BOOL
    ok = api(process, ctypes.byref(counters), counters.cb)
    if not ok:
        raise ctypes.WinError()
    return int(counters.ws)


class EnduranceDriver:
    """A normal Control-producing driver adapted from the traffic driver."""

    def __init__(self, simulation, seed):
        self.simulation = simulation
        self.driver = HighwayDriver(1, seed)
        self.last_origin = simulation.origin_y
        self.reset_pending = True
        self.cached_control = Control()

    @property
    def lane_changes(self):
        return self.driver.lane_changes

    def sample(self, state, dt):
        simulation = self.simulation
        if simulation.origin_y != self.last_origin:
            if not simulation.road.curve:
                self.driver.start_y -= simulation.origin_y - self.last_origin
            self.last_origin = simulation.origin_y
        player = state.player
        if state.tick % 6:
            return self.cached_control
        if self.reset_pending or "player_reset" in state.events:
            _, lateral = simulation.road.locate(player)
            self.driver.lane = min(
                range(len(simulation.road.lanes)),
                key=lambda lane: abs(simulation.road.lanes[lane] - lateral),
            )
            self.driver.target_lane = self.driver.lane
            self.driver.start_y = simulation.road.locate(player)[0]
            self.driver.cancel()
            self.reset_pending = False

        traffic = [car for car in state.traffic if car.active]
        locations = [simulation.road.locate(player)] + [simulation.road.locate(car) for car in traffic]
        reservations = [
            (npc_driver.target_lane, simulation.road.locate(car)[0], car.speed)
            for npc_driver, car in zip(simulation.drivers, state.traffic)
            if car.active and isinstance(npc_driver, HighwayDriver)
            and npc_driver.phase in ("signal", "changing")
        ]
        self.driver.plan(player, traffic, simulation.road, reservations)
        self.cached_control = self.driver.control(player, traffic, simulation.road, locations)
        return self.cached_control


def count_render_nodes(app):
    return app.scene.render.findAllMatches("**").getNumPaths()


def count_bodies(app):
    world = app.session.simulation._world
    return int(world.getNumRigidBodies())


def window_minimized(app):
    get_properties = getattr(app.win, "getProperties", None)
    if get_properties is None:
        return False
    return bool(get_properties().getMinimized())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=1800.0)
    parser.add_argument("--output", type=Path, default=Path("logs/h4b/endurance-061"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--offscreen", action="store_true", help="Use an offscreen smoke window")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    jsonl_path = args.output / "samples.jsonl"
    if jsonl_path.exists():
        parser.error("Choose a new output directory; existing run evidence is preserved")
    summary_path = args.output / "summary.json"
    started = None
    frame_times = []
    samples = []
    next_sample = 0.0
    next_screenshot = 300.0
    interrupted = False
    completed = False
    failures = set()
    error = None
    warmup_dropped = None
    app = None
    driver = None
    last_frame = time.perf_counter()

    def write_sample(sample):
        samples.append(sample)
        with jsonl_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(sample, ensure_ascii=False) + "\n")

    def monitor(task):
        nonlocal next_sample, next_screenshot, completed, last_frame, warmup_dropped
        now = time.perf_counter()
        previous_frame = last_frame
        last_frame = now
        wall = now - started
        if wall >= 30.0:
            frame_times.append(now - previous_frame)
        else:
            warmup_dropped = app.session.stepper.dropped_time
        state = app.session.current
        if window_minimized(app):
            failures.add("window_minimized")
        if app.session.phase.value != "driving":
            failures.add("driving_interrupted")
        if abs(state.player.position[0]) > 6.9 or not 0.25 < state.player.position[2] < 0.8:
            failures.add("player_off_road")
        if wall >= next_sample:
            state = app.session.current
            position = state.origin_y + state.player.position[1]
            write_sample({
                "wall_time": wall,
                "simulation_time": state.time,
                "mileage_m": position - 8.0,
                "speed_mps": state.player.speed,
                "segments": len(app.scene.segment_nodes),
                "bodies": count_bodies(app),
                "render_nodes": count_render_nodes(app),
                "tasks": len(app.taskMgr.getAllTasks()),
                "events": len(app.getAllAccepting()),
                "collision_steps": app.session.simulation.collision_count,
                "lane_changes": driver.lane_changes,
                "rebases": app.session.simulation.rebases,
                "traffic_cycles": app.session.simulation.traffic_cycles,
                "active_traffic": sum(c.active for c in state.traffic),
                "dropped_time": app.session.stepper.dropped_time,
                "working_set_bytes": working_set_bytes(),
                "phase": app.session.phase.value,
                "minimized": window_minimized(app),
            })
            next_sample = wall + 1.0
        if wall >= next_screenshot:
            app.graphicsEngine.renderFrame()
            screenshot = args.output / f"frame-{int(next_screenshot):05d}.png"
            app.win.saveScreenshot(Filename.fromOsSpecific(str(screenshot)))
            next_screenshot += 300.0
        if wall >= args.seconds:
            completed = True
            app.userExit()
            return task.done
        return task.cont

    try:
        app = CoastalDrive(
            smoke=True, onscreen=not args.offscreen, output=args.output,
            seed=args.seed, track="endless",
        )
        app.taskMgr.remove("finish-smoke")
        # smoke mode's windowEvent already suppresses focus pause; keep that fact explicit in evidence.
        app.session.start(mode=GameMode.FREE_DRIVE, track="endless", countdown=False)
        driver = EnduranceDriver(app.session.simulation, args.seed + 701)
        app.session.set_controller(driver)
        app.taskMgr.add(monitor, "endurance-monitor", sort=50)
        started = last_frame = time.perf_counter()
        app.run()
    except Exception as exc:
        error = repr(exc)
        raise
    finally:
        interrupted = not completed
        ended = time.perf_counter()
        measured_wall = ended - started if started is not None else 0.0
        state = app.session.current if app is not None else None
        final_mileage = (state.origin_y + state.player.position[1] - 8.0) if state else 0.0
        post_warmup_dropped = (
            app.session.stepper.dropped_time - (warmup_dropped or 0.0)
            if app is not None else None
        )
        qualified = bool(
            completed and error is None and not args.offscreen and state is not None
            and not failures
            and state.time >= max(0.0, measured_wall - 30.0) * 0.95
            and final_mileage >= max(10.0, state.time * 5.0)
            and len(state.traffic) >= 1 and len(app.scene.segment_nodes) >= 3
            and (post_warmup_dropped or 0.0) <= 1e-9 and measured_wall >= 1800.0
        )
        summary = {
            "status": "completed" if completed and error is None else "interrupted" if error is None else "error",
            "completed": completed,
            "acceptance_passed": qualified,
            "qualified_30min": qualified,
            "requested_seconds": args.seconds,
            "wall_seconds": measured_wall,
            "simulation_seconds": state.time if state else 0.0,
            "frames_after_warmup": len(frame_times),
            "frame_time_mean": statistics.fmean(frame_times) if frame_times else None,
            "frame_time_p95": sorted(frame_times)[int(len(frame_times) * 0.95)] if frame_times else None,
            "focus_pause_suppressed_by_harness": True,
            "real_rendering": not args.offscreen,
            "interrupted": interrupted,
            "error": error,
            "samples": len(samples),
            "final_mileage_m": final_mileage,
            "post_warmup_dropped_time": post_warmup_dropped,
            "failures": sorted(failures),
            "collision_steps": app.session.simulation.collision_count if app else None,
            "review_required": "Inspect memory trend, frame times, collisions and screenshots before H4B acceptance",
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if app is not None:
            app.close_game()


if __name__ == "__main__":
    main()
