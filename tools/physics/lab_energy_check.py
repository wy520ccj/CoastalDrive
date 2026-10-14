"""读取正式世界的有限姿态全储能账；诊断钩子不改输入、冲量或原生推进。"""

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import simulation as simulation_module
from lab_experiment import LabExperiment, LabOptions
from lab_records import model_fingerprint
from unsprung_contact import suspension_potential
from unsprung_drivetrain import tire_ports
from unsprung_dynamics import cross_matrix
from unsprung_geometry import read_unsprung_geometry
from vehicle_designs import REFERENCE_DESIGN
from vehicle_state import VehicleCommand
from vehicle_unsprung import UnsprungAdvanceInput, read_mechanics


def state(car, angles):
    """储能直接读实际物体/轴速/材料状态，不用共同求解的预测姿态。"""
    pos, rotation, centers, velocities, q, _u, _xy, v, hardware = read_mechanics(car, angles)
    geometry = read_unsprung_geometry(car._world, car._chassis, centers, rotation[:,2], hardware.axes, car.config)
    mass = car._sprung_frame.partition
    radial = np.where([hit is not None for hit in geometry.hits], np.maximum(geometry.deflection,0.),0.)
    spring = suspension_potential(q+car._unsprung_reference,car.config)[0]
    tire = .5*np.dot(car.config.tire_radial_stiffness,radial**2)
    tangent = .5*car.config.tire_contact_stiffness*np.sum(np.asarray(car.tires.deformation)**2)
    spin = np.r_[car.powertrain.engine_omega,car.powertrain.shaft_omega,car.tires.omega,car.powertrain.downstream_omega]
    inertias = np.r_[car.config.engine_inertia,car.config.input_shaft_inertia,
                    np.full(4,car.config.wheel_inertia),hardware.downstream_inertias]
    return {"position":pos,"rotation":rotation,"centers":centers,"velocity":v[:3],"angular":v[3:6],
            "wheel_velocity":velocities,"inertia":hardware.mechanical.world_inertia,"mass":mass,
            "spin":spin,"spin_inertias":inertias,"spring":spring,"radial":tire,"tangent":tangent,
            "deflection":geometry.deflection,"compression":q+car._unsprung_reference,
            "gravity":np.array([tuple(car._chassis.getGravity()),*(tuple(p.getGravity()) for p in car._wheel_guides.points)]),
            "external_force":np.array([tuple(car._chassis.getTotalForce()),*(tuple(p.getTotalForce()) for p in car._wheel_guides.points)]),
            "external_torque":np.asarray(tuple(car._chassis.getTotalTorque()))}


def rotation_increment(old, new):
    matrix = new@old.T
    skew = np.array((matrix[2,1]-matrix[1,2],matrix[0,2]-matrix[2,0],matrix[1,0]-matrix[0,1]))/2
    sine = np.linalg.norm(skew)
    return np.zeros(3) if sine==0. else skew*np.arctan2(sine,(np.trace(matrix)-1)/2)/sine


def normal_geometry_derivatives(car):
    """虚位姿只用于同一道路几何查询；不移动任何实际刚体、不推进物理。"""
    angles = tuple(s.steering for s in car.tires.states[:2])
    pos,rotation,centers,_vel,_q,_u,_xy,_v,hardware = read_mechanics(car,angles)
    geometry = read_unsprung_geometry(car._world,car._chassis,centers,rotation[:,2],hardware.axes,car.config)
    ports = tire_ports(hardware,geometry.offsets,geometry.tangents,geometry.laterals,geometry.normals,np.zeros((4,3)),np.zeros(4))
    results = []
    for epsilon in (1e-3,1e-4,1e-5):
        for axis in range(3):
            skew = cross_matrix(np.eye(3)[axis])
            plus = np.eye(3)+np.sin(epsilon)*skew+(1-np.cos(epsilon))*skew@skew
            minus = plus.T
            deltas = []
            for transform in (plus,minus):
                test = read_unsprung_geometry(car._world,car._chassis,(centers-pos)@transform.T+pos,
                    transform@rotation[:,2],hardware.axes@transform.T,car.config)
                deltas.append(test.deflection)
            derivative = (deltas[0]-deltas[1])/(2*epsilon)
            conjugate = -ports.normal[:,3+axis]
            results.append({"rotation_axis":axis,"epsilon":epsilon,
                            "geometry_derivative":derivative.tolist(),"conjugate_port":conjugate.tolist(),
                            "difference":(derivative-conjugate).tolist()})
    return results


