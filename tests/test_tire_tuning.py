"""只改变选定前胎，原车副本与当前文件写入边界各自可验证。"""

import json
from dataclasses import asdict, replace

import pytest

from tire_tuning import install, previous_path, restore, vehicle_digest
from vehicle_workspace import WorkspaceVehicle
from workshop_cornering import build_config


def original():
    return WorkspaceVehicle('reference-rwd', build_config(2, False, False),
        parameter_metadata={'basis': '原标定'}, report_path='trial/report.html', scheme_id='a'*32)


@pytest.mark.parametrize('index', [0, 1, 3])
def test_only_front_stiffness_changes_and_complete_original_can_be_restored(tmp_path, index):
    path = tmp_path/'vehicle.json'
    before = original()
    before.save(path)
    old_bytes = path.read_bytes()
    after = install(before, index, path)
    config = asdict(after.config)
    config['lateral_stiffness'] = before.config.lateral_stiffness
    assert config == asdict(before.config)
    assert after.report_path is after.workshop_result is after.scheme_id is None
    assert after.parameter_metadata != before.parameter_metadata
    assert WorkspaceVehicle.load(path) == after
    backup = previous_path(after, path)
    assert backup.name == vehicle_digest(before)+'.json' and backup.read_bytes() == old_bytes
    assert restore(WorkspaceVehicle.load(path), path) == before
    assert path.read_bytes() == old_bytes and backup.read_bytes() == old_bytes


def test_same_recipe_never_writes_or_drops_original_evidence(tmp_path):
    before = original()
    assert install(before, 2, tmp_path/'missing/vehicle.json') is before
    assert not (tmp_path/'missing').exists()


def test_valid_workshop_receipt_is_unlinked_and_can_be_restored_from_original(tmp_path):
    # 合法成绩格式夹具，只验证关联和保存边界，不声称执行了工程试验。
    from workshop import CHALLENGE_ID, build_config, config_digest
    config = build_config(2, False)
    receipt = {'challenge_id': CHALLENGE_ID, 'share_index': 2, 'large_brakes': False, 'cost': 1,
        'baseline_m': 32., 'candidate_m': 28., 'improvement_pct': 12.5, 'peak_yaw_radps': 0.,
        'passed': True, 'medal': '金', 'config_digest': config_digest(config), 'road_validated': True}
    before = replace(original(), config=config, workshop_result=receipt)
    path = tmp_path/'vehicle.json'
    before.save(path)
    after = install(before, 3, path)
    assert after.workshop_result is None and before.workshop_result == receipt
    assert restore(after, path) == before


def test_repeated_install_keeps_immutable_chain_and_restart_can_restore_twice(tmp_path):
    path = tmp_path/'vehicle.json'
    before = original()
    middle = install(before, 0, path)
    middle_backup = previous_path(middle, path)
    saved = middle_backup.read_bytes()
    install(middle, 3, path)
    assert middle_backup.read_bytes() == saved
    assert restore(WorkspaceVehicle.load(path), path) == middle
    assert restore(WorkspaceVehicle.load(path), path) == before


@pytest.mark.parametrize('stage', ['backup', 'current', 'restore'])
def test_write_failure_keeps_current_file_and_input_vehicle(tmp_path, monkeypatch, stage):
    path = tmp_path/'vehicle.json'
    before = original()
    before.save(path)
    if stage == 'restore':
        before = install(before, 3, path)
    old = path.read_bytes()
    save = WorkspaceVehicle.save

    def fail(vehicle, target=None):
        if (stage == 'backup' and target.parent.name == 'tuning-backups') or (stage != 'backup' and target == path):
            raise OSError('模拟只读目录')
        return save(vehicle, target)

    monkeypatch.setattr(WorkspaceVehicle, 'save', fail)
    with pytest.raises(OSError):
        restore(before, path) if stage == 'restore' else install(before, 0, path)
    assert path.read_bytes() == old and WorkspaceVehicle.load(path) == before


@pytest.mark.parametrize('bad', ['../../escape.json', 123, 'x.json'])
def test_backup_reference_cannot_escape_workspace(tmp_path, bad):
    car = replace(original(), parameter_metadata={'tire_tuning_previous': bad})
    with pytest.raises(ValueError, match='编号'):
        restore(car, tmp_path/'vehicle.json')


@pytest.mark.parametrize('bad', ['missing', 'invalid', 'changed', 'other_design'])
def test_bad_backup_never_replaces_current_car(tmp_path, bad):
    path = tmp_path/'vehicle.json'
    after = install(original(), 3, path)
    backup = previous_path(after, path)
    old = path.read_bytes()
    if bad == 'missing':
        backup.unlink()
    elif bad == 'invalid':
        backup.write_text('{', encoding='utf-8')
    else:
        value = json.loads(backup.read_text(encoding='utf-8'))
        if bad == 'changed':
            value['vehicle_config']['mass'] += 1
        else:
            value['design_id'] = 'reference-fwd'
        backup.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises((OSError, ValueError)):
        restore(after, path)
    assert path.read_bytes() == old and WorkspaceVehicle.load(path) == after


def test_corrupt_existing_original_copy_is_not_overwritten(tmp_path):
    path = tmp_path/'vehicle.json'
    before = original()
    after = install(before, 3, path)
    backup = previous_path(after, path)
    backup.write_text('{}', encoding='utf-8')
    old = path.read_bytes()
    with pytest.raises((ValueError, KeyError)):
        install(before, 0, path)
    assert backup.read_text(encoding='utf-8') == '{}' and path.read_bytes() == old
