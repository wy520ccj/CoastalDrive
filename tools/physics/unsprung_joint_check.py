"""真实实验台准备输入上的簧下共同求解节点；不冒充生产世界已接入。"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

import tire_drivetrain
from lab_experiment import LabExperiment, LabOptions
from lab_records import model_fingerprint
from unsprung_drivetrain import drivetrain_ports, tire_ports
from unsprung_dynamics import assemble_unsprung, partition_vehicle
from unsprung_joint import solve_unsprung_joint
from vehicle_state import VehicleCommand


def serial(value):
    if isinstance(value,np.ndarray):
        return value.tolist()
    if isinstance(value,np.generic):
        return value.item()
    raise TypeError(f"不能保存的机械输入类型：{type(value).__name__}")


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    original = tire_drivetrain.advance_drivetrain
    captured,ready = [],False

    def capture(*args,**kwargs):
        result = original(*args,**kwargs)
        if ready:
            car = run.experiment.simulation.player
            captured.append((args,kwargs,result,tuple(car._chassis.getLinearVelocity()),
                tuple(car._chassis.getAngularVelocity()),tuple(car._chassis.getTransform().getQuat()),
                tuple(car._chassis.getGravity()),tuple(car._chassis.getTotalForce()),tuple(car._chassis.getTotalTorque())))
        return result

    tire_drivetrain.advance_drivetrain = capture
    run = None
    try:
        run = LabExperiment(LabOptions(maneuver="manual",speed_kph=60.,duration=.6))
        run.manual_command = VehicleCommand(steering=3.,throttle=.4,brake=.15,gear=1,clutch=.7)
        ready = True
        while not run.done:
            run.step()
        args,kwargs,legacy,v0,a0,quaternion,gravity,force,torque = captured[-1]
        _free_v,_free_a,wheels,engine,frames,deformation,engine_torque,capacity,ratio,brakes,config,_rear,dt = args
        q = np.asarray(quaternion,dtype=float)
        q /= np.linalg.norm(q)
        w,x,y,z = q
        rotation = np.array(((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
                             (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
                             (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y))))
        centers = np.asarray([tuple(frame.hub) for frame in frames])@rotation
        inertia = rotation.T@np.linalg.inv(kwargs["inverse_inertia"])@rotation
        partition = partition_vehicle(config.mass,inertia,(40.,)*4,centers)
        center_shift = rotation@partition.center
        state = np.r_[np.asarray(v0)+np.cross(a0,center_shift),a0,np.zeros(4),engine,kwargs["shaft_omega"],wheels]
        mechanics = assemble_unsprung(partition,rotation,np.zeros(4),((0.,0.,1.),)*4,state[:10])
        graph = drivetrain_ports(mechanics,np.asarray([f.spin_axis for f in frames]),kwargs["engine_axis"],
            kwargs["shaft_axis"],kwargs["downstream_axes"],ratio,config)
        tangents,laterals,normals = (np.asarray([tuple(f.tangent) for f in frames]),
                                   np.asarray([tuple(f.axle) for f in frames]),
                                   np.asarray([f.elastic_frame[2] for f in frames]))
        trails = np.asarray([f.pneumatic_trail for f in frames])
        offsets = np.asarray([np.asarray(f.point)+f.pneumatic_trail*np.asarray(f.tangent)-f.hub for f in frames])
        steering = np.zeros((4,3))
        for i,(axis,transport,spin) in enumerate(zip(graph.axes,kwargs["steering_torques"],wheels)):
            derivative = np.asarray(transport)/(config.wheel_inertia*spin)
            direction = np.cross(rotation[:,2],axis)
            steering[i] = rotation[:,2]*np.dot(direction,derivative)/np.dot(direction,direction)
        contact = tire_ports(graph,offsets,tangents,laterals,normals,steering,trails)
        compression = kwargs["suspension"].compression
        old_load = np.asarray(legacy.suspension.axial_force)/np.asarray(legacy.suspension_system.alignment)
        radial = np.full(4,200000.)
        radial_deflection = old_load/radial
        known = np.r_[mechanics.gravity_forces(gravity)-mechanics.inertial_bias,np.zeros(6)]
        known[:3] += force
        known[3:6] += torque+np.cross(-center_shift,force)+np.sum(kwargs["steering_torques"],axis=0)
        initial_force = np.asarray(kwargs["force_initial"])[:,:2]
        result = solve_unsprung_joint(graph,contact,state,kwargs["downstream_omega"],compression,radial_deflection,
            deformation,initial_force,known,np.zeros(4),radial,np.full(4,500.),np.asarray([f.mu for f in frames]),
            kwargs["rolling_coefficients"],engine_torque,kwargs["engine_drag"],capacity,brakes,ratio,kwargs["synchronizing"],dt,config)
        assert result.momentum_error<1e-9 and result.force_error<1e-5 and result.port_error<1e-9
        assert abs(result.energy_error)<3e-8
        source = {"schema":"coastal-unsprung-joint-input-v1","config":asdict(config),"command":asdict(run.manual_command),
            "legacy_velocity":v0,"legacy_angular":a0,"legacy_orientation":quaternion,
            "wheel_masses":(40.,)*4,"radial_rates":radial,"radial_damping":(500.,)*4,
            "displacement":(0.,)*4,"guides_local":((0.,0.,1.),)*4,"road_delta":(0.,)*4,
            "wheel_centers_local":centers,"body_inertia_local":inertia,"rotation":rotation,"new_initial_velocity":state,
            "compression":compression,"radial_deflection":radial_deflection,"deformation":deformation,
            "initial_force":initial_force,"known_force":known,"axes":graph.axes,"engine_axis":graph.engine_axis,
            "shaft_axis":graph.shaft_axis,"downstream_axes":graph.downstream_axes,"downstream_omega":kwargs["downstream_omega"],
            "offsets":offsets,"tangents":tangents,"laterals":laterals,"normals":normals,"steering_angular":steering,
            "trails":trails,"friction":[f.mu for f in frames],"rolling_coefficients":kwargs["rolling_coefficients"],
            "engine_torque":engine_torque,"engine_drag":kwargs["engine_drag"],"clutch_capacity":capacity,
            "brake_capacities":brakes,"ratio":ratio,"synchronizing":kwargs["synchronizing"],"dt":dt,
            "source_fingerprint":model_fingerprint()}
        (output/"source-input.json").write_text(json.dumps(source,default=serial,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        (output/"prediction.json").write_text(json.dumps(asdict(result),default=serial,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        summary = {"stage":"frozen joint node using prepared real inputs; NOT installed in Simulation",
            "assumptions":"40kg each wheel, radial 200000N/m and 500Ns/m; zero relative wheel-center speed initial condition",
            "legacy_preload":"copied suspension state and prior solved load/radial rate, not a new static equilibrium",
            "known_work":"includes frozen geometric inertial bias; not finite-pose full-world energy validation",
            "iterations":result.iterations,"momentum_residual":result.momentum_error,
            "force_residual_N":result.force_error,"port_residual_Nm":result.port_error,"frozen_energy_error_J":result.energy_error,
            "normal_N":result.normal.normal_force,"FxFy_N":result.forces,"relative_wheel_center_speed_mps":result.velocity[6:10]}
        summary["actual_prepared_control"] = {"ratio":ratio,"synchronizing":kwargs["synchronizing"],
            "clutch_capacity":capacity,"brake_capacities":brakes,"engine_torque":engine_torque}
        (output/"summary.json").write_text(json.dumps(summary,default=serial,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        print(json.dumps(summary,default=serial,ensure_ascii=False))
    finally:
        tire_drivetrain.advance_drivetrain = original
        if run is not None:
            run.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    check(parser.parse_args().output.resolve())