def balance(source, step, old, new):
    mass, h = old["mass"],source.dt
    dv = new["velocity"]-old["velocity"]
    dw = new["wheel_velocity"]-old["wheel_velocity"]
    kinetic = .5*mass.mass*np.dot(dv,new["velocity"]+old["velocity"])
    kinetic += .5*np.sum(np.asarray(mass.wheel_masses)[:,None]*dw*(new["wheel_velocity"]+old["wheel_velocity"]))
    kinetic += .5*(new["angular"]@new["inertia"]@new["angular"]-old["angular"]@old["inertia"]@old["angular"])
    kinetic += .5*np.dot(old["spin_inertias"],(new["spin"]-old["spin"])*(new["spin"]+old["spin"]))
    displacement = np.vstack((new["position"]-old["position"],new["centers"]-old["centers"]))
    masses = np.r_[mass.mass,mass.wheel_masses]
    gravity = -np.sum(masses[:,None]*old["gravity"]*displacement)
    elastic = sum(new[key]-old[key] for key in ("spring","radial","tangent"))
    external = np.sum(old["external_force"]*displacement)
    external += np.dot(old["external_torque"],rotation_increment(old["rotation"],new["rotation"]))
    steering_gyro = h*np.dot(np.sum(source.steering_torque,axis=0),step.velocity[3:6])
    projection = np.sum(source.frame_loss)
    losses = (step.kinetic_numerical_loss+step.material_loss+step.contact_numerical_loss+step.road_loss
              +np.sum(step.port_heat)+step.rolling_heat+step.engine_heat+projection)
    residual = kinetic+gravity+elastic+losses-step.engine_work-external-steering_gyro-step.steering_work-step.road_work
    native_kinetic = kinetic-step.kinetic_change
    elastic_geometry = elastic-step.potential_change+projection
    spring_geometry = new["spring"]-step.normal.suspension_potential
    radial_rates = np.asarray(source.config.tire_radial_stiffness)*np.array([hit is not None for hit in source.geometry.hits])
    old_radial = .5*np.dot(radial_rates,np.maximum(source.geometry.deflection,0.)**2)
    radial_geometry = new["radial"]-old["radial"]-(step.normal.tire_potential-old_radial)
    old_tangent = .5*source.config.tire_contact_stiffness*np.sum(source.deformation**2)
    tangent_geometry = new["tangent"]-old["tangent"]-(sum(w.elastic_energy for w in step.wheels)-old_tangent)+projection
    geometry_work = gravity+step.known_work-external-steering_gyro
    reconstructed = step.energy_error+native_kinetic+elastic_geometry+geometry_work
    if abs(residual-reconstructed)>1e-8:
        raise ArithmeticError("独立储能账与差项分解不一致")
    if abs(elastic_geometry-spring_geometry-radial_geometry-tangent_geometry)>1e-8:
        raise ArithmeticError("三个实际弹性储能差与总差不一致")
    return {"kinetic_change":kinetic,"gravity_change":gravity,"elastic_change":elastic,
            "losses":losses,"engine_work":step.engine_work,"external_work":external,
            "steering_gyro_work":steering_gyro,"contact_steering_work":step.steering_work,
            "moving_road_work":step.road_work,"actual_energy_residual":residual,
            "frozen_energy_residual":step.energy_error,"native_kinetic_defect":native_kinetic,
            "elastic_geometry_defect":elastic_geometry,"geometry_work_defect":geometry_work,
            "spring_geometry_defect":spring_geometry,"radial_geometry_defect":radial_geometry,
            "tangent_geometry_defect":tangent_geometry,
            **{f"radial_deflection_defect_{i}":float(new["deflection"][i]-step.tire_deflection[i]) for i in range(4)},
            **{f"spring_compression_defect_{i}":float(new["compression"][i]-step.compression[i]) for i in range(4)},
            "inertial_bias_work":-h*np.dot(step.velocity[:10],source.hardware.mechanical.inertial_bias)}


def check(output, maneuver, duration, substeps):
    output.mkdir(parents=True,exist_ok=False)
    executed = Path(__file__).read_bytes()
    (output/"executed-tool.py").write_bytes(executed)
    config = replace(REFERENCE_DESIGN,unsprung_enabled=True,tire_substeps=substeps)
    options = LabOptions(maneuver=maneuver,speed_kph=18. if maneuver=="ride_bump" else 60.,duration=duration)
    run = LabExperiment(options,config=config)
    rows, pending = [],[]
    original_commit, original_advance = UnsprungAdvanceInput.commit,simulation_module.advance_world

    def commit(source, car, result):
        pending.append((source,result,state(car,source.angles)))
        original_commit(source,car,result)

    def advance(*args,observe,**kwargs):
        def after(before,last):
            source,result,old = pending.pop()
            row = balance(source,result,old,state(run.experiment.simulation.player,source.angles))
            row["substep"] = len(rows)+1
            row["time"] = row["substep"]*source.dt
            rows.append(row)
            observe(before,last)
        return original_advance(*args,observe=after,**kwargs)

    UnsprungAdvanceInput.commit,simulation_module.advance_world = commit,advance
    try:
        while not run.done:
            command = VehicleCommand(steering=3.,throttle=.4,brake=.15,gear=1,clutch=.7) if maneuver=="manual" else None
            run.step(command)
        with (output/"substeps.csv").open("w",newline="",encoding="utf-8") as stream:
            writer = csv.DictWriter(stream,fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
        result = {"summary":run.summary(),"config":asdict(config),"substeps":substeps,"source":model_fingerprint(),
                  "tool_sha256":hashlib.sha256(executed).hexdigest(),
                  "definition":"Actual world kinetic + gravity + suspension/radial/tangent potential; all joint losses. External force work uses actual displacement; imposed steering/engine use joint end-speed quadrature. Diagnostic residual, not a claimed closed energy gate.",
                  "max_abs":{key:max(abs(r[key]) for r in rows) for key in rows[0] if key not in ("time","substep")},
                  "sum":{key:sum(r[key] for r in rows) for key in rows[0] if key not in ("time","substep")}}
        result["normal_geometry_derivatives"] = normal_geometry_derivatives(run.experiment.simulation.player)
        (output/"result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
        print(json.dumps({"reason":run.reason,"steps":len(rows),"energy_residual_max":result["max_abs"]["actual_energy_residual"],"energy_residual_sum":result["sum"]["actual_energy_residual"]}))
    finally:
        UnsprungAdvanceInput.commit,simulation_module.advance_world = original_commit,original_advance
        run.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--maneuver",choices=("ride_bump","manual"),default="ride_bump")
    parser.add_argument("--duration",type=float,default=2.4)
    parser.add_argument("--substeps",type=int,choices=(2,4,8),default=2)
    args = parser.parse_args()
    check(args.output.resolve(),args.maneuver,args.duration,args.substeps)
