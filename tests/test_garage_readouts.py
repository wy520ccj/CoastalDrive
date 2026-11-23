"""预算参数的真实单位读数与完整候选硬件相符，预览不写玩家车辆。"""

from dataclasses import replace

import pytest

from career_garage import GARAGE_CARS
from challenge_build import BuildDraft
from challenge_catalog import SPRINT_CHALLENGES
from race import GameMode
from ui.challenge_layout import field_values, read_value
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


@pytest.mark.parametrize('design_id', [car.design_id for car in GARAGE_CARS])
def test_budget_readings_match_candidate_si_parameters_without_mutating_original(tmp_path, design_id):
    vehicle = WorkspaceVehicle(design_id, vehicle_design(design_id).config)
    path = tmp_path/'vehicle.json'
    vehicle.save(path)
    original = path.read_bytes()
    spec = replace(SPRINT_CHALLENGES[GameMode.BEND_SPRINT], base_config=vehicle.config, design_id=design_id)
    draft = BuildDraft(power=1.1, mass=.96, drag=.95, front_tire=1.15, rear_tire=.85,
                        brakes=1.15, springs=1.1, dampers=.9, final_drive=1.05,
                        brake_share=.7, antiroll_share=.4)
    candidate = spec.configuration(draft)
    actual = {'power': draft.power*100, 'mass': candidate.mass,
              'drag': candidate.drag_coefficient*candidate.frontal_area,
              'front_tire': candidate.lateral_stiffness/1000,
              'rear_tire': candidate.rear_lateral_stiffness/1000,
              'brakes': candidate.brake_torque,
              'springs': sum(candidate.suspension_spring_rates)/4000,
              'dampers': 100*candidate.suspension_compression_damping[0]/vehicle.config.suspension_compression_damping[0],
              'final_drive': candidate.final_drive, 'brake_share': candidate.front_brake_share*100,
              'antiroll_share': candidate.suspension_antiroll_rates[0]/sum(candidate.suspension_antiroll_rates)*100}
    for key, expected in actual.items():
        *_, value = field_values(spec, draft, key)
        assert value == pytest.approx(expected)
        assert read_value(spec, draft, key, value) == pytest.approx(draft.value(key))
    assert path.read_bytes() == original and WorkspaceVehicle.load(path) == vehicle
