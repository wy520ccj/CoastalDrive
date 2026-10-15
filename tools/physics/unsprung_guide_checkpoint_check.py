"""以保存的真实位姿/速度作独立初值，核对原生导向框架与单步位置修正。"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from panda3d.bullet import BulletConstraint, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, TransformState, Vec3

from unsprung_body import NativeWheelGuides, SprungBodyFrame, rigid_transform
from vehicle_config import VehicleConfig
from vehicle_unsprung import body_partition


def read(body,frame,guides):
    position,rotation = frame.read(body)
    centers,speeds,_q,_u,xy = guides.read()
    angular = np.asarray(tuple(body.getAngularVelocity()))
    relative = (speeds-np.asarray(tuple(body.getLinearVelocity()))-np.cross(angular,centers-position))@rotation
    return {"position_error":xy.tolist(),"relative_velocity":relative.tolist(),
            "motor_error":[tuple(c.getTranslationalLimitMotor().getCurrentError()) for c in guides.constraints],
            "limits":[[c.getTranslationalLimitMotor().getCurrentLimit(i) for i in range(3)] for c in guides.constraints],
            "frame_positions":[tuple(c.getFrameA().getPos()) for c in guides.constraints],
            "velocity":tuple(body.getLinearVelocity()),"angular":tuple(body.getAngularVelocity())}


def check(input_folder,output):
    output.mkdir(parents=True,exist_ok=False)
    initial = json.loads((input_folder/"peak-input.json").read_text(encoding="utf-8"))["actual_before"]
    config = VehicleConfig(**json.loads((input_folder/"result.json").read_text(encoding="utf-8"))["config"])
    rows = []
    for erp in (None,0.):
        world,body = BulletWorld(),BulletRigidBodyNode("checkpoint-sprung")
        world.setGravity(Vec3(0))
        frame = SprungBodyFrame.from_partition(body_partition(config))
        body.setIntoCollideMask(BitMask32.bit(1));body.setDeactivationEnabled(False)
        frame.install(body,config,TransformState.makeIdentity())
        body.setTransform(rigid_transform(np.asarray(initial["rotation"])@frame.principal_axes,initial["position"]))
        body.setLinearVelocity(Vec3(*initial["velocity"]));body.setAngularVelocity(Vec3(*initial["angular"]))
        world.attachRigidBody(body)
        guides = NativeWheelGuides(world,body,frame)
        try:
            # 这些赋值仅定义独立试验初值，不覆盖正在运行的生产车辆。
            for point,center,speed in zip(guides.points,initial["centers"],initial["wheel_velocity"]):
                point.setTransform(TransformState.makePos(Vec3(*center)))
                point.setLinearVelocity(Vec3(*speed))
            world.doPhysics(0.,0,1/960)
            guides.refresh_frames()
            if erp is not None:
                for constraint in guides.constraints:
                    for axis in (0,1):constraint.setParam(BulletConstraint.CPStopErp,erp,axis)
            before = read(body,frame,guides)
            world.doPhysics(1/960,0,1/960)
            rows.append({"override_erp":erp,"before":before,"after":read(body,frame,guides)})
        finally:
            guides.close();world.removeRigidBody(body)
    (output/"result.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps({"cases":len(rows),"max_transverse_speed":[
        float(np.max(np.abs(np.asarray(r["after"]["relative_velocity"])[:,:2]))) for r in rows]}))


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    check(args.input.resolve(),args.output.resolve())
