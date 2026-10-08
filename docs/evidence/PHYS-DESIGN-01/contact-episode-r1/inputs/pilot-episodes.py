"""以毫米级车身侧接触和无初始穿透的护栏入射验证原事故计数。"""
import json
import sys
from pathlib import Path
from panda3d.core import Vec3
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'src'))
from simulation import Simulation,Control
sim=Simulation(track='endless',traffic_count=1);counts=[];distances=[]
try:
    for _ in range(120):sim.step(Control())
    assert sim.snapshot().collisions==0
    for _ in range(5):
        pose=sim.player._chassis.getTransform();hpr=pose.getHpr()
        width=sim.player.config.collision_half_width+sim.npcs[0].config.collision_half_width
        position=pose.getPos()+pose.getQuat().getRight()*(width-.001)
        sim.npcs[0].reset(tuple(position),hpr.x,hpr.y)
        before=[c.getManifoldPoint().getDistance() for c in sim._world.contactTestPair(sim.player._chassis,sim.npcs[0]._chassis).getContacts()]
        distances.append(before)
        sim.step(Control());counts.append(sim.snapshot().collisions)
    assert sim.snapshot().collisions==1
    sim.npcs[0].reset((0,200,.55));sim.reset_player((0,8,.55))
    for _ in range(121):sim.step(Control())
    x=8-.12-sim.config.collision_half_width-.05
    sim.reset_player((x,20,.55));sim.player._chassis.setLinearVelocity(Vec3(6,0,0))
    for _ in range(30):sim.step(Control())
    assert sim.snapshot().collisions==2
    report={'side_pair_initial_distances':distances,'side_counts':counts,'rail_start_x':x,'final_collisions':sim.snapshot().collisions}
    (Path(__file__).resolve().parent/'episode-pilot.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
finally:sim.close()
