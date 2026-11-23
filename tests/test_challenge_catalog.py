"""实际生涯、车流、长距离道路统一预算接口，不继承当前玩家改装。"""

from dataclasses import replace

import pytest

from challenge_build import BuildDraft
from challenge_catalog import (
    ROAD_CHALLENGES,
    course_gates,
    course_mode,
    course_shape,
    course_track,
    distance_challenge_spec,
)
from controls import ConstantController
from highway_run import TRAFFIC_DENSITIES
from race import BestTimes, GameMode
from session import Session
from sprint_routes import VALLEY_BRAKING_VERSION
from streamed_road import ROAD_EDGE_ADJUSTMENT_AVAILABLE
from vehicle_state import Control


@pytest.mark.parametrize('key', tuple(key for key in ROAD_CHALLENGES if key not in
    (GameMode.BEND_SPRINT, GameMode.RIDGE_SPRINT, GameMode.VALLEY_PACE)))
def test_every_new_road_entry_starts_same_pipeline_restores_and_retries(tmp_path, key):
    spec, mode = ROAD_CHALLENGES[key], course_mode(key)
    app = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    original = app.vehicle_config
    try:
        app.road_shape = course_shape(key)
        draft = BuildDraft(power=1.1) if 'power' in spec.allowed else BuildDraft()
        active_spec = (distance_challenge_spec(app.road_shape, app.traffic_density)
                       if mode == GameMode.DISTANCE_CHALLENGE else spec)
        app.start(mode=mode, track=course_track(key), countdown=False, challenge_spec=spec,
                  build=draft, career_event_id=key if mode == GameMode.CAREER else None)
        assert app.challenge_spec == active_spec and app.vehicle_config == active_spec.configuration(draft)
        assert app.highway.snapshot.engineering.name == spec.name
        if mode in (GameMode.SAFE_OVERTAKE, GameMode.HILL_TRAFFIC):
            assert app.highway.overtake.route.finish_at_end
            assert not app.highway.overtake.record_scores
        app.set_controller(ConstantController(Control(throttle=.3)))
        for _ in range(12):
            app.tick()
        assert app.highway.snapshot.engineering.litres > 0.
        app.finish()
        assert not app.highway.snapshot.engineering.result.official
        app.start(countdown=False)
        assert app.challenge_spec == active_spec and app.highway.snapshot.engineering.litres == 0.
        app.menu()
        assert app.vehicle_config == original
    finally:
        app.close()


def test_catalog_has_fixed_finish_and_explicit_decision_space():
    for key, spec in ROAD_CHALLENGES.items():
        assert course_gates(key)[-1] == spec.distance_m
        assert spec.configuration(BuildDraft()).finite_drivetrain
        assert 'road_friction' not in spec.allowed
        assert not spec.provisional
        if spec.assessment == 'road':
            assert bool(spec.targets) == (key != GameMode.DISTANCE_CHALLENGE)
    targets = {distance_challenge_spec(shape, density).targets for shape in ('straight', 'hills')
               for density in TRAFFIC_DENSITIES}
    assert len(targets) == 6 and all(len(group) == 3 for group in targets)


def test_career_switch_does_not_inherit_prior_event_spec(tmp_path):
    app = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    try:
        app.start(mode=GameMode.CAREER, track='endless', career_event_id='first-drive',
                  challenge_spec=ROAD_CHALLENGES['first-drive'], countdown=False)
        app.start(mode=GameMode.CAREER, track='endless', career_event_id='coast-sprint', countdown=False)
        assert app.challenge_spec is None
        assert app.career_event_id == 'coast-sprint'
    finally:
        app.close()


@pytest.mark.parametrize('mode, shape, legacy, version', (
    (GameMode.BEND_SPRINT, 'budget-bend', 'curve', 'budget-bend-medals-v1'),
    (GameMode.RIDGE_SPRINT,
     'budget-ridge-long-waves' if ROAD_EDGE_ADJUSTMENT_AVAILABLE else 'budget-ridge-suspension',
     'hills', 'budget-route-v5-medals-v1' if ROAD_EDGE_ADJUSTMENT_AVAILABLE else 'budget-route-v4-medals-v1'),
    (GameMode.VALLEY_PACE, 'budget-valley', 'hills', VALLEY_BRAKING_VERSION),
))
def test_budget_uses_new_physical_course_and_preserves_legacy_route(tmp_path, mode, shape, legacy, version):
    spec = ROAD_CHALLENGES[mode]
    app = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    try:
        app.start(mode=mode, track='endless', countdown=False, challenge_spec=spec)
        assert app.road_shape == course_shape(mode) == shape
        assert app.simulation.road.curve.course_id == shape
        assert app.simulation.road.curve.length == spec.distance_m
        assert spec.version == version
        assert app.highway.sprint.route.gates == course_gates(mode)
        app.menu()
        if mode == GameMode.VALLEY_PACE:
            previous = replace(spec, version='budget-route-v2-medals-v1')
            app.start(mode=mode, track='endless', countdown=False, challenge_spec=previous)
            assert app.highway.sprint.route.gates[0] == app.engineering.gates[0] == 250.
            app.menu()
        app.start(mode=mode, track='endless', countdown=False)
        assert app.challenge_spec is None and app.road_shape == legacy
    finally:
        app.close()
