"""独立Bullet接触对核验初始真实轮胎包络与路侧物体的穿透。"""
import json
import sys
from pathlib import Path
from panda3d.core import Vec3,Quat,TransformState
from panda3d.bullet import BulletRigidBodyNode
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'src'))
from simulation import Simulation,forward
from suspension_contacts import cylinder_suspension_rays
folder=Path(__file__).resolve().parent
sim=Simulation(track='coastal')
try:
    index,(prop,z)=next((i,p) for i,p in enumerate(sim.props) if p[0].kind=='checkpoint')
    direction=Vec3(*forward(prop.heading));position=Vec3(prop.x,prop.y,z+.55)-direction*6
    sim.reset_player(tuple(position),prop.heading)
    pose=sim._chassis.getTransform();orientation=pose.getQuat();axis=orientation.getRight()
    q=orientation
    config=sim.config;rows=[]
    for i,hub in enumerate(sim.player.suspension.hubs):
        center=position+orientation.xform(Vec3(*hub))+Vec3(0,0,-sim._vehicle.getWheel(i).getSuspensionRestLength())
        probe=BulletRigidBodyNode('wheel-envelope-probe');probe.addShape(sim.player.suspension.envelope)
        probe.setTransform(TransformState.makePosQuatScale(center,q,Vec3(1)))
        overlaps=[]
        for body in sim._world.getRigidBodies():
            if body==sim._chassis:continue
            hits=sim._world.contactTestPair(probe,body).getContacts()
            distances=[h.getManifoldPoint().getDistance() for h in hits]
            if any(d<0 for d in distances):overlaps.append({'body':body.getName(),'distances':distances})
        rows.append({'wheel':i,'center':tuple(center),'overlaps':overlaps})
    (folder/'wheel-envelope-overlap.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print(json.dumps(rows))
finally:sim.close()
