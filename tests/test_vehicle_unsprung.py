"""正式Simulation链中的真实轮心、执行器、快照、生命周期与工程文件边界。"""

from dataclasses import asdict, replace

import numpy as np
import pytest
from physics_packet_kernels import encode

from lab_experiment import LabExperiment, LabOptions
from lab_records import LabRecord, export_record, load_record, recalculate
from simulation import Simulation
from snapshot_wire import _pre_unsprung_layout, decode_snapshots, encode_snapshots
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document, grouped_parameters
from vehicle_state import VehicleCommand

NEW = replace(REFERENCE_DESIGN,unsprung_enabled=True)


def test_engineering_boundary_keeps_legacy_off_and_rejects_invalid_new_hardware():
    values = asdict(NEW)
    for key in ("unsprung_enabled","unsprung_masses","tire_radial_stiffness","tire_radial_damping"):
        del values[key]
    assert not config_from_document(values,NEW).unsprung_enabled
    document = {"schema":"vehicle-engineering-v1","parameters":grouped_parameters(NEW)}
    assert config_from_document(document,REFERENCE_DESIGN)==NEW
    for change in ({"unsprung_masses":(400.,)*4},{"tire_radial_stiffness":(0.,)*4},
                   {"tire_radial_damping":(-1.,)*4},{"body_inertia":None},{"angular_damping":.1},
                   {"input_shaft_enabled":False}):
        with pytest.raises(ValueError):
            replace(NEW,**change)


def test_unique_simulation_owns_five_vehicle_bodies_and_reads_actual_positions():
    simulation = Simulation(track="lab",traffic_count=0,config=NEW)
    world = simulation._world
    try:
        assert world.getNumRigidBodies()==6 and world.getNumConstraints()==4
        car = simulation.player
        assert car._chassis.getMass()==1040.
        for _ in range(16):
            simulation.step(VehicleCommand(gear=0,clutch=0.))
        state = simulation.snapshot().player
        assert state.unsprung_state is not None and state.suspension_state is None
        assert state.unsprung_state.force_tick==state.contact_tick==16
        for wheel,point,observed in zip(state.wheels,car._wheel_guides.points,state.unsprung_state.wheel_positions):
            assert wheel.position==observed==tuple(point.getTransform().getPos())
        mass = state.unsprung_state
        expected = (1040.*np.array(mass.sprung_position)+40.*np.array(mass.wheel_positions).sum(axis=0))/1200.
        assert mass.total_center_position==pytest.approx(expected,abs=1e-12)
        snapshot = simulation.snapshot()
        assert decode_snapshots(encode_snapshots((snapshot,)))[0]==snapshot
        legacy = decode_snapshots(encode(_pre_unsprung_layout,(snapshot,)))[0]
        assert legacy.player.unsprung_state is None
        assert legacy.player.wheel_dynamics==snapshot.player.wheel_dynamics
        # 正式重定位只平移坐标；位移、相对速度与储能保持，轮心不重建积分状态。
        before = car.snapshot().unsprung_state
        car.shift(10.)
        after = car.snapshot().unsprung_state
        assert np.array(after.wheel_positions)==pytest.approx(np.array(before.wheel_positions)-(0.,10.,0.),abs=1e-6)
        assert after.displacement==pytest.approx(before.displacement,abs=1e-6)
        assert after.relative_velocity==pytest.approx(before.relative_velocity,abs=1e-8)
        for contact,wheel in zip(car._wheel_contacts,after.wheel_positions):
            if contact.contact_point is not None:
                assert contact.contact_point[1]==pytest.approx(wheel[1],abs=1e-6)
        car.detach_physics()
        assert world.getNumRigidBodies()==1 and world.getNumConstraints()==0
        car.attach_physics()
        assert world.getNumRigidBodies()==6 and world.getNumConstraints()==4
        car.reset((95.,0.,.6),heading=15.,speed=3.)
        assert world.getNumRigidBodies()==6 and world.getNumConstraints()==4
        assert car.snapshot().heading==pytest.approx(15.,abs=2e-6)
        assert car.snapshot().speed==pytest.approx(3.,abs=2e-6)
    finally:
        simulation.close()
    assert world.getNumRigidBodies()==1 and world.getNumConstraints()==0


def test_real_lab_initialize_command_record_and_recalculate_preserve_full_new_state(tmp_path):
    run = LabExperiment(LabOptions(maneuver="step_steer",speed_kph=30.,duration=.12,onset=0.,steering_deg=2.),config=NEW)
    try:
        initial = run.current.player
        assert initial.unsprung_state.normal_force==pytest.approx((2943.,)*4,abs=.2)
        assert initial.unsprung_state.radial_deflection==pytest.approx((2943/200000.,)*4,abs=1e-6)
        assert initial.speed==pytest.approx(30/3.6,abs=2e-6)
        assert max(abs(w.kappa) for w in initial.wheel_dynamics)<1e-6
        while not run.done:
            run.step()
        assert run.reason=="time_limit" and run.error is None
        assert max(w.force_residual for w in run.current.player.wheel_dynamics)<1e-5
        assert any(abs(w.aligning_moment)>1. for w in run.current.player.wheel_dynamics)
        original = LabRecord.from_run(run)
        export_record(original,tmp_path/"new-world")
        restored = load_record(tmp_path/"new-world")
        assert restored.snapshots==original.snapshots
        repeated = recalculate(restored)
        assert repeated.snapshots==restored.snapshots
        assert repeated.samples==restored.samples
        assert repeated.commands==restored.commands
    finally:
        run.close()
