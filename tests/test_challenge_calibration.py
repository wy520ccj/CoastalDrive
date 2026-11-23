"""门槛候选算法的合成夹具；不代表已有真人试跑或已标定关卡。"""

import copy
import json
import math
import uuid
from dataclasses import asdict, replace

import pytest
from test_challenge_rules import SPEC

from challenge_build import PRICE_VERSION, BuildDraft
from challenge_calibration import candidate_targets, checked_sample
from challenge_trace import TRACE_COLUMNS
from fuel import FUEL_MODEL_VERSION, FUEL_STEP_COLUMNS, FuelMeter
from powertrain import engine_torque


def fixture_document(spec, build=None):
    # 人为构造2拍跨终点，测试复算与拒绝错误；不写入游戏记录目录。
    build = BuildDraft() if build is None else build
    result = spec.evaluate(build, .0125, .07)
    document = {'version': 2, 'run_id': uuid.uuid4().hex, 'physics_hz': 120, 'price_version': PRICE_VERSION,
            'fuel_version': FUEL_MODEL_VERSION, 'controller': 'keyboard',
            'source_start': {'fixture': 'synthetic-test-only'}, 'source_end': {'fixture': 'synthetic-test-only'},
            'input_group': 'test-fixture', 'spec': json.loads(json.dumps(asdict(spec))),
            'columns': TRACE_COLUMNS, 'build': asdict(build), 'initial_tick': 10,
            'start_litres': .1, 'result': asdict(result),
            'samples': [[10, 0., 0., .1, 0., 900., 1, 0., 0., 0., 0., 0., 1],
                        [11, 1/120, 900., .16, 0., 3000., 1, 0., .5, 0., .5, 0., 1],
                        [12, 2/120, 1100., .18, 0., 3000., 1, 0., .5, 0., .5, 0., 1]]}
    config = spec.configuration(build)
    meter = FuelMeter(config.idle_rpm, config.engine_redline_rpm)
    meter.litres = .1
    omega = config.engine_redline_rpm*.5*math.tau/60
    full_torque = engine_torque(config.engine_redline_rpm*.5, config)
    steps = [[]]
    for index, delta in enumerate((.06, .02), 1):
        # 故意夸大的功量仅用于单位测试，不是可达到的车辆轨迹。
        step = (delta*.29*32_000_000., omega, omega, full_torque, 1/120, True)
        meter.accept(*step[:5], coupled=step[-1])
        document['samples'][index][3:5] = [meter.litres, meter.rate_lph]
        document['samples'][index][7] = step[0]
        steps.append([step])
    document.update(fuel_step_columns=FUEL_STEP_COLUMNS, fuel_steps=steps)
    return document


def test_finish_fuel_and_time_are_recalculated_from_raw_crossing():
    doc = fixture_document(SPEC)
    result = checked_sample(SPEC, doc)
    assert result['seconds'] == pytest.approx(.0125)
    assert result['consumption'] == pytest.approx(7.)
    doc['result']['litres'] = .06
    with pytest.raises(ValueError, match='复算'):
        checked_sample(SPEC, doc)


def test_automatic_changed_source_missing_ticks_and_incompatible_rules_are_rejected():
    original = fixture_document(SPEC)
    cases = []
    for key, value in (('controller', 'tools.RoadPilot'), ('source_end', {'changed': True}),
                        ('price_version', 'old'), ('fuel_version', 'old')):
        doc = copy.deepcopy(original)
        doc[key] = value
        cases.append(doc)
    missing = copy.deepcopy(original)
    missing['samples'].pop(1)
    cases.append(missing)
    for doc in cases:
        with pytest.raises(ValueError):
            checked_sample(SPEC, doc)
    with pytest.raises(ValueError, match='目录'):
        checked_sample(replace(SPEC, budget=6500), original)


def test_two_different_repeated_builds_generate_rounded_joint_thresholds_and_no_game_mutation():
    documents = [fixture_document(SPEC) for _ in range(2)]
    documents += [fixture_document(SPEC, BuildDraft(power=1.1)) for _ in range(2)]
    source = documents[0]['source_start']
    targets = candidate_targets(SPEC, documents, source=source)
    assert [(target.medal, target.seconds, target.consumption) for target in targets] == [
        ('铜', .2, 9.5), ('银', .2, 8.2), ('金', .1, 7.3)]
    with pytest.raises(ValueError, match='各两次'):
        candidate_targets(SPEC, documents[:2], source=source)
    with pytest.raises(ValueError, match='不同工程方案'):
        candidate_targets(SPEC, [fixture_document(SPEC) for _ in range(4)], source=source)
    with pytest.raises(ValueError, match='重复提供'):
        candidate_targets(SPEC, [documents[0], documents[0], documents[2], documents[3]], source=source)


def test_matching_old_records_cannot_calibrate_a_new_game_version():
    documents = [fixture_document(SPEC) for _ in range(2)]
    documents += [fixture_document(SPEC, BuildDraft(power=1.1)) for _ in range(2)]
    with pytest.raises(ValueError, match='当前游戏'):
        candidate_targets(SPEC, documents, source={'fixture': 'new-physics-version'})


def test_changing_totals_and_summary_together_cannot_bypass_fuel_substep_recalculation():
    document = fixture_document(SPEC)
    document['samples'][-1][3] += .01
    document['result']['litres'] += .005
    document['result']['consumption'] += .5
    with pytest.raises(ValueError, match='机械子步复算'):
        checked_sample(SPEC, document)


def test_missing_fuel_substep_cannot_hide_consumption_behind_valid_tick_numbers():
    document = fixture_document(SPEC)
    document['fuel_steps'][1] = []
    with pytest.raises(ValueError, match='时长或主动功'):
        checked_sample(SPEC, document)


def test_agent_candidates_require_explicit_origin_and_never_pass_as_human():
    documents = [fixture_document(SPEC) for _ in range(2)]
    documents += [fixture_document(SPEC, BuildDraft(power=1.1)) for _ in range(2)]
    for document in documents:
        document['controller'] = 'tools.VisibleDriver'
        document['result']['official'] = False
        document['result']['medal'] = ''
    source = documents[0]['source_start']
    with pytest.raises(ValueError):
        candidate_targets(SPEC, documents, source=source)
    assert len(candidate_targets(SPEC, documents, source=source, agent=True)) == 3
    mixed = copy.deepcopy(documents)
    mixed[-1]['controller'] = 'tools.AnotherDriver'
    with pytest.raises(ValueError, match='同一驾驶控制器'):
        candidate_targets(SPEC, mixed, source=source, agent=True)
    documents[0]['result']['official'] = True
    with pytest.raises(ValueError, match='驾驶来源'):
        candidate_targets(SPEC, documents, source=source, agent=True)
