"""手动调校使用真实硬件、完整副本和原工坊车辆。"""

from dataclasses import replace

import pytest

from garage_setup import candidate, install
from tire_tuning import restore
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def test_setup_applies_real_axles_and_preserves_unedited_model(tmp_path):
    original = WorkspaceVehicle('game-tuned', vehicle_design('game-tuned').config)
    path = tmp_path/'vehicle.json'
    original.save(path)
    changes = {'front_tire': '72', 'rear_tire': '62', 'front_spring': '48', 'rear_bar': '12',
               'brake_share': '67', 'final_drive': '4.1', 'rear_diff': '30', 'rear_cap': '200'}
    updated = install(original, changes, path)
    expected = replace(original.config, lateral_stiffness=72000., rear_lateral_stiffness=62000.,
        suspension_spring_rates=(48000., 48000., *original.config.suspension_spring_rates[2:]),
        suspension_antiroll_rates=(original.config.suspension_antiroll_rates[0], 12000.),
        front_brake_share=.67, final_drive=4.1, differential_damping=(0., 30., 0.), differential_capacity=(0., 200., 0.))
    assert updated.config == expected
    assert WorkspaceVehicle.load(path) == updated
    assert updated.workshop_result is None and updated.report_path is None
    assert restore(updated, path) == original


def test_invalid_numeric_or_write_failure_keeps_original(tmp_path, monkeypatch):
    from pathlib import Path

    original = WorkspaceVehicle('game-tuned', vehicle_design('game-tuned').config)
    path = tmp_path/'vehicle.json'
    original.save(path)
    before = path.read_bytes()
    for change in ({'brake_share': '90'}, {'front_spring': 'nan'}, {'rear_diff': 'word'}):
        with pytest.raises(ValueError):
            install(original, change, path)
        assert path.read_bytes() == before
    assert candidate(original.config, {}) == original.config

    def fail(self, target):
        raise OSError('测试文件不能写入')

    monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises(OSError):
        install(original, {'final_drive': '4'}, path)
    assert path.read_bytes() == before
