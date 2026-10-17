"""启动工程选择必须同时到达可选外观和唯一Session硬件。"""

import sys
import types

import pytest

from skins import vehicle_for_design
from vehicle_designs import DESIGN_VEHICLES, vehicle_design


@pytest.mark.parametrize("design", DESIGN_VEHICLES)
def test_design_selects_matching_physical_model(design):
    model = vehicle_for_design(design.id, "sports")
    assert vehicle_design(model.physics_id).config is design.config


def test_same_hardware_keeps_selected_sedan():
    assert vehicle_for_design("game-tuned", "sedan").id == "sedan"


def test_unknown_design_is_not_replaced_by_another_car():
    with pytest.raises(ValueError, match="工程设计没有对应"):
        vehicle_for_design("unknown", "sports")


@pytest.mark.parametrize("mode", ("game", "simulation"))
def test_window_entry_passes_explicit_gr86_to_application(monkeypatch, mode):
    import main

    created = []

    class Application:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.next_workspace = None
            self.workspace_vehicle = kwargs["workspace_vehicle"]
            self.next_drive = False

        def run(self):
            pass

        def close_game(self):
            pass

    module = types.ModuleType("application")
    module.CoastalDrive = Application
    monkeypatch.setitem(sys.modules, "application", module)
    monkeypatch.setattr(sys, "argv", ["coastaldrive", "--vehicle-design", "gr86-2022-premium-6mt",
                                    "--driving-mode", mode])
    assert main.main() == 0
    assert created[0]["vehicle_design_id"] == "gr86-2022-premium-6mt"
    assert created[0]["driving_mode"].value == mode


def test_workspace_dispatch_closes_previous_world_before_applying_trial(monkeypatch):
    import main
    from vehicle_workspace import WorkspaceVehicle

    vehicle = WorkspaceVehicle("reference-fwd", vehicle_design("reference-fwd").config)
    events = []

    class Lab:
        def __init__(self, **kwargs):
            assert not events or events[-1] == "game-close"
            self.next_workspace = None if events else "game"
            self.next_drive = self.next_workspace == "game"
            self.workspace_vehicle = vehicle
            events.append("lab-open")

        def run(self):
            pass

        def close_game(self):
            events.append("lab-close")

    class Game:
        def __init__(self, **kwargs):
            assert events[-1] == "lab-close" and kwargs["workspace_vehicle"] is vehicle
            self.workspace_vehicle = vehicle
            self.next_workspace, self.next_drive = "lab", False
            events.append("game-open")

        def start_game(self, *, mode, track):
            assert mode.value == "free_drive" and track == "coastal"
            events.append("test-drive")

        def run(self):
            pass

        def close_game(self):
            events.append("game-close")

    game_module, lab_module = types.ModuleType("application"), types.ModuleType("lab_application")
    game_module.CoastalDrive, lab_module.VehicleLab = Game, Lab
    monkeypatch.setitem(sys.modules, "application", game_module)
    monkeypatch.setitem(sys.modules, "lab_application", lab_module)
    monkeypatch.setattr(WorkspaceVehicle, "load", lambda: None)
    monkeypatch.setattr(sys, "argv", ["coastaldrive", "--lab"])
    assert main.main() == 0
    assert events == ["lab-open", "lab-close", "game-open", "test-drive", "game-close", "lab-open", "lab-close"]
