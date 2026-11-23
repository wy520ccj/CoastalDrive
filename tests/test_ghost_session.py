"""权威完成步独立记录；慢窗口与跨进程元数据不丢采样。"""

import time
from dataclasses import replace

import pytest
from route_driver import RouteDriver

from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES
from challenge_run import EnergySplit
from controls import ConstantController
from driving_modes import DrivingMode
from lap_ghost import ghost_context, load_ghost, record_context
from race import BestTimes, GameMode
from session import Phase, Session
from session_process import SessionProcess
from simulation import Control


def test_authority_records_without_window_and_pause_focus_reset_restart_are_consistent(tmp_path):
    session = Session(scores=BestTimes(tmp_path/"scores.json"))
    try:
        session.start(mode=GameMode.TIME_TRIAL, countdown=False)
        start_tick = session.current.tick
        session.set_controller(ConstantController(Control(throttle=.3)))
        for _ in range(120):
            session.tick()
        recorder = session.ghost_recording
        assert recorder.frames == session.current.tick-start_tick+1 == 121
        frozen = session.race.snapshot
        session.focus_changed(False)
        for _ in range(10):
            session.tick()
        assert session.phase == Phase.PAUSED and session.race.snapshot == frozen and recorder.frames == 121
        session.resume()
        session.tick()
        assert recorder.frames == 122
        session.reset_player()
        session.tick()
        assert session.race.snapshot.invalidated and session.ghost_recording is None
        session.start(mode=GameMode.TIME_TRIAL, countdown=False)
        assert session.ghost_recording.frames == 1 and not session.race.snapshot.splits
        session.menu()
        assert session.ghost_recording is None and session.reference_ghost is None
    finally:
        session.close()


@pytest.mark.parametrize("boundary", ["context", "load"])
def test_ghost_file_boundary_failure_does_not_prevent_real_driving(tmp_path, monkeypatch, boundary):
    session = Session(scores=BestTimes(tmp_path/"scores.json"))
    try:
        def fail(*args):
            raise OSError("unreadable file")

        monkeypatch.setattr("session.ghost_context" if boundary == "context" else "session.load_ghost", fail)
        session.start(mode=GameMode.TIME_TRIAL, countdown=False)
        assert session.phase == Phase.DRIVING and session.reference_ghost is None
        assert session.race.snapshot.ghost_notice
        session.tick()
        assert session.current.tick == 1
    finally:
        session.close()


def test_retry_budget_score_can_attach_ghost_from_the_completed_run(tmp_path, monkeypatch):
    mode = GameMode.TIME_TRIAL
    session = Session(scores=BestTimes(tmp_path/'scores.json'))
    try:
        session.start(mode=mode, countdown=False, challenge_spec=ROAD_CHALLENGES[mode], build=BuildDraft())
        session.tick()
        session.tick()
        recorder = session.ghost_recording
        run = session.engineering
        run.trace = None
        seconds, litres = .025, .05
        run.window.litres = litres
        run.splits = tuple(EnergySplit(gate, seconds*gate/run.spec.distance_m, litres*gate/run.spec.distance_m)
                           for gate in run.gates[:-1])+(EnergySplit(run.spec.distance_m, seconds, litres),)

        def fail(document):
            raise OSError('测试只读')

        with monkeypatch.context() as patch:
            patch.setattr(run.scores, '_write', fail)
            run.stop('完成滨海环路', succeeded=True, seconds=seconds)
        session.current = replace(session.current, tick=session.current.tick+1)
        session.race.snapshot = replace(session.race.snapshot, finished=True)
        session.record_ghost_step(ghost_context(session.seed))
        session.phase = Phase.RESULTS
        assert run.score_pending and session.ghost_recording is recorder
        session.retry_challenge_score()
        assert not run.score_pending and session.ghost_recording is None
        best = run.scores.reference
        lap = load_ghost(run.scores, mode, best['run_id'], run.scores.context['physics'], seconds,
                         tuple(split.seconds for split in run.splits))
        assert lap.frames == 4
    finally:
        session.close()


def test_independent_session_saves_full_physics_lap_despite_slow_frame_requests(tmp_path):
    path = tmp_path/"scores.json"
    remote = SessionProcess(track="coastal", driving_mode=DrivingMode.GAME, scores=BestTimes(path))
    try:
        remote.start(mode=GameMode.TIME_TRIAL, countdown=False)
        remote.set_controller(RouteDriver())
        start_tick = remote.current.tick
        remote.frame(0.)
        deadline = time.perf_counter()+100.
        while not remote.race.snapshot.finished and time.perf_counter() < deadline:
            time.sleep(.25)
            remote.frame(0.)
        remote.pause()
        race = remote.race.snapshot
        assert race.finished and not race.invalidated, (remote.phase, race)
        assert not race.save_error and "已保存" in race.ghost_notice
        scores = BestTimes(path)
        # 进程双方使用同一实际源码/SDK；这里重读真实落盘记录，不从窗口12份历史拼接。
        course_id = next(key.removesuffix(":time_trial") for key in scores.times
                         if key.endswith(":time_trial"))
        lap = load_ghost(scores, GameMode.TIME_TRIAL, course_id,
                         record_context(ghost_context(0), GameMode.TIME_TRIAL), race.last_lap, race.splits)
        assert lap.frames == remote.current.tick-start_tick+1 and lap.frames > len(remote.history)*100
        assert lap.pose_at(race.last_lap) is not None
        remote.menu()
        remote.start(mode=GameMode.TIME_TRIAL, countdown=True)
        assert remote.reference_ghost == lap and remote.race.snapshot.start_time is None
        reference = remote.reference_ghost
        remote.pause()
        remote.resume()
        assert remote.reference_ghost is reference
    finally:
        remote.close()
