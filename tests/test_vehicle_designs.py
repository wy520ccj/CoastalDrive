"""设计布局、菜单重建与同硬件两输入模式的实际物理关联。"""

from dataclasses import asdict, replace

import pytest

from driving_modes import DrivingMode
from session import Phase, Session
from simulation import Simulation
from vehicle_designs import REFERENCE_DESIGN, vehicle_design
from vehicle_state import VehicleCommand


@pytest.mark.parametrize("design_id", ["reference-rwd", "reference-fwd", "reference-awd"])
def test_design_commands_are_identical_between_input_modes(design_id):
    config = vehicle_design(design_id).config
    assert replace(config, front_drive_share=0.) == REFERENCE_DESIGN
    worlds = [Simulation(23, track="test", traffic_count=0, config=config,
                         input_config=mode.input_config) for mode in DrivingMode]
    try:
        peak_speed = 0.
        for tick in range(120):
            command = VehicleCommand(throttle=.4 if tick < 90 else 0,
                                     steering=2 if tick < 60 else -1,
                                     brake=.2 if tick >= 90 else 0, direction=1)
            for world in worlds:
                world.step(command)
            assert asdict(worlds[0].snapshot().player) == asdict(worlds[1].snapshot().player)
            peak_speed = max(peak_speed, worlds[0].snapshot().player.speed)
        # 末段施加制动，起步能力应从真实起步区间读取。
        assert peak_speed > .1
    finally:
        for world in worlds:
            world.close()


def test_menu_selection_preserves_hardware_and_rebuilds_at_start():
    session = Session(track="test", vehicle_config=vehicle_design("game-tuned").config)
    try:
        original = session.simulation
        first_score = session.score_variant()
        session.set_tcs_enabled(False)
        chosen = replace(vehicle_design("reference-fwd").config, mass=1450)
        session.set_vehicle_config(chosen)
        session.set_driving_mode(DrivingMode.SIMULATION)
        assert session.simulation is original and not original.closed
        assert session.base_vehicle_config is chosen
        assert not session.tcs_enabled
        assert replace(session.vehicle_config, traction=chosen.traction) == chosen
        assert session.score_variant() != first_score
        session.start(countdown=False)
        assert original.closed
        assert session.simulation.config is session.vehicle_config
        assert session.simulation.player._chassis.getMass() == pytest.approx(1450)
        assert session.phase == Phase.DRIVING
        with pytest.raises(ValueError, match="主菜单"):
            session.set_vehicle_config(REFERENCE_DESIGN)
        session.menu()
        previous_hardware = session.vehicle_config
        simulation_score = session.score_variant()
        session.set_driving_mode(DrivingMode.GAME)
        assert session.vehicle_config == previous_hardware
        assert session.score_variant() != simulation_score
        session.set_vehicle_config(replace(chosen, mass=1500))
        assert session.score_variant().split(":hardware-")[1] != simulation_score.split(":hardware-")[1]
    finally:
        session.close()
