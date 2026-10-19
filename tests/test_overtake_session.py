"""真实会话接入固定原生交通，完成步与独立进程按同一规则返回。"""

import pytest

from driving_modes import DrivingMode
from overtake_routes import OVERTAKE_ROUTES
from race import BestTimes, GameMode
from session import Phase, Session
from session_process import SessionProcess, _decode_frame, _encode_frame, _output


@pytest.mark.parametrize('mode', OVERTAKE_ROUTES)
def test_fixed_traffic_course_and_reset_and_existing_free_density(tmp_path, mode):
    route = OVERTAKE_ROUTES[mode]
    session = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    try:
        with pytest.raises(ValueError):
            session.start(mode=mode, track='coastal')
        session.traffic_density, session.road_shape = 'busy', 'hills'
        session.start(mode=mode, track='endless', countdown=False, settle_initial=True)
        assert session.seed == route.seed and session.road_shape == route.shape
        assert len(session.current.traffic) == 12 and session.simulation.traffic_span == 540
        assert session.traffic_density == 'busy' and session.simulation.config.tire_substeps == 1
        assert session.highway.snapshot.overtake is not None and session.highway.snapshot.challenge
        session.tick()
        result = session.highway.snapshot.overtake
        assert result.seconds == 1/120 and result.passes == 0
        output = _output(session)
        assert _decode_frame(_encode_frame(output)).highway == output.highway
        session.pause()
        before = session.current
        session.frame(1.)
        assert session.current == before and session.phase == Phase.PAUSED
        session.resume()
        session.reset_player()
        assert session.phase == Phase.RESULTS and '复位' in session.highway.snapshot.overtake.reason
        session.start(countdown=False, settle_initial=True)
        assert len(session.current.traffic) == 12 and session.highway.snapshot.overtake.passes == 0
        session.finish()
        assert '提前' in session.highway.snapshot.reason
        session.start(mode=GameMode.FREE_DRIVE, countdown=False)
        assert len(session.current.traffic) == 18 and session.highway.snapshot.overtake is None
    finally:
        session.close()


@pytest.mark.parametrize('mode', OVERTAKE_ROUTES)
def test_process_returns_fixed_course_and_quit_state(tmp_path, mode):
    route = OVERTAKE_ROUTES[mode]
    session = SessionProcess(track='test', driving_mode=DrivingMode.GAME, scores=BestTimes(tmp_path/'best.json'))
    try:
        session.traffic_density, session.road_shape = 'light', 'hills'
        session.start(mode=mode, track='endless', countdown=False, settle_initial=True)
        assert session.seed == route.seed and session.road_shape == route.shape
        assert len(session.current.traffic) == 12 and session.highway.snapshot.overtake.passes == 0
        session.finish()
        assert not session.highway.snapshot.overtake.succeeded and '提前' in session.highway.snapshot.reason
    finally:
        session.close()
