"""同一原生五刚体的单步动量诊断：连续几何偏置与冻结约束行分别作预测。"""

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
from unsprung_dynamics import assemble_unsprung
from vehicle_designs import REFERENCE_DESIGN
from vehicle_unsprung import body_partition


def step(dt):
    config = replace(REFERENCE_DESIGN,unsprung_masses=(40.,)*4)
    world,body = BulletWorld(),BulletRigidBodyNode("guide-momentum")
    world.setGravity(Vec3(0))
    body.setDeactivationEnabled(False);body.setIntoCollideMask(BitMask32.bit(1))
    frame = SprungBodyFrame.from_partition(body_partition(config))
    frame.install(body,config,TransformState.makePos(Vec3(0,0,1)))
    body.setLinearVelocity(Vec3(.2,3.,.1));body.setAngularVelocity(Vec3(.3,-.4,.2))
    world.attachRigidBody(body)
    guides = NativeWheelGuides(world,body,frame,(.02,-.03,.04,-.01))
    try:
        position,rotation = frame.read(body)
        _centers,_speeds,q,_u,_xy = guides.read()
        initial = np.r_[tuple(body.getLinearVelocity()),tuple(body.getAngularVelocity()),(.1,-.12,0.,.05)]
        mechanics = assemble_unsprung(frame.partition,rotation,q,((0.,0.,1.),)*4,initial)
        for point,speed in zip(guides.points,mechanics.wheel_jacobians@initial):point.setLinearVelocity(Vec3(*speed))
        centers,speeds,q,u,_xy = guides.read()
        initial[6:] = u
        mechanics = assemble_unsprung(frame.partition,rotation,q,((0.,0.,1.),)*4,initial)
        forces = np.array(((12.,-20.,70.),(-8.,15.,40.),(4.,-10.,-30.),(-3.,5.,20.)))
        body_force,body_torque = np.array((10.,-30.,100.)),np.array((1.,2.,-3.))
        generalized = mechanics.wheel_forces(forces)
        generalized[:3] += body_force;generalized[3:6] += body_torque
        momentum = mechanics.mass_matrix@initial+mechanics.wheel_forces(
            mechanics.wheel_masses[:,None]*(speeds-mechanics.wheel_jacobians@initial))
        body_bias = np.zeros(10)
        body_bias[3:6] = np.cross(initial[3:6],mechanics.world_inertia@initial[3:6])
        continuous = np.linalg.solve(mechanics.mass_matrix,momentum+dt*(generalized-mechanics.inertial_bias))
        frozen = np.linalg.solve(mechanics.mass_matrix,momentum+dt*(generalized-body_bias))
        before = {"position":position.tolist(),"centers":centers.tolist(),"velocity":initial.tolist(),
                  "wheel_velocity":speeds.tolist(),"full_bias":mechanics.inertial_bias.tolist()}
        guides.refresh_frames()
        for point,force in zip(guides.points,forces):point.applyCentralImpulse(Vec3(*(dt*force)))
        body.applyCentralImpulse(Vec3(*(dt*body_force)));body.applyTorqueImpulse(Vec3(*(dt*body_torque)))
        world.doPhysics(dt,0,dt)
        _centers,actual_speeds,_q,_u,_xy = guides.read()
        actual_body = np.r_[tuple(body.getLinearVelocity()),tuple(body.getAngularVelocity())]
        return {"dt":dt,"before":before,"body_force":body_force.tolist(),"body_torque":body_torque.tolist(),
                "wheel_forces":forces.tolist(),"actual_body_velocity":actual_body.tolist(),"actual_wheel_velocity":actual_speeds.tolist(),
                "continuous_prediction":continuous.tolist(),"frozen_prediction":frozen.tolist(),
                "continuous_body_error":float(np.max(np.abs(actual_body-continuous[:6]))),
                "frozen_body_error":float(np.max(np.abs(actual_body-frozen[:6]))),
                "continuous_wheel_error":float(np.max(np.abs(actual_speeds-mechanics.wheel_jacobians@continuous))),
                "frozen_wheel_error":float(np.max(np.abs(actual_speeds-mechanics.wheel_jacobians@frozen)))}
    finally:guides.close();world.removeRigidBody(body)


