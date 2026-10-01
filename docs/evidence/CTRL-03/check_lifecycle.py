"""真实NPC介入后核对重定位与回收；边界触发夹具不作为运动轨迹证据。"""

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from panda3d.core import Vec3
from driving_modes import DrivingMode
from session import Session

session = Session(track="endless", driving_mode=DrivingMode.SIMULATION)
try:
    session.start(countdown=False)
    for _ in range(240):
        session.tick()
    sim = session.simulation
    car = sim.npcs[0]
    assert all(w.sample_support for w in car.tires.states)
    car._chassis.setLinearVelocity(Vec3(0, 20, 0))
    car._chassis.setAngularVelocity(Vec3(0, 0, .5))
    car.tires.initialize_rolling(20)
    session.tick()
    active = car.stability.state
    assert active.active
    car.shift(-2000)
    assert car.stability.state == active
    cycles = sim.traffic_cycles
    sim._update_stream()
    assert sim.traffic_cycles > cycles
    assert not car.stability.state.active and car.stability.state.feedback_tick == 0
    assert car.stability.state.reference_yaw_rate == 0
    assert car.brakes.states[0].pressure == 0
    assert car.config is sim.config and car.stability.vehicle_config is car.config
    session.menu()
    old = sim
    session.set_driving_mode(DrivingMode.GAME)
    session.start(countdown=False)
    assert old.closed
    assert not session.current.player.stability_state.active
    assert session.current.player.stability_state.feedback_tick == 0
    assert all(not npc.stability.state.active and npc.stability.state.feedback_tick == 0
               for npc in session.simulation.npcs)
    report = {"passed": True, "npc_active_state": asdict(active),
              "traffic_cycles_before": cycles, "traffic_cycles_after": sim.traffic_cycles,
              "events": sim._events, "mode_rebuild_closed_previous_world": old.closed,
              "protocol": "Real NPC wheel/body feedback activates ESC. Vehicle.shift(-2000) preserves memory and triggers actual stream recycling; this relocation is a lifecycle fixture, not a trajectory or traffic recovery performance claim.",
              "source_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (ROOT / "src").rglob("*.py")}}
    (Path(__file__).parent / "lifecycle.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Actual NPC ESC, origin shift, recycling and mode rebuild passed")
finally:
    session.close()
