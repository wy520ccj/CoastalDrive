"""从无初始穿透的行车道沿直线撞向原检查点，保留原速度/时长/碰撞断言。"""
import json
import sys
from pathlib import Path
from panda3d.core import Vec3,TransformState
from panda3d.bullet import BulletRigidBodyNode
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'src'))
from simulation import Simulation,Control,forward
from coastal_map import nearest_point,offset_point,ROAD_WIDTH
from vehicle_state import heading_for
folder=Path(__file__).resolve().parent
sim=Simulation(track='coastal')
try:
    index,(prop,z)=next((i,p) for i,p in enumerate(sim.props) if p[0].kind=='checkpoint')
    target=next(b for b in sim._world.getRigidBodies() if b.getName()==f'checkpoint-{index}')
    old=Vec3(prop.x,prop.y,z+.55)-Vec3(*forward(prop.heading))*6
    center,distance=nearest_point(old.x,old.y)
    fraction=(ROAD_WIDTH/2-sim.config.collision_half_width-.05)/distance
    position=Vec3(center.x+(old.x-center.x)*fraction,center.y+(old.y-center.y)*fraction,center.z+.60)
    heading=heading_for(prop.x-position.x,prop.y-position.y);direction=Vec3(*forward(heading))
    sim.reset_player(tuple(position),heading)
    initial=[]
    for i,hub in enumerate(sim.player.suspension.hubs):
        center_world=position+sim._chassis.getTransform().getQuat().xform(Vec3(*hub))+Vec3(0,0,-sim._vehicle.getWheel(i).getSuspensionRestLength())
        probe=BulletRigidBodyNode('wheel-envelope-probe');probe.addShape(sim.player.suspension.envelope)
        probe.setTransform(TransformState.makePosQuatScale(center_world,sim._chassis.getTransform().getQuat(),Vec3(1)))
        distances=[hit.getManifoldPoint().getDistance() for body in sim._world.getRigidBodies() if body!=sim._chassis
                   for hit in sim._world.contactTestPair(probe,body).getContacts()]
        assert all(d>=0 for d in distances),distances
        initial.append(distances)
    for _ in range(120):sim.step(Control())
    sim._chassis.setLinearVelocity(direction*15)
    sim.player.tires.initialize_rolling(sim._chassis.getLinearVelocity().dot(sim._chassis.getTransform().getQuat().getForward()))
    collided=False;first=None
    for i in range(150):
        sim.step(Control());hit=sim._world.contactTestPair(sim._chassis,target).getNumContacts()>0
        collided|=hit
        if hit and first is None:first=i
    assert collided and abs(sim.snapshot().player.speed)<10
    report={'position':tuple(position),'heading':heading,'initial_tire_pair_distances':initial,'first_contact_after_launch_tick':first,'final_speed':sim.snapshot().player.speed,'full_120_settle_150_collision_steps_completed':True}
    (folder/'approach-pilot.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
finally:sim.close()