def rotating(dt):
    """自由旋转检查真实约束仍产生向心加速度，不把冻结预测当作关闭惯性机制。"""
    config = replace(REFERENCE_DESIGN,unsprung_masses=(40.,)*4)
    world,body = BulletWorld(),BulletRigidBodyNode("guide-rotation")
    world.setGravity(Vec3(0));body.setIntoCollideMask(BitMask32.bit(1));body.setDeactivationEnabled(False)
    frame = SprungBodyFrame.from_partition(body_partition(config))
    frame.install(body,config,TransformState.makePos(Vec3(0,0,1)))
    body.setAngularVelocity(Vec3(0,0,.5));world.attachRigidBody(body)
    guides = NativeWheelGuides(world,body,frame)
    rows = []
    try:
        for index in range(round(.4/dt)):
            position,rotation = frame.read(body)
            centers,speeds,q,u,_xy = guides.read()
            initial = np.r_[tuple(body.getLinearVelocity()),tuple(body.getAngularVelocity()),u]
            mechanics = assemble_unsprung(frame.partition,rotation,q,((0.,0.,1.),)*4,initial)
            momentum = mechanics.mass_matrix@initial+mechanics.wheel_forces(
                mechanics.wheel_masses[:,None]*(speeds-mechanics.wheel_jacobians@initial))
            body_bias = np.zeros(10);body_bias[3:6]=np.cross(initial[3:6],mechanics.world_inertia@initial[3:6])
            guides.refresh_frames()
            errors = np.asarray([tuple(c.getTranslationalLimitMotor().getCurrentError()) for c in guides.constraints])
            bias = -.2/dt*(errors@rotation.T)
            continuous = np.linalg.solve(mechanics.mass_matrix,momentum-dt*mechanics.inertial_bias)
            matched = np.linalg.solve(mechanics.mass_matrix,momentum-dt*body_bias
                -mechanics.wheel_forces(mechanics.wheel_masses[:,None]*bias))
            world.doPhysics(dt,0,dt)
            _new_centers,new_speeds,_q,_u,_xy = guides.read()
            new_body = np.r_[tuple(body.getLinearVelocity()),tuple(body.getAngularVelocity())]
            arms = centers-position
            radial = new_speeds-speeds-(new_body[:3]-initial[:3])
            radial -= np.cross(new_body[3:6]-initial[3:6],arms)
            radial /= dt
            projection = np.sum(arms[:,:2]*radial[:,:2])/np.sum(arms[:,:2]**2)
            rows.append({"time":(index+1)*dt,"centripetal_rate":float(projection),
                "expected_rate":float(-initial[5]**2),
                "continuous_wheel_error":float(np.max(np.abs(new_speeds-mechanics.wheel_jacobians@continuous))),
                "matched_wheel_error":float(np.max(np.abs(new_speeds-(mechanics.wheel_jacobians@matched+bias)))),
                "matched_body_error":float(np.max(np.abs(new_body-matched[:6]))),
                "guide_bias":bias.tolist()})
        tail = rows[round(.1/dt):]
        return {"dt":dt,"steps":rows,"mean_centripetal_rate":float(np.mean([r["centripetal_rate"] for r in tail])),
                "mean_expected_rate":float(np.mean([r["expected_rate"] for r in tail])),
                "max_matched_wheel_error":max(r["matched_wheel_error"] for r in rows),
                "max_continuous_wheel_error":max(r["continuous_wheel_error"] for r in rows),
                "max_matched_body_error":max(r["matched_body_error"] for r in rows)}
    finally:guides.close();world.removeRigidBody(body)


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    output = parser.parse_args().output.resolve();output.mkdir(parents=True,exist_ok=False)
    rows = [step(1/(120*n)) for n in (2,4,8)]
    rotations = [rotating(1/(120*n)) for n in (2,4,8)]
    (output/"result.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
    (output/"rotation.json").write_text(json.dumps(rotations,indent=2),encoding="utf-8")
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps([{k:v for k,v in row.items() if k.endswith("error") or k=="dt"} for row in rows]))
    print(json.dumps([{k:v for k,v in row.items() if k!="steps"} for row in rotations]))
