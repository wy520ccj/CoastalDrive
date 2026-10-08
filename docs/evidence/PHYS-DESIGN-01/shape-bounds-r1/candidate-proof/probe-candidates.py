"""同一失效射线：原候选筛选与实际有限道路几何独立对照。"""
import json
import math
import sys
from pathlib import Path

from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode
from panda3d.core import BitMask32, Mat4, NodePath, Quat, TransformState, Vec3

root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'src'))
from simulation import Simulation
from suspension_contacts import cylinder_suspension_rays
from suspension_geometry import CylinderSurface

folder=Path(__file__).resolve().parent
record=json.loads((folder/'input-native.json').read_text(encoding='utf-8'))
misses=json.loads((folder/'missing-rays.json').read_text(encoding='utf-8'))
sim=Simulation(record['seed'],track='highway')
pose=record['solver_chassis']
sim.player._chassis.setTransform(TransformState.makePosQuatScale(Vec3(*pose['position']),Quat(*pose['orientation']),Vec3(1)))
rows=[]
try:
    for values in (misses[0],misses[-1]):
        rays=tuple(tuple(tuple(p) for p in ray) for ray in values['rays'])
        axis=tuple(values['axes'][0]); origin=tuple(values['ray_origin'])
        radius,width,shoulder,crown=(values[name] for name in ('radius','width','shoulder','crown'))
        actual,=cylinder_suspension_rays(sim._world,sim.player._chassis,rays,(axis,),radius,width,shoulder,crown,
            envelope=sim.player.suspension.envelope,ray_origin=origin)
        points=tuple(tuple(p[a]+origin[a] for a in range(3)) for ray in rays for p in ray)
        padding=radius+width/2+1e-5
        low=tuple(min(p[a] for p in points)-padding for a in range(3))
        high=tuple(max(p[a] for p in points)+padding for a in range(3))
        probe=BulletRigidBodyNode('suspension-query')
        shape=BulletBoxShape(Vec3(*((b-a)/2 for a,b in zip(low,high)))); shape.setMargin(0.); probe.addShape(shape)
        probe.setTransform(TransformState.makePos(Vec3(*((a+b)/2 for a,b in zip(low,high)))))
        native_bodies=set()
        for contact in sim._world.contactTest(probe).getContacts():
            native_bodies.add(contact.getNode1() if contact.getNode0()==probe else contact.getNode0())
        independent=[]
        for body in sim._world.getRigidBodies():
            if body.getName()!='highway-road': continue
            tree=body.getPythonTag('suspension_mesh')
            inverse=Mat4(); inverse.invertFrom(body.getShapeTransform(0).getMat()*NodePath(body).getNetTransform().getMat())
            frame=tuple(tuple(inverse.getCell(b,a) for b in range(3)) for a in range(3))
            offset=tuple(inverse.getCell(3,a)+sum(frame[a][b]*origin[b] for b in range(3)) for a in range(3))
            start,end=rays[0]
            reach=math.sqrt(sum((end[a]-start[a])**2 for a in range(3)))-radius
            surface=CylinderSurface((),body.getShape(0).getMargin(),frame,offset,radius,reach,width,shoulder,axis,crown=crown,triangles=tree)
            hit=surface.entry(surface.local(start),surface.local(end),axis)
            if hit is not None:
                independent.append({'body':body.getName(),'position':tuple(body.getTransform().getPos()),'hit':hit,
                    'included_by_native_contact_probe':body in native_bodies,'mesh_low':tree.low,'mesh_high':tree.high,
                    'local_start':surface.local(start),'local_end':surface.local(end)})
        rows.append({'query':values,'original_hit':None if actual is None else {'fraction':actual.fraction,'normal':actual.normal},
                     'probe_bodies':[(b.getName(),tuple(b.getTransform().getPos())) for b in native_bodies],
                     'independent_mesh_hits':independent})
finally: sim.close()
(folder/'candidate-proof.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps([{'original_hit':r['original_hit'],'native_candidates':r['probe_bodies'],
                  'independent_hits':[(h['position'],h['hit'][0],h['included_by_native_contact_probe']) for h in r['independent_mesh_hits']]} for r in rows]))
