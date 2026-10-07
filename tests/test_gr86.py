"""实车型来源锚点、真实几何／静载及共用硬件入口。"""

import json
import math
from dataclasses import asdict

import pytest
from panda3d.core import NodePath
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from powertrain import engine_torque
from session import Session
from skins import vehicle_definition
from vehicle_designs import GR86_DESIGN, GR86_PROFILE_PATH
from vehicle_state import VehicleCommand
from vehicle_visual import load_vehicle


def test_source_fields_and_exact_rating_anchors():
    document = json.loads(GR86_PROFILE_PATH.read_text(encoding="utf-8"))
    metadata = document["metadata"]
    assert set(metadata["vehicle_fields"]) == set(asdict(GR86_DESIGN))
    assert metadata["candidate"]["model_year"] == 2022
    assert metadata["candidate"]["transmission"] == "TL70 six-speed manual"
    assert metadata["vehicle_fields"]["mass"]["status"] == "measured"
    assert metadata["vehicle_fields"]["body_inertia"]["status"] == "engineering_prior"
    assert GR86_DESIGN.gear_ratios == (3.626, 2.189, 1.541, 1.213, 1., .767)
    assert engine_torque(3700., GR86_DESIGN) == pytest.approx(184 * 1.3558179483314)
    power = engine_torque(7000., GR86_DESIGN) * math.tau * 7000 / 60
    assert power == pytest.approx(228 * 745.6998715822702)
    assert not GR86_DESIGN.game_speed_limits


def test_actual_geometry_and_static_axle_loads():
    config = GR86_DESIGN
    world, car = _create_vehicle(config)
    try:
        expected_x = (-.76, .76, -.775, .775)
        assert tuple(w.getChassisConnectionPointCs().x for w in car._vehicle.getWheels()) == pytest.approx(expected_x)
        for _ in range(480):
            _step(world, car, VehicleCommand())
        state = car.snapshot()
        loads = [wheel.normal_load for wheel in state.wheel_contacts]
        assert all(wheel.in_contact for wheel in state.wheel_contacts)
        assert sum(loads) == pytest.approx(config.mass * 9.81, rel=.005)
        assert sum(loads[:2]) / sum(loads) == pytest.approx(.53, abs=.005)
        assert state.position[2] == pytest.approx(.45, abs=.005)
        assert abs(state.pitch) < .1 and abs(state.roll) < .1
    finally:
        car.close()


def test_imported_appearance_preserves_nominal_body_and_actual_axle_tracks():
    parent = NodePath("gr86-geometry")
    body, wheels = load_vehicle(parent, vehicle_definition("gr86-2022"))
    low, high = body.getTightBounds(body)
    assert tuple(high - low) == pytest.approx((2.03, 4.26512, 1.18), abs=2e-6)
    paint_low, paint_high = body.find("**/paint").getTightBounds(body)
    assert paint_high.x - paint_low.x == pytest.approx(1.775, abs=2e-6)
    assert tuple(w.getX() for w in wheels) == pytest.approx((-.76, .76, -.775, .775))
    assert tuple(w.getY() for w in wheels) == pytest.approx((1.21025, 1.21025, -1.36475, -1.36475))
    for wheel in wheels:
        wheel_low, wheel_high = wheel.getTightBounds(wheel)
        assert tuple(wheel_high - wheel_low) == pytest.approx((.215, .6292, .6292), abs=2e-6)


def test_menu_rebuild_and_input_modes_share_real_hardware():
    session = Session(track="test", vehicle_config=GR86_DESIGN)
    try:
        original = session.simulation
        hardware_ids = []
        for mode in DrivingMode:
            session.set_driving_mode(mode)
            assert session.vehicle_config == GR86_DESIGN
            hardware_ids.append(session.score_variant().split(":hardware-")[1])
        assert hardware_ids[0] == hardware_ids[1]
        session.start(countdown=False)
        assert original.closed
        assert session.simulation.config == GR86_DESIGN
        assert session.simulation.player._chassis.getMass() == pytest.approx(1287.29514606)
    finally:
        session.close()
