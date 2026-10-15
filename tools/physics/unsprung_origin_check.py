"""相同五刚体小运动的平移坐标对照；保持真实导向，不修改生产状态。"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from panda3d.bullet import BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, TransformState, Vec3

from unsprung_body import NativeWheelGuides, SprungBodyFrame
from vehicle_designs import REFERENCE_DESIGN
from vehicle_unsprung import body_partition


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    rows = []
    config = replace(REFERENCE_DESIGN,unsprung_masses=(40.,)*4)
    for x in (95.,0.):
        world,body = BulletWorld(),BulletRigidBodyNode("origin-probe")
        world.setGravity(Vec3(0))
        body.setIntoCollideMask(BitMask32.bit(1));body.setDeactivationEnabled(False)
        frame = SprungBodyFrame.from_partition(body_partition(config))
        frame.install(body,config,TransformState.makePos(Vec3(x,0,1)))
        body.setLinearVelocity(Vec3(-.0036,4.84,-.00176))
        body.setAngularVelocity(Vec3(.0066,-.003456,-.000887))
        world.attachRigidBody(body)
        guides = NativeWheelGuides(world,body,frame)
        trace = []
        try:
            for index in range(192):
                guides.refresh_frames();world.doPhysics(1/960,0,1/960)
                centers,speeds,_q,_u,xy = guides.read()
                position,rotation = frame.read(body)
                relative = (speeds-np.asarray(tuple(body.getLinearVelocity()))
                            -np.cross(tuple(body.getAngularVelocity()),centers-position))@rotation
                trace.append({"step":index+1,"position_error":xy.tolist(),"transverse_velocity":relative[:,:2].tolist()})
            rows.append({"origin_x":x,"duration_s":.2,"substeps":8,"steps":trace,
                "position_error_peak_m":max(np.max(np.abs(r["position_error"])) for r in trace),
                "transverse_velocity_peak_mps":max(np.max(np.abs(r["transverse_velocity"])) for r in trace)})
        finally:
            guides.close();world.removeRigidBody(body)
    (output/"result.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps([{k:v for k,v in r.items() if k!="steps"} for r in rows]))


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output.resolve())
