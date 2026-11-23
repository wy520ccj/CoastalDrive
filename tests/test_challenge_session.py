"""样板真实道路的临时原车、起止计量、返回恢复与进程回包。"""

import time
from dataclasses import replace

import pytest

from challenge_build import BuildDraft
from challenge_catalog import SPRINT_CHALLENGES
from controls import ConstantController
from driving_modes import DrivingMode
from race import BestTimes, GameMode
from session import Phase, Session
from session_process import SessionProcess, _decode_frame, _encode_frame, _output
from vehicle_designs import GR86_DESIGN
from vehicle_state import Control


class SteadyDriver:
    def sample(self, state, dt):
        return Control(throttle=.4)


@pytest.mark.parametrize('mode', tuple(SPRINT_CHALLENGES))
def test_real_route_temporary_build_pause_retry_and_restore(tmp_path, mode):
    path = tmp_path/'best.json'
    session = Session(track='test', scores=BestTimes(path), vehicle_config=GR86_DESIGN)
    original = session.base_vehicle_config, session.vehicle_config
    spec, build = SPRINT_CHALLENGES[mode], BuildDraft(power=1.1, front_tire=1.15)
    try:
        session.start(mode=mode, track='endless', countdown=False, challenge_spec=spec, build=build)
        assert session.simulation.config == spec.configuration(build)
        assert session.highway.snapshot.engineering.cost == 3000
        session.set_controller(SteadyDriver())
        for _ in range(32):
            session.tick()
        state = session.highway.snapshot.engineering
        assert state.seconds > 0 and state.litres > 0
        assert state.consumption is None  # 前50米保留真实累计值，不显示起步放大值。
        session.pause()
        for _ in range(3):
            session.tick()
        assert session.highway.snapshot.engineering == state
        restored = _decode_frame(_encode_frame(_output(session)))
        assert restored.highway.engineering == state
        session.resume()
        session.finish()
        assert not session.highway.snapshot.engineering.result.official
        assert not path.with_name('sprint-best.json').exists()
        assert not path.with_name('challenge-best.json').exists()
        session.start(mode=mode, track='endless', countdown=False)
        assert session.challenge_build == build
        assert session.highway.snapshot.engineering.litres == 0.
        session.menu()
        assert (session.base_vehicle_config, session.vehicle_config) == original
        assert session.challenge_spec is session.engineering is None
    finally:
        session.close()


def test_wrong_route_or_runtime_hardware_is_rejected_before_replacing_original(tmp_path):
    session = Session(track='test', scores=BestTimes(tmp_path/'best.json'), vehicle_config=GR86_DESIGN)
    old = session.vehicle_config
    spec = SPRINT_CHALLENGES[GameMode.BEND_SPRINT]
    try:
        with pytest.raises(ValueError, match='路线不一致'):
            session.start(mode=GameMode.RIDGE_SPRINT, track='endless', challenge_spec=spec)
        with pytest.raises(ValueError, match='机械细分'):
            session.start(mode=GameMode.BEND_SPRINT, track='endless',
                          challenge_spec=replace(spec, base_config=replace(spec.base_config, tire_substeps=2)))
        assert session.vehicle_config == old and session.phase == Phase.MENU
    finally:
        session.close()


def test_reset_ends_current_attempt_without_reusing_old_fuel_or_awarding(tmp_path):
    mode = GameMode.BEND_SPRINT
    session = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    try:
        session.start(mode=mode, track='endless', countdown=False,
                      challenge_spec=SPRINT_CHALLENGES[mode])
        session.set_controller(SteadyDriver())
        for _ in range(16):
            session.tick()
        before = session.highway.snapshot.engineering.litres
        session.reset_player()
        result = session.highway.snapshot.engineering.result
        assert result is not None and not result.valid and result.litres == before
    finally:
        session.close()


def test_independent_authority_transmits_same_budget_build_and_fuel_then_restores(tmp_path):
    remote = SessionProcess(track='test', driving_mode=DrivingMode.GAME,
                            scores=BestTimes(tmp_path/'best.json'), vehicle_config=GR86_DESIGN)
    original = remote.vehicle_config
    mode, build = GameMode.BEND_SPRINT, BuildDraft(power=1.1)
    try:
        remote.start(mode=mode, track='endless', countdown=False,
                     challenge_spec=SPRINT_CHALLENGES[mode], build=build)
        remote.set_controller(ConstantController(Control(throttle=.3)))
        deadline = time.monotonic()+10
        while remote.frame(0).tick < 12 and time.monotonic() < deadline:
            time.sleep(.005)
        remote.pause()
        state = remote.highway.snapshot.engineering
        assert state.cost == 2250 and state.litres > 0.
        assert remote.vehicle_config == SPRINT_CHALLENGES[mode].configuration(build)
        remote.finish()
        assert not remote.highway.snapshot.engineering.result.official
        remote.menu()
        assert remote.vehicle_config == original
    finally:
        remote.close()
