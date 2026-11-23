"""环路预算的真实短启动与门线规则夹具；位置夹具不代表实际驾驶成绩。"""

import copy
import json
import math
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from challenge_build import PRICE_VERSION, BuildDraft
from challenge_calibration import checked_sample, replay_circuit, replay_fuel
from challenge_catalog import ROAD_CHALLENGES, course_gates
from challenge_trace import TRACE_COLUMNS
from controls import ConstantController
from fuel import FUEL_MODEL_VERSION, FUEL_STEP_COLUMNS, FuelMeter
from powertrain import engine_torque
from race import BestTimes, GameMode, RaceTracker
from session import Phase, Session
from session_process import _decode_frame, _encode_frame, _output
from tracks import COASTAL_CIRCUIT
from vehicle_designs import GR86_DESIGN
from vehicle_state import Control


def circuit_document():
    """只测试门线位置复算；以合成路径代替物理驾驶必须明确标记。"""
    circuit = COASTAL_CIRCUIT
    race = RaceTracker(GameMode.TIME_TRIAL, record_scores=False)
    race.begin()
    first = circuit.point_at(0.)
    speed = circuit.length*120/1000
    frames = [(first.x, first.y, first.z+.42, speed)]
    rows = [(0, 0., 0.)]
    for index in range(1, 1002):
        point = circuit.point_at(circuit.length*index/1000)
        frame = (point.x, point.y, point.z+.42, speed)
        race.update(SimpleNamespace(player=SimpleNamespace(position=frame[:3], speed=speed)), 1/120)
        frames.append(frame)
        rows.append((index, index/120, race.distance))
        if race.snapshot.finished:
            break
    assert race.snapshot.finished and not race.snapshot.invalidated
    return {'fixture': 'synthetic-geometry-only', 'circuit_frames': frames, 'samples': rows,
            'splits': [{'seconds': seconds} for seconds in race.snapshot.splits]}, race.snapshot


def test_circuit_geometry_replay_requires_complete_ordered_lap_and_original_positions():
    document, lap = circuit_document()
    assert replay_circuit(document) == lap.elapsed
    truncated = copy.deepcopy(document)
    truncated['circuit_frames'].pop()
    truncated['samples'].pop()
    with pytest.raises(ValueError, match='全部门线'):
        replay_circuit(truncated)
    changed = copy.deepcopy(document)
    changed['circuit_frames'][400] = (10000., 10000., 0., 0.)
    with pytest.raises(ValueError, match='进度|门线'):
        replay_circuit(changed)


def test_circuit_calibration_recomputes_end_time_and_fuel_from_v3_raw_fixture():
    # 位置与主动功为显式合成夹具；不保存为游戏成绩或称作真人样本。
    document, lap = circuit_document()
    spec, build = ROAD_CHALLENGES[GameMode.TIME_TRIAL], BuildDraft()
    config = spec.configuration(build)
    meter = FuelMeter(config.idle_rpm, config.engine_redline_rpm)
    meter.litres = .1
    omega = 3000*math.tau/60
    step = (10., omega, omega, engine_torque(3000, config), 1/120, True)
    rows = [[0, 0., 0., .1, 0., 3000., 1, 0., 0., 0., 0., 0., 1]]
    groups = [[]]
    for tick, seconds, progress in document['samples'][1:]:
        meter.accept(*step[:5], coupled=True)
        fuel = meter.snapshot()
        rows.append([tick, seconds, progress, fuel.litres, fuel.rate_lph, 3000., 1, 10., .5, 0., .5, 0., 1])
        groups.append([step])
    before, after = rows[-2:]
    fraction = (lap.elapsed-before[1])/(after[1]-before[1])
    litres = before[3]+(after[3]-before[3])*fraction-.1
    result = spec.evaluate(build, lap.elapsed, litres)
    document.update(version=3, physics_hz=120, controller='keyboard', price_version=PRICE_VERSION,
        fuel_version=FUEL_MODEL_VERSION, source_start={'fixture': 'synthetic-test-only'},
        source_end={'fixture': 'synthetic-test-only'}, input_group='test-fixture', initial_tick=0,
        spec=json.loads(json.dumps(asdict(spec))), build=asdict(build), start_litres=.1,
        columns=TRACE_COLUMNS, fuel_step_columns=FUEL_STEP_COLUMNS, samples=rows, fuel_steps=groups,
        result=asdict(result))
    checked = checked_sample(spec, document)
    assert checked['seconds'] == lap.elapsed
    assert checked['consumption'] == pytest.approx(litres*100_000/spec.distance_m)
    document['result']['litres'] += .001
    with pytest.raises(ValueError, match='复算'):
        checked_sample(spec, document)


def test_actual_circuit_budget_start_fuel_pause_trace_wire_and_restore(tmp_path):
    scores = BestTimes(tmp_path/'legacy.json')
    scores.record(GameMode.TIME_TRIAL, 80.)
    old_file = scores.path.read_bytes()
    spec = ROAD_CHALLENGES[GameMode.TIME_TRIAL]
    session = Session(track='test', scores=scores, vehicle_config=GR86_DESIGN)
    original = session.vehicle_config, session.base_vehicle_config
    try:
        session.start(mode=GameMode.TIME_TRIAL, track='coastal', challenge_spec=spec,
                      build=BuildDraft(power=1.1), countdown=False)
        assert session.engineering.gates == course_gates(GameMode.TIME_TRIAL)
        assert len(session.engineering.gates) == 5
        assert session.race.snapshot.reference_lap is None and session.reference_ghost is None
        assert not session.race.record_scores and session.ghost_recording.frames == 1
        session.set_controller(ConstantController(Control(throttle=.4)))
        assert session.ghost_recording is None
        for _ in range(120):
            session.tick()
        status = session.highway.snapshot.engineering
        assert status.seconds == pytest.approx(1.) and status.litres > 0
        assert status.progress_m == pytest.approx(max(0., session.race.distance))
        assert len(session.engineering.trace.circuit_frames) == 121
        session.pause()
        for _ in range(3):
            session.tick()
        assert session.highway.snapshot.engineering == status
        assert _decode_frame(_encode_frame(_output(session))).highway.engineering == status
        session.resume()
        session.finish()
        finished = session.highway.snapshot.engineering
        assert session.phase == Phase.RESULTS and not finished.result.valid
        document = json.loads(session.engineering.trace.path.read_text(encoding='utf-8'))
        assert document['version'] == 3 and document['controller'] != 'keyboard'
        assert len(document['circuit_frames']) == len(document['samples'])
        fuel = replay_fuel(spec, document)
        assert fuel.litres-document['start_litres'] == pytest.approx(finished.litres)
        assert scores.path.read_bytes() == old_file
        session.start(mode=GameMode.TIME_TRIAL, track='coastal', countdown=False)
        assert session.challenge_build == BuildDraft(power=1.1)
        assert session.highway.snapshot.engineering.litres == 0
        session.menu()
        assert (session.vehicle_config, session.base_vehicle_config) == original
    finally:
        session.close()


def test_circuit_budget_rejects_wrong_track_before_replacing_player_car(tmp_path):
    session = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    before = session.vehicle_config
    try:
        with pytest.raises(ValueError, match='路线不一致'):
            session.start(mode=GameMode.TIME_TRIAL, track='endless',
                          challenge_spec=ROAD_CHALLENGES[GameMode.TIME_TRIAL])
        assert session.vehicle_config == before and session.phase == Phase.MENU
    finally:
        session.close()
