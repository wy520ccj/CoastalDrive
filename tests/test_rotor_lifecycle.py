"""真实NPC自旋、平移重定位与回收；模式重建不得继承轴承记账。"""

import math

import pytest

from driving_modes import DrivingMode
from highway_segments import REBASE_DISTANCE, SEGMENT_LENGTH
from session import Session
from simulation import Control


def rotor_state(car):
    return tuple(car.tires.omega), tuple(car.tires.states)


@pytest.mark.parametrize("mode", list(DrivingMode))
def test_player_npc_rotor_rebase_recycle_and_mode_rebuild(mode):
    session = Session(track="endless", road_shape="hills", driving_mode=mode)
    try:
        session.start(countdown=False)
        sim = session.simulation
        assert sim.config.wheel_rotor_transport
        npc = sim.npcs[0]
        active_bearing = False
        for _ in range(120):
            sim.step(Control(throttle=.3))
            active_bearing |= any(math.sqrt(sum(v*v for v in w.gyro_angular_impulse)) > 1e-8
                                  for w in npc.snapshot().wheel_dynamics)
        assert active_bearing
        for car in (sim.player, npc):
            assert car.config is sim.config
            assert all(w.rolling_radius > 0 and math.isfinite(w.steering_work)
                       for w in car.snapshot().wheel_dynamics)
        state = rotor_state(npc)
        suspension = npc.suspension.state
        assert suspension.force_tick == npc.snapshot().contact_tick
        assert suspension.step is not None
        assert all(w.getWheelsSuspensionForce() == 0 for w in npc._vehicle.getWheels())
        npc.shift(100)
        assert rotor_state(npc) == state
        assert npc.suspension.state == suspension
        npc.shift(-100)
        for car in [sim.player, *sim.npcs]:
            car.shift(-(REBASE_DISTANCE + SEGMENT_LENGTH))
        sim._rebase()
        assert sim.rebases == 1 and rotor_state(npc) == state
        npc.shift(-5000)
        cycles = sim.traffic_cycles
        sim._update_stream()
        assert sim.traffic_cycles > cycles
        assert "traffic_recycled:0" in sim._events
        assert all(w.gyro_angular_impulse == (0., 0., 0.) and w.steering_work == 0.
                   for w in npc.snapshot().wheel_dynamics)
        assert npc.suspension.state.step is None
        old_world = sim
        session.menu()
        session.set_driving_mode(DrivingMode.SIMULATION if mode == DrivingMode.GAME else DrivingMode.GAME)
        session.start(countdown=False)
        assert old_world.closed and session.simulation is not old_world
        for car in [session.simulation.player, *session.simulation.npcs]:
            assert car.config.wheel_rotor_transport
            assert car.suspension.state.step is None
            assert all(w.steering_work == 0. and w.gyro_angular_impulse == (0., 0., 0.)
                       for w in car.snapshot().wheel_dynamics)
    finally:
        session.close()
