"""真实会话接入固定原生交通，完成步与独立进程按同一规则返回。"""

import time
from dataclasses import replace

import pytest

from driving_modes import DrivingMode
from overtake_observations import GapIncident, TrafficReading
from overtake_routes import OVERTAKE_ROUTES
from overtake_run import body
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
        # 非空事件夹具只验证传输字段；不伪称本次物理发生违规。
        observed = replace(result, traffic_reading=TrafficReading((0, 0), 'front', -2., 12., 10., .72, True),
                           incident=GapIncident((0, 0), 'front', -2., 9., .01, .1, True))
        packet = replace(output, highway=replace(output.highway, overtake=observed))
        assert _decode_frame(_encode_frame(packet)).highway.overtake == observed
        session.pause()
        before = session.current
        session.frame(1.)
        assert session.current == before and session.phase == Phase.PAUSED
        session.resume()
        session.reset_player()
        assert session.phase == Phase.RESULTS and '复位' in session.highway.snapshot.overtake.reason
        session.start(countdown=False, settle_initial=True)
        assert len(session.current.traffic) == 12 and session.highway.snapshot.overtake.passes == 0
        session.tick()
        if mode == GameMode.HILL_TRAFFIC:
            assert session.highway.snapshot.overtake.traffic_reading is not None
        else:
            assert session.highway.snapshot.overtake.traffic_reading is None
            own = body(session.current.player, session.vehicle_config)
            front = [other[1]-own[1]-own[3]-other[3] for car in session.current.traffic
                     if car.active and (other := body(car, session.vehicle_config))[1] > own[1]
                     and abs(other[0]-own[0]) < own[2]+other[2]+1.]
            assert min(front) > 120.
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
        deadline = time.monotonic()+10.
        first_tick = session.current.tick
        while session.current.tick < first_tick+12 and time.monotonic() < deadline:
            session.frame(0.)
            time.sleep(.005)
        session.pause()
        assert session.current.tick >= first_tick+12
        if mode == GameMode.HILL_TRAFFIC:
            assert session.highway.snapshot.overtake.traffic_reading is not None
        else:
            assert session.highway.snapshot.overtake.traffic_reading is None
        assert session.highway.snapshot.overtake.incident is None
        session.resume()
        session.finish()
        assert not session.highway.snapshot.overtake.succeeded and '提前' in session.highway.snapshot.reason
    finally:
        session.close()
