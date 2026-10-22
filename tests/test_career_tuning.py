"""生涯升级的配置边界、逐次恢复及重复安装；不把配方检查当作驾驶收益。"""

from dataclasses import asdict, replace

import pytest

from career_tuning import DAMPER_GAIN, install, installed_parts
from tire_tuning import install as install_tires
from tire_tuning import install_brakes, previous_path, restore
from vehicle_designs import DESIGN_VEHICLES, REFERENCE_DESIGN
from vehicle_workspace import WorkspaceVehicle


@pytest.mark.parametrize('part_id,fields', [
    ('street-power', {'torque_curve'}),
    ('sport-suspension', {'suspension_spring_rates', 'suspension_compression_damping',
        'suspension_extension_damping', 'suspension_stiffness', 'suspension_compression', 'suspension_relaxation'}),
])
def test_catalog_upgrades_change_only_selected_hardware_and_restore_complete_original(tmp_path, part_id, fields):
    for design in DESIGN_VEHICLES:
        path = tmp_path/design.id/'vehicle.json'
        original = WorkspaceVehicle(design.id, design.config, parameter_metadata={'basis': '已有标定'},
                                    report_path='old/report.json', scheme_id='b'*32)
        original.save(path)
        old = path.read_bytes()
        modified = install(original, part_id, path)
        before, after = asdict(original.config), asdict(modified.config)
        assert {field for field in before if before[field] != after[field]} == fields
        assert modified.report_path is modified.workshop_result is modified.scheme_id is None
        assert WorkspaceVehicle.load(path) == modified and installed_parts(modified) == {part_id}
        backup = previous_path(modified, path)
        assert backup.read_bytes() == old
        assert restore(WorkspaceVehicle.load(path), path) == original and path.read_bytes() == old


def test_mixed_parts_survive_reload_and_reinstall_without_stacking_then_restore_in_order(tmp_path):
    path = tmp_path/'vehicle.json'
    before = WorkspaceVehicle('reference-rwd', REFERENCE_DESIGN)
    power = install(before, 'street-power', path)
    suspension = install(power, 'sport-suspension', path)
    tires = install_tires(suspension, 3, path)
    final = install_brakes(tires, 2, path)
    saved = path.read_bytes()
    for part_id in ('street-power', 'sport-suspension'):
        assert install(WorkspaceVehicle.load(path), part_id, path) == final
        assert path.read_bytes() == saved
    assert installed_parts(final) == {'street-power', 'sport-suspension'}
    assert power.config.torque_curve[-1][1] == pytest.approx(before.config.torque_curve[-1][1]*1.12)
    assert suspension.config.suspension_spring_rates[0] == pytest.approx(before.config.suspension_spring_rates[0]*1.15)
    for expected in (tires, suspension, power, before):
        assert restore(WorkspaceVehicle.load(path), path) == expected


def test_suspension_matches_nonlinear_dampers_and_keeps_installation_geometry(tmp_path):
    curves = (((-.5, -1500.), (-.2, -900.), (-.05, -250.), (0., 0.),
               (.05, 400.), (.2, 1300.), (.5, 2400.)),)*4
    geometry = (((-.1, -.09, -.08), (0., 0., 0.), (.1, .11, .12)),)*4
    config = replace(REFERENCE_DESIGN, unsprung_enabled=True, suspension_coil_enabled=True,
                     suspension_damper_curves=curves, suspension_installation_curves=geometry)
    vehicle = WorkspaceVehicle('reference-rwd', config)
    after = install(vehicle, 'sport-suspension', tmp_path/'vehicle.json')
    assert after.config.suspension_damper_curves[0][-1] == pytest.approx((.5, 2400.*DAMPER_GAIN))
    assert after.config.suspension_damper_curves[0][0] == pytest.approx((-.5, -1500.*DAMPER_GAIN))
    assert after.config.suspension_installation_curves == geometry
    assert after.config.suspension_spring_preloads == config.suspension_spring_preloads


@pytest.mark.parametrize('part_id', ['street-power', 'sport-suspension'])
def test_failed_active_save_keeps_current_bytes_and_can_retry_once(tmp_path, monkeypatch, part_id):
    path = tmp_path/'vehicle.json'
    before = WorkspaceVehicle('reference-rwd', REFERENCE_DESIGN)
    before.save(path)
    payload, save = path.read_bytes(), WorkspaceVehicle.save

    def fail(vehicle, target=None):
        if target == path:
            raise OSError('当前车写入失败')
        save(vehicle, target)

    with monkeypatch.context() as patch:
        patch.setattr(WorkspaceVehicle, 'save', fail)
        with pytest.raises(OSError):
            install(before, part_id, path)
        assert path.read_bytes() == payload and WorkspaceVehicle.load(path) == before
    installed = install(before, part_id, path)
    assert restore(installed, path) == before
