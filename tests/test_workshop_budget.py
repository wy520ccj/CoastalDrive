"""连续参数参考A/B使用真实记录，旧receipt与新报价分开核对。"""

import copy
from dataclasses import replace

import pytest

from challenge_build import BuildDraft
from lab_experiment import LabExperiment
from lab_records import LabRecord
from vehicle_schemes import checked_challenge, compare_schemes, save_scheme
from vehicle_workspace import WorkspaceVehicle
from workshop_budget import REFERENCE_CHALLENGES, evaluate


@pytest.fixture(scope='module')
def measured():
    pairs = []
    for topic, build in ((0, BuildDraft(brake_share=.7)),
                         (1, BuildDraft(front_tire=1.3, antiroll_share=8/30))):
        spec = REFERENCE_CHALLENGES[topic]
        records = []
        for config in (spec.base_config, spec.configuration(build)):
            run = LabExperiment(spec.options, config=config)
            try:
                while not run.done:
                    run.step()
                records.append(LabRecord.from_run(run))
            finally:
                run.close()
        pairs.append((build, *records))
    return pairs


@pytest.mark.parametrize('topic', [0, 1])
def test_reference_ab_uses_common_quote_and_real_config_without_charging_free_setup(topic, measured):
    build, baseline, candidate = measured[topic]
    spec = REFERENCE_CHALLENGES[topic]
    result = evaluate(topic, baseline, candidate, build)
    assert result['cost'] == build.cost
    assert result['budget'] == spec.budget
    assert result['improvement_pct'] > 0
    assert checked_challenge(result, baseline, candidate) == result
    if topic == 0:
        assert result['passed'] and result['medal'] == '金' and result['cost'] == 0


def test_new_reference_receipt_keeps_full_vehicle_and_reload_rechecks_quote(measured, tmp_path):
    build, baseline, candidate = measured[0]
    spec = REFERENCE_CHALLENGES[0]
    receipt = evaluate(0, baseline, candidate, build)
    vehicle = WorkspaceVehicle('reference-rwd', spec.configuration(build), workshop_result=receipt)
    path = tmp_path/'vehicle.json'
    vehicle.save(path)
    assert WorkspaceVehicle.load(path) == vehicle
    wrong = copy.deepcopy(receipt)
    wrong['cost'] = 1
    with pytest.raises(ValueError):
        replace(vehicle, workshop_result=wrong).save(path)
    assert WorkspaceVehicle.load(path) == vehicle


def test_actual_hardware_mismatches_and_changed_ab_source_cannot_be_summarized_as_success(measured):
    build, baseline, candidate = measured[0]
    with pytest.raises(ValueError, match='完整硬件'):
        evaluate(0, baseline, candidate, BuildDraft(brake_share=.6))
    metadata = copy.deepcopy(candidate.metadata)
    metadata['source_end'] = {}
    with pytest.raises(ValueError):
        evaluate(0, baseline, replace(candidate, metadata=metadata), build)


@pytest.mark.parametrize('topic', [0, 1])
def test_new_reference_scheme_keeps_raw_records_and_comparison_uses_common_money_units(topic, measured, tmp_path):
    build, baseline, candidate = measured[topic]
    receipt = evaluate(topic, baseline, candidate, build)
    saved = save_scheme(tmp_path/'schemes', '预算方案', candidate, baseline, receipt)
    a, b, restored = saved.records()
    assert checked_challenge(restored, a, b) == receipt
    comparison = compare_schemes(saved, saved)
    assert comparison['comparable']
    assert comparison['rows'][-1] == ('改装费', build.cost, build.cost, '')
