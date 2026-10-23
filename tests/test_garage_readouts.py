"""购买预览与实际安装后的完整硬件相符，预览本身不写入车辆。"""

import pytest

from career import PART_BY_ID
from career_garage import GARAGE_CARS
from career_tuning import install, is_installed
from tire_tuning import install as install_tires
from tire_tuning import install_brakes
from ui.garage_layout import part_readout
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def reading(config, topic):
    if topic == 'tires':
        return config.lateral_stiffness/1000
    if topic == 'brakes':
        return config.front_brake_share*100
    if topic == 'power':
        return max(rpm*torque/9549.3 for rpm, torque in config.torque_curve)
    return sum(config.suspension_spring_rates)/4000


@pytest.mark.parametrize('design_id', [car.design_id for car in GARAGE_CARS])
@pytest.mark.parametrize('part_id', tuple(PART_BY_ID))
def test_preview_readings_match_actual_installed_file(tmp_path, design_id, part_id):
    part = PART_BY_ID[part_id]
    vehicle = WorkspaceVehicle(design_id, vehicle_design(design_id).config)
    path = tmp_path/'vehicle.json'
    vehicle.save(path)
    payload = path.read_bytes()
    *_, before, after = part_readout(vehicle, part, is_installed(vehicle, part))
    assert path.read_bytes() == payload
    if part.topic == 'tires':
        installed = install_tires(vehicle, part.recipe, path)
    elif part.topic == 'brakes':
        installed = install_brakes(vehicle, part.recipe, path)
    else:
        installed = install(vehicle, part_id, path)
    tolerance = .51 if part.topic == 'power' else .051
    assert float(before) == pytest.approx(reading(vehicle.config, part.topic), abs=tolerance)
    assert float(after) == pytest.approx(reading(installed.config, part.topic), abs=tolerance)
    assert WorkspaceVehicle.load(path) == installed
    *_, current, _ = part_readout(installed, part, True)
    assert float(current) == pytest.approx(reading(installed.config, part.topic), abs=tolerance)
