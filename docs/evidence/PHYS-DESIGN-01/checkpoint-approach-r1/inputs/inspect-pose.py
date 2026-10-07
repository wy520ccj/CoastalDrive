import json
import sys
from pathlib import Path
from panda3d.core import Vec3,BitMask32
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'src'))
from simulation import Simulation,forward
from coastal_map import road_height,nearest_point
folder=Path(__file__).resolve().parent
sim=Simulation(track='coastal')
try:
    index,(prop,z)=next((i,p) for i,p in enumerate(sim.props) if p[0].kind=='checkpoint')
    direction=Vec3(*forward(prop.heading));position=Vec3(prop.x,prop.y,z+.55)-direction*6
    sim.reset_player(tuple(position),prop.heading)
    contacts=[]
    for hit in sim._world.contactTest(sim._chassis).getContacts():
        contacts.append({'a':hit.getNode0().getName(),'b':hit.getNode1().getName(),
                         'distance':hit.getManifoldPoint().getDistance()})
    rays=sim._world.rayTestAll(Vec3(position.x,position.y,position.z+5),Vec3(position.x,position.y,position.z-5),BitMask32.bit(0))
    hits=[{'name':h.getNode().getName(),'position':tuple(h.getHitPos()),'normal':tuple(h.getHitNormal())} for h in rays.getHits() if h.getNode()!=sim._chassis]
    report={'position':tuple(position),'prop_z':z,'analytic_road_height':road_height(position.x,position.y),
            'nearest_point':str(nearest_point(position.x,position.y)),'contacts':contacts,'vertical_hits':hits}
    (folder/'initial-pose-facts.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
finally:sim.close()
