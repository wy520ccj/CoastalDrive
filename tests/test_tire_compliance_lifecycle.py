"""真实NPC驾驶建立胎体储能，检验重定位、回收与模式重建。"""
import pytest

from driving_modes import DrivingMode
from highway_segments import REBASE_DISTANCE, SEGMENT_LENGTH
from session import Session
from simulation import Control


def elastic_memory(car):
    return tuple(car.tires.deformation), tuple(w.elastic_energy for w in car.snapshot().wheel_dynamics)


def drive_npc(simulation):
    npc = simulation.npcs[0]
    for _ in range(120):
        simulation.step(Control(throttle=.3))
    deformation, energies = elastic_memory(npc)
    assert npc.config.tire_compliance
    assert any(sum(value * value for value in wheel) > 0 for wheel in deformation)
    assert sum(energies) > 0
    assert npc.snapshot().speed > 0
    return npc


@pytest.mark.parametrize("mode", list(DrivingMode))
def test_real_npc_shift_rebase_preserve_elastic_memory_then_reset_and_recycle_clear(mode):
    session = Session(track="endless", driving_mode=mode)
    try:
        session.start(countdown=False)
        simulation = session.simulation
        npc = drive_npc(simulation)
        memory = elastic_memory(npc)
        position = npc.snapshot().position
        npc.shift(100)
        assert elastic_memory(npc) == memory
        assert npc.snapshot().position[1] == pytest.approx(position[1] - 100, abs=1e-3)
        npc.shift(-100)

        # 只把坐标系移至重定位入口；没有改写速度、变形或能量。
        amount = REBASE_DISTANCE + SEGMENT_LENGTH
        for car in [simulation.player, *simulation.npcs]:
            car.shift(-amount)
        world_y = npc.snapshot().position[1] + simulation.origin_y
        memory = elastic_memory(npc)
        simulation._rebase()
        assert simulation.rebases == 1
        assert npc.snapshot().position[1] + simulation.origin_y == pytest.approx(world_y, abs=1e-3)
        assert elastic_memory(npc) == memory

        npc.reset(npc.snapshot().position, speed=10)
        assert elastic_memory(npc) == (((0.0, 0.0, 0.0),) * 4, (0.0,) * 4)
        npc = drive_npc(simulation)
        # 离开回收范围前保留实际驾驶所得储能，调用真正的道路回收入口。
        npc.shift(-5000)
        assert sum(elastic_memory(npc)[1]) > 0
        cycles = simulation.traffic_cycles
        simulation._update_stream()
        assert simulation.traffic_cycles > cycles
        assert "traffic_recycled:0" in simulation._events
        assert elastic_memory(npc) == (((0.0, 0.0, 0.0),) * 4, (0.0,) * 4)
        assert npc.config is simulation.config
    finally:
        session.close()


def test_mode_rebuild_creates_true_compliance_cars_without_previous_elastic_energy():
    session = Session(track="endless")
    try:
        session.start(countdown=False)
        old_world = session.simulation
        old_npc = drive_npc(old_world)
        assert sum(elastic_memory(old_npc)[1]) > 0
        session.menu()
        session.set_driving_mode(DrivingMode.SIMULATION)
        session.start(countdown=False)
        assert old_world.closed
        assert session.simulation is not old_world
        for car in [session.simulation.player, *session.simulation.npcs]:
            assert car is not old_npc
            assert car.config is session.vehicle_config
            assert car.config.tire_compliance
            assert elastic_memory(car) == (((0.0, 0.0, 0.0),) * 4, (0.0,) * 4)
    finally:
        session.close()
