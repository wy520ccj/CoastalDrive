"""新簧上/轮心原生世界的实际路面节点；尚不替换生产Vehicle/Snapshot。"""

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, TransformState, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from suspension import stiffness_matrix
from suspension_contacts import static_support_shapes
from unsprung_body import NativeWheelGuides, SprungBodyFrame, apply_joint_forces
from unsprung_drivetrain import drivetrain_ports, tire_ports
from unsprung_dynamics import assemble_unsprung, partition_vehicle
from unsprung_geometry import read_unsprung_geometry
from unsprung_joint import solve_unsprung_joint
from vehicle_config import wheel_hubs
from vehicle_designs import REFERENCE_DESIGN


def run(output, *, mass=40., substeps=2, speed=5., duration=1.2, bump=True):
    output.mkdir(parents=True,exist_ok=False)
    config,gravity = REFERENCE_DESIGN,np.array((0.,0.,-9.81))
    world = BulletWorld()
    world.setGravity(Vec3(*gravity))
    floor = BulletRigidBodyNode("actual-plane")
    floor.addShape(BulletPlaneShape(Vec3(0,0,1),0))
    floor.setIntoCollideMask(BitMask32.bit(0)|BitMask32.bit(1))
    world.attachRigidBody(floor)
    obstacle = None
    if bump:
        obstacle = BulletRigidBodyNode("actual-left-bump")
        shape = BulletBoxShape(Vec3(.24,.45,.005))
        shape.setMargin(0.)
        obstacle.addShape(shape)
        obstacle.setTransform(TransformState.makePos(Vec3(-config.wheel_track_widths[0]/2,2.5,.005)))
        obstacle.setIntoCollideMask(BitMask32.bit(0)|BitMask32.bit(1))
        world.attachRigidBody(obstacle)
    hubs = np.asarray(wheel_hubs(config))
    centers_local = hubs.copy()
    centers_local[:,2] = config.wheel_radius-config.center_of_mass_height
    rest = .4
    reference_q = centers_local[:,2]-(hubs[:,2]-rest)
    partition = partition_vehicle(config.mass,np.diag(config.body_inertia),(mass,)*4,centers_local)
    frame = SprungBodyFrame.from_partition(partition)
    ks = np.asarray(stiffness_matrix(config.suspension_spring_rates,config.suspension_antiroll_rates))
    q = np.linalg.solve(ks,np.full(4,partition.mass*9.81/4))
    radial,radial_c = np.full(4,200000.),np.full(4,500.)
    delta = (ks@q+mass*9.81)/radial
    z_ref = config.wheel_radius-delta[0]-(hubs[0,2]-rest+q[0])
    body = BulletRigidBodyNode("sprung-new-world")
    body.setIntoCollideMask(BitMask32.bit(1))
    body.setDeactivationEnabled(False)
    body.setLinearDamping(0.)
    body.setAngularDamping(0.)
    frame.install(body,config,TransformState.makePos(Vec3(0.,0.,z_ref)))
    world.attachRigidBody(body)
    body.setLinearVelocity(Vec3(0.,speed,0.))
    guides = NativeWheelGuides(world,body,frame,q-reference_q)
    relative = np.full(4,speed/(config.wheel_radius-delta[0]))
    rotors = np.r_[250.,0.,relative]
    initial_rotation = frame.read(body)[1]
    initial_centers,initial_speeds,initial_displacement,initial_u,_initial_xy = guides.read()
    initial_v = np.r_[tuple(body.getLinearVelocity()),tuple(body.getAngularVelocity()),initial_u,rotors]
    initial_mechanics = assemble_unsprung(partition,initial_rotation,initial_displacement,((0.,0.,1.),)*4,initial_v[:10])
    initial_graph = drivetrain_ports(initial_mechanics,np.tile(initial_rotation[:,0],(4,1)),initial_rotation[:,1],
        initial_rotation[:,1],np.tile(initial_rotation[:,1],(3,1)),0.,config)
    downstream = initial_graph.downstream@initial_v
    deformation,forces = np.zeros((4,2)),np.zeros((4,2))
    dt,rows = 1/(120*substeps),[]
    maxima = {"native_velocity_defect":0.,"native_transverse":0.,"frozen_energy_error":0.,"force_error":0.,
              "native_kinetic_increment_defect":0.,"initial_velocity_incompatibility":0.,"external_body_contacts":0}
    initial = {"config":asdict(config),"mass_per_wheel":mass,"radial_rates":radial.tolist(),"radial_damping":radial_c.tolist(),
               "centers_reference":centers_local.tolist(),"reference_compression":reference_q.tolist(),
               "initial_compression":q.tolist(),"initial_deflection":delta.tolist(),"speed":speed,"dt":dt,
               "initial_velocity":initial_v.tolist(),"wheel_initial_velocity":initial_speeds.tolist(),
               "wheel_initial_positions":initial_centers.tolist(),"downstream_omega":downstream.tolist(),
               "duration":duration,"bump":bump,"body_count":world.getNumRigidBodies(),"constraint_count":world.getNumConstraints(),
               "source_sha256":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   (*sorted((ROOT/"src").glob("unsprung_*.py")),Path(__file__))}}
    (output/"input.json").write_text(json.dumps(initial,ensure_ascii=False,indent=2),encoding="utf-8")
    for tick in range(round(duration/dt)):
        _pos,rotation = frame.read(body)
        centers,speeds,displacement,u,_transverse = guides.read()
        v = np.r_[tuple(body.getLinearVelocity()),tuple(body.getAngularVelocity()),u,rotors]
        mechanical = assemble_unsprung(partition,rotation,displacement,((0.,0.,1.),)*4,v[:10])
        maxima["initial_velocity_incompatibility"] = max(maxima["initial_velocity_incompatibility"],float(np.max(np.abs(speeds-mechanical.wheel_velocities))))
        axes = np.tile(rotation[:,0],(4,1))
        support = static_support_shapes(world,body,BitMask32.bit(0))
        geometry = read_unsprung_geometry(world,body,centers,rotation[:,2],axes,config,static_shapes=support)
        graph = drivetrain_ports(mechanical,axes,rotation[:,1],rotation[:,1],np.tile(rotation[:,1],(3,1)),0.,config)
        contacts = tire_ports(graph,geometry.offsets,geometry.tangents,geometry.laterals,geometry.normals,
                              np.zeros((4,3)),np.zeros(4))
        # 共同预测计入几何惯性；物理提交不重复施加，原生guide/gyro自行实现。
        known = np.r_[mechanical.gravity_forces(gravity)-mechanical.inertial_bias,np.zeros(6)]
        step = solve_unsprung_joint(graph,contacts,v,downstream,displacement+reference_q,geometry.deflection,
            deformation,forces,known,np.zeros(4),radial,radial_c,np.full(4,.7),np.zeros(4),30.,.12,0.,np.zeros(4),
            0.,False,dt,config,wheel_initial_velocity=speeds)
        before_native = (.5*partition.mass*np.dot(v[:3],v[:3])+.5*v[3:6]@mechanical.world_inertia@v[3:6]
                         +.5*mass*np.sum(speeds**2))
        apply_joint_forces(body,guides,graph,contacts,step,30.,.12,downstream,np.zeros(3),dt,config)
        world.doPhysics(dt,0,dt)
        rotors,downstream = step.velocity[10:].copy(),step.downstream_omega.copy()
        deformation = np.array([(w.deformation_x,w.deformation_y) for w in step.wheels])
        forces = step.forces.copy()
        new_pos,new_rotation = frame.read(body)
        new_centers,new_speeds,new_displacement,new_u,new_xy = guides.read()
        native_v = np.r_[tuple(body.getLinearVelocity()),tuple(body.getAngularVelocity()),new_u]
        after_native = (.5*partition.mass*np.dot(native_v[:3],native_v[:3])
                        +.5*native_v[3:6]@(new_rotation@partition.inertia@new_rotation.T)@native_v[3:6]
                        +.5*mass*np.sum(new_speeds**2))
        # 初始实际轮心初速已进入求解，预测增量的基线也必须是实际点质量动能。
        before_prediction = before_native
        after_prediction = .5*step.velocity[:10]@mechanical.mass_matrix@step.velocity[:10]
        energy_defect = after_native-before_native-(after_prediction-before_prediction)
        contact_count = sum(manifold.getNumManifoldPoints() for manifold in world.getManifolds()
                            if body in (manifold.getNode0(),manifold.getNode1())
                            and not any(point in (manifold.getNode0(),manifold.getNode1()) for point in guides.points))
        maxima["native_velocity_defect"] = max(maxima["native_velocity_defect"],float(np.max(np.abs(native_v-step.velocity[:10]))))
        maxima["native_transverse"] = max(maxima["native_transverse"],float(np.max(np.abs(new_xy))))
        maxima["frozen_energy_error"] = max(maxima["frozen_energy_error"],abs(step.energy_error))
        maxima["native_kinetic_increment_defect"] = max(maxima["native_kinetic_increment_defect"],abs(float(energy_defect)))
        maxima["force_error"] = max(maxima["force_error"],step.force_error)
        maxima["external_body_contacts"] = max(maxima["external_body_contacts"],contact_count)
        row = {"time":(tick+1)*dt,"body_z":new_pos[2],"body_vz":native_v[2],"body_az":(native_v[2]-v[2])/dt,
               "body_roll_rate":native_v[4],"native_kinetic_increment_defect":energy_defect,
               "velocity_defect":np.max(np.abs(native_v-step.velocity[:10])),"external_body_contacts":contact_count}
        for i in range(4):
            row.update({f"wheel_z_{i}":new_centers[i,2],f"compression_{i}":new_displacement[i]+reference_q[i],
                        f"wheel_vz_{i}":new_speeds[i,2],f"relative_v_{i}":new_u[i],f"normal_force_{i}":step.normal.normal_force[i],
                        f"radial_{i}":geometry.deflection[i],f"surface_z_{i}":geometry.hits[i].point[2] if geometry.hits[i] is not None else None})
        rows.append(row)
    with (output/"trajectory.csv").open("w",encoding="utf-8",newline="") as stream:
        writer = csv.DictWriter(stream,rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    result = dict(steps=len(rows),duration=duration,substeps=substeps,mass_per_wheel=mass,**maxima,
                  normal_min=min(row[f"normal_force_{i}"] for row in rows for i in range(4)),
                  normal_max=max(row[f"normal_force_{i}"] for row in rows for i in range(4)),
                  peak_body_acceleration=max(abs(row["body_az"]) for row in rows),
                  rms_body_acceleration=float(np.sqrt(np.mean([row["body_az"]**2 for row in rows]))),
                  peak_wheel_relative_speed=max(abs(row[f"relative_v_{i}"]) for row in rows for i in range(4)),
                  final_body_z=rows[-1]["body_z"],initial_body_z=frame.physical_pose(TransformState.makePos(Vec3(0,0,z_ref))).getPos().z,
                  stage="actual Bullet bodies and road; not yet production Vehicle/Snapshot integration or finite-pose gate")
    guides.close()
    world.removeRigidBody(body)
    world.removeRigidBody(floor)
    if obstacle is not None:
        world.removeRigidBody(obstacle)
    result["remaining_bodies"],result["remaining_constraints"] = world.getNumRigidBodies(),world.getNumConstraints()
    (output/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--mass",type=float,default=40.)
    parser.add_argument("--substeps",type=int,default=2)
    parser.add_argument("--speed",type=float,default=5.)
    parser.add_argument("--duration",type=float,default=1.2)
    parser.add_argument("--no-bump",action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.output,mass=args.mass,substeps=args.substeps,speed=args.speed,
                         duration=args.duration,bump=not args.no_bump),ensure_ascii=False,indent=2))
