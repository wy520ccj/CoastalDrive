from panda3d.core import Vec3

from session import Session
from simulation import Control, Simulation


def test_side_impact_is_resolved_by_physics():
    sim = Simulation(track="highway", traffic_count=1)
    try:
        sim.npcs[0].reset((0, 300, 0.55))
        sim.drivers[0].cruise = 0
        sim.reset_player((-4.5, 300, 0.55), -90)
        sim.player.reverse_enabled = False
        for _ in range(240):
            sim.step(Control())
        sim._chassis.setLinearVelocity(Vec3(8, 0, 0))
        collided = False
        peak_lateral_speed = 0
        for _ in range(120):
            sim.step(Control())
            peak_lateral_speed = max(peak_lateral_speed, sim.npcs[0]._chassis.getLinearVelocity().x)
            collided |= (
                sim._world.contactTestPair(sim._chassis, sim.npcs[0]._chassis).getNumContacts() > 0
            )
            assert sim.player.snapshot().position[0] < sim.npcs[0].snapshot().position[0]
        assert collided
        assert peak_lateral_speed > 0.2
    finally:
        sim.close()


def test_blocked_reset_leaves_player_and_race_untouched(monkeypatch):
    session = Session(track="highway")
    try:
        session.start(countdown=False)
        before = session.simulation.snapshot()
        race = session.race.snapshot
        monkeypatch.setattr(session.simulation, "_position_clear", lambda *a, **kw: False)
        session.reset_player()
        assert session.simulation.snapshot().player == before.player
        assert session.race.snapshot == race
        assert session.notice
        assert session.simulation.snapshot().events == ("reset_blocked",)
    finally:
        session.close()
