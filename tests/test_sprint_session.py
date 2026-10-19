"""真实会话的固定路线/无车流/标架与独立进程成绩接口。"""

from dataclasses import replace

import pytest

from driving_modes import DrivingMode
from race import BestTimes, GameMode
from session import Phase, Session
from session_process import SessionProcess, _decode_frame, _encode_frame, _output
from sprint_routes import SPRINT_ROUTES


@pytest.mark.parametrize('mode', SPRINT_ROUTES)
def test_new_run_freezes_route_and_no_traffic_and_uses_road_frame(tmp_path, mode):
    app = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    try:
        with pytest.raises(ValueError):
            app.start(mode=mode, track='coastal')
        app.start(mode=mode, track='endless', countdown=False, settle_initial=True)
        route = SPRINT_ROUTES[mode]
        assert app.seed == route.seed and app.road_shape == route.shape
        assert not app.simulation.npcs and app.simulation.config.tire_substeps == 1
        assert app.highway.snapshot.sprint is not None and app.highway.snapshot.target == route.gates[-1]
        point = app.simulation.road.sample_lateral(350., 0.)
        pose = replace(app.current.player, position=(point.x, point.y, point.z+.5), heading=point.heading)
        local = app.simulation.road.lane_frame(pose)
        assert abs(point.x) > 40. and local.position[0] == pytest.approx(0., abs=1e-8)
        assert local.heading == pytest.approx(0.)
        # 人工构造的只读坐标核对不写回物理；真实推进仍从原出生状态开始。
        before = app.current
        app.tick()
        assert app.current.tick == before.tick+1 and app.highway.snapshot.sprint.seconds == 1/120
        output = _output(app)
        assert _decode_frame(_encode_frame(output)).highway == output.highway
        app.reset_player()
        assert app.phase == Phase.RESULTS and not app.highway.snapshot.sprint.succeeded
        assert '复位' in app.highway.snapshot.sprint.reason
    finally:
        app.close()


def test_independent_process_exposes_same_read_only_score_group_and_stored_route(tmp_path):
    path = tmp_path/'best.json'
    local = Session(track='test', scores=BestTimes(path))
    try:
        variant = local.score_variant()
    finally:
        local.close()
    app = SessionProcess(track='test', driving_mode=DrivingMode.GAME, scores=BestTimes(path))
    try:
        assert app.race.scores.path == path and app.score_variant() == variant
        app.start(mode=GameMode.RIDGE_SPRINT, track='endless', countdown=False, settle_initial=True)
        assert app.road_shape == 'hills' and app.seed == 0 and not app.simulation.traffic_models
        assert app.highway.snapshot.sprint.route_id == GameMode.RIDGE_SPRINT.value
        app.pause()
        before = app.current
        app.frame(1.)
        assert app.current == before and app.phase == Phase.PAUSED
        app.start(mode=GameMode.BEND_SPRINT, track='endless', countdown=False, settle_initial=True)
        assert app.road_shape == 'curve' and app.seed == 17
        app.finish()
        assert not app.highway.snapshot.sprint.succeeded and '提前' in app.highway.snapshot.sprint.reason
        app.menu()
        assert app.score_variant() == variant
    finally:
        app.close()
