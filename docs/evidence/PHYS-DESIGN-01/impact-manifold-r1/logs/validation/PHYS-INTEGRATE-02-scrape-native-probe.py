"""读取沿栏闭环真实原生点；不改物理或接触分类。"""
import json
import sys
from pathlib import Path
from dataclasses import replace
root = Path.cwd()
sys.path.insert(0, str(root / 'src'))
from panda3d.core import Vec3
from simulation import Simulation
from impact_events import ImpactDetectionConfig
from vehicle_config import CAR
from vehicle_state import VehicleCommand
simulation = Simulation(track='highway', traffic_count=0,
                        config=replace(CAR, finite_drivetrain=False))
rows = []
try:
    simulation.reset_player((6.81, 30, .55))
    simulation.player._chassis.setLinearVelocity(Vec3(2 * ImpactDetectionConfig().normal_enter, 8, 0))
    simulation.player.tires.initialize_rolling(8)
    for tick in range(720):
        simulation.step(VehicleCommand(throttle=.5, steering=2 + simulation.snapshot().player.heading, direction=1))
        snapshot = simulation.snapshot()
        points = []
        for manifold in simulation._world.getManifolds():
            a, b = manifold.getNode0(), manifold.getNode1()
            if ((a == simulation.player._chassis and 'rail' in b.getName())
                or (b == simulation.player._chassis and 'rail' in a.getName())):
                points.extend((p.getDistance(), p.getAppliedImpulse(), p.getLifeTime()) for p in manifold.getManifoldPoints())
        rows.append({'tick': tick+1, 'position': snapshot.player.position,
                     'velocity': tuple(simulation.player._chassis.getLinearVelocity()),
                     'heading': snapshot.player.heading, 'points': points,
                     'contact': any(c.material == 'metal_barrier' for c in snapshot.contacts),
                     'impacts': [e.tick for e in snapshot.impacts]})
finally:
    simulation.close()
path = root/'logs/validation/PHYS-INTEGRATE-02-scrape-native-probe.json'
path.write_text(json.dumps(rows), encoding='utf-8')
gaps = [row for row in rows if not row['contact'] and row['tick'] > 30]
print(json.dumps({'gaps': len(gaps), 'first_gaps': gaps[:8], 'end': rows[-1]}, indent=2))
