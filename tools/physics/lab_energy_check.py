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

from unsprung_step_checkpoint import save_step

import simulation as simulation_module
from lab_experiment import LabExperiment, LabOptions
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
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
            "wheel_velocity":velocities,"relative_velocity":_u,"inertia":hardware.mechanical.world_inertia,"mass":mass,
            "spin":spin,"spin_inertias":inertias,"spring":spring,"radial":tire,"tangent":tangent,
            "deflection":geometry.deflection,"compression":q+car._unsprung_reference,
            "normals":geometry.normals,"normal_offsets":geometry.normal_offsets,"axes":hardware.axes,
            "road_nodes":tuple(None if hit is None else hit.node.getName() for hit in geometry.hits),
            "contact_points":tuple(None if hit is None else hit.point for hit in geometry.hits),
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
    ports = tire_ports(hardware,geometry.offsets,geometry.tangents,geometry.laterals,geometry.normals,np.zeros((4,3)),np.zeros(4),
                       normal_offsets=geometry.normal_offsets)
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
    predicted_wheels = source.hardware.mechanical.wheel_jacobians@step.velocity[:10]
    if source.guide_velocity_bias is not None:
        predicted_wheels += source.guide_velocity_bias
    predicted_body,predicted_angular = step.velocity[:3],step.velocity[3:6]
    body_defect = .5*mass.mass*np.dot(new["velocity"]-predicted_body,new["velocity"]+predicted_body)
    wheel_defect = .5*np.sum(np.asarray(mass.wheel_masses)[:,None]
        *(new["wheel_velocity"]-predicted_wheels)*(new["wheel_velocity"]+predicted_wheels))
    angular_defect = .5*np.dot(new["angular"]-predicted_angular,
        old["inertia"]@(new["angular"]+predicted_angular))
    inertia_defect = .5*new["angular"]@(new["inertia"]-old["inertia"])@new["angular"]
    predicted_spin = np.r_[step.velocity[10:],step.downstream_omega]
    spin_defect = .5*np.dot(old["spin_inertias"],(new["spin"]-predicted_spin)*(new["spin"]+predicted_spin))
    if abs(native_kinetic-body_defect-wheel_defect-angular_defect-inertia_defect-spin_defect)>1e-8:
        raise ArithmeticError("原生动能差的独立分量不闭合")
    # 单精度舍入仅作参照；不写回速度，也不把误差当耗散。
    rounded_body = predicted_body.astype(np.float32).astype(float)
    rounded_wheels = predicted_wheels.astype(np.float32).astype(float)
    rounding_defect = .5*mass.mass*np.dot(rounded_body-predicted_body,rounded_body+predicted_body)
    rounding_defect += .5*np.sum(np.asarray(mass.wheel_masses)[:,None]
        *(rounded_wheels-predicted_wheels)*(rounded_wheels+predicted_wheels))
    elastic_geometry = elastic-step.potential_change+projection
    spring_geometry = new["spring"]-step.normal.suspension_potential
    radial_rates = np.asarray(source.config.tire_radial_stiffness)*np.array([hit is not None for hit in source.geometry.hits])
    initial_delta = source.geometry.deflection if source.finite_contact is None else source.finite_contact.initial.deflection
    old_radial = .5*np.dot(radial_rates,np.maximum(initial_delta,0.)**2)
    radial_geometry = new["radial"]-old["radial"]-(step.normal.tire_potential-old_radial)
    old_tangent = .5*source.config.tire_contact_stiffness*np.sum(source.deformation**2)
    tangent_geometry = new["tangent"]-old["tangent"]-(sum(w.elastic_energy for w in step.wheels)-old_tangent)+projection
    geometry_work = gravity+step.known_work-external-steering_gyro
    reconstructed = (step.energy_error+native_kinetic+elastic_geometry+geometry_work+step.guide_work
                     +step.body_gyro_work+step.suspension_geometry_work)
    if abs(residual-reconstructed)>1e-8:
        raise ArithmeticError("独立储能账与差项分解不一致")
    if abs(elastic_geometry-spring_geometry-radial_geometry-tangent_geometry)>1e-8:
        raise ArithmeticError("三个实际弹性储能差与总差不一致")
    normals = source.geometry.normals
    wheel_predicted = predicted_wheels
    point_motion = np.einsum('ij,ij->i',normals,h*wheel_predicted-displacement[1:])
    surface = source.contacts.normal@step.velocity+source.contacts.steering_velocity[:,2]
    if source.contacts.guide_velocity is not None:
        surface += source.contacts.guide_velocity[:,2]
    shape_motion = (new["deflection"]-initial_delta
                    +np.einsum('ij,ij->i',normals,displacement[1:])
                    +h*(step.normal_scale*surface-np.einsum('ij,ij->i',normals,wheel_predicted)))
    radial_defect = new["deflection"]-step.tire_deflection
    if np.max(np.abs(radial_defect-point_motion-shape_motion))>1e-12:
        raise ArithmeticError("实际径向位移差项不闭合")
    native_velocity_error = h*np.einsum('ij,ij->i',normals,wheel_predicted-new["wheel_velocity"])
    native_position_error = np.einsum('ij,ij->i',normals,h*new["wheel_velocity"]-displacement[1:])
    actual_spring = suspension_potential(new["compression"],source.config)[1]
    actual_damping = np.where(new["relative_velocity"]>=0.,source.config.suspension_compression_damping,
                              source.config.suspension_extension_damping)*new["relative_velocity"]
    return {"kinetic_change":kinetic,"gravity_change":gravity,"elastic_change":elastic,
            "losses":losses,"engine_work":step.engine_work,"external_work":external,
            "steering_gyro_work":steering_gyro,"contact_steering_work":step.steering_work,
            "moving_road_work":step.road_work,"actual_energy_residual":residual,
            "numerical_guide_work":step.guide_work,"energy_residual_after_guide_work":residual-step.guide_work,
            "energy_residual_after_guide_and_gyro_work":residual-step.guide_work-step.body_gyro_work,
            "suspension_geometry_work":step.suspension_geometry_work,
            "energy_residual_after_all_geometry_work":residual-step.guide_work-step.body_gyro_work-step.suspension_geometry_work,
            "suspension_force_end_error_max":float(np.max(np.abs(step.normal.suspension_force-actual_spring-actual_damping))),
            "suspension_velocity_end_error_max":float(np.max(np.abs(new["relative_velocity"]-step.suspension_relative_velocity))),
            "suspension_compression_end_error_max":float(np.max(np.abs(new["compression"]-step.compression))),
            "frozen_energy_residual":step.energy_error,"native_kinetic_defect":native_kinetic,
            "native_body_translation_defect":body_defect,"native_wheel_translation_defect":wheel_defect,
            "native_body_angular_defect":angular_defect,"native_inertia_transport_defect":inertia_defect,
            "native_spin_defect":spin_defect,"float32_translation_rounding_defect":rounding_defect,
            "native_translation_beyond_rounding":body_defect+wheel_defect-rounding_defect,
            "native_body_velocity_error":float(np.max(np.abs(new["velocity"]-predicted_body))),
            "native_wheel_velocity_error":float(np.max(np.abs(new["wheel_velocity"]-predicted_wheels))),
            "elastic_geometry_defect":elastic_geometry,"geometry_work_defect":geometry_work,
            "spring_geometry_defect":spring_geometry,"radial_geometry_defect":radial_geometry,
            "tangent_geometry_defect":tangent_geometry,
            **{f"radial_deflection_defect_{i}":float(new["deflection"][i]-step.tire_deflection[i]) for i in range(4)},
            **{f"spring_compression_defect_{i}":float(new["compression"][i]-step.compression[i]) for i in range(4)},
            **{f"point_motion_defect_{i}":float(point_motion[i]) for i in range(4)},
            **{f"surface_shape_defect_{i}":float(shape_motion[i]) for i in range(4)},
            **{f"native_point_velocity_defect_{i}":float(native_velocity_error[i]) for i in range(4)},
            **{f"native_point_position_defect_{i}":float(native_position_error[i]) for i in range(4)},
            **{f"normal_spin_radius_{i}":float(source.contacts.spin_radii[i,2]) for i in range(4)},
            "body_gyro_work":step.body_gyro_work,
            "continuous_bias_work_not_applied":-h*np.dot(step.velocity[:10],source.hardware.mechanical.inertial_bias)}


def write_rows(path,rows):
    with path.open("w",encoding="utf-8",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=rows[0])
        writer.writeheader();writer.writerows(rows)


def check(output, maneuver, duration, substeps):
    output.mkdir(parents=True,exist_ok=False)
    executed = Path(__file__).read_bytes()
    (output/"executed-tool.py").write_bytes(executed)
    config = replace(REFERENCE_DESIGN,unsprung_enabled=True,tire_substeps=substeps)
    options = LabOptions(maneuver=maneuver,speed_kph=18. if maneuver=="ride_bump" else 60.,duration=duration)
    run = LabExperiment(options,config=config)
    rows, pending, peak = [],[],[]
    original_commit, original_advance = UnsprungAdvanceInput.commit,simulation_module.advance_world
    original_solve = UnsprungAdvanceInput.solve

    def solve(source,**kwargs):
        try:
            return original_solve(source,**kwargs)
        except ArithmeticError as error:
            save_step(source,output/"failed-step.pkl")
            failure = {"error":str(error),"completed_steps":len(rows),"completed_time":len(rows)*source.dt,
                       "summary":run.summary(),"source":model_fingerprint(),"config":asdict(config)}
            (output/"failure.json").write_text(json.dumps(failure,indent=2,ensure_ascii=False),encoding="utf-8")
            write_rows(output/"completed-substeps.csv",rows)
            raise

    def commit(source, car, result):
        old_angles = tuple(w.steering for w in car.tires.states[:2])
        pending.append((source.resolved_source(result),result,state(car,old_angles)))
        original_commit(source,car,result)

    def advance(*args,observe,**kwargs):
        def after(before,last):
            source,result,old = pending.pop()
            new = state(run.experiment.simulation.player,source.angles)
            row = balance(source,result,old,new)
            row["substep"] = len(rows)+1
            row["time"] = row["substep"]*source.dt
            rows.append(row)
            if not peak or abs(row["elastic_geometry_defect"])>abs(peak[0]["ledger"]["elastic_geometry_defect"]):
                def physical(values):
                    keys = ("position","rotation","centers","velocity","angular","wheel_velocity",
                            "spin","deflection","compression","normals","normal_offsets","axes")
                    return {**{key:values[key].tolist() for key in keys},
                            "road_nodes":values["road_nodes"],"contact_points":values["contact_points"]}
                peak[:] = [{"ledger":row,"actual_before":physical(old),"actual_after":physical(new),
                            "initial_velocity":source.velocity.tolist(),"predicted_velocity":result.velocity.tolist(),
                            "normal_port":source.contacts.normal.tolist(),"known_force":source.known_force.tolist(),
                            "predicted_compression":result.compression.tolist(),"predicted_deflection":result.tire_deflection.tolist(),
                            "normal_force":result.normal.normal_force.tolist(),"dt":source.dt}]
            observe(before,last)
        return original_advance(*args,observe=after,**kwargs)

    UnsprungAdvanceInput.commit,simulation_module.advance_world = commit,advance
    UnsprungAdvanceInput.solve = solve
    try:
        while not run.done:
            command = VehicleCommand(steering=3.,throttle=.4,brake=.15,gear=1,clutch=.7) if maneuver=="manual" else None
            run.step(command)
        with (output/"substeps.csv").open("w",newline="",encoding="utf-8") as stream:
            writer = csv.DictWriter(stream,fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
        result = {"summary":run.summary(),"config":asdict(config),"substeps":substeps,"source":model_fingerprint(),
                  "tool_sha256":hashlib.sha256(executed).hexdigest(),"runtime":runtime_fingerprint(),
                  "definition":"Actual world kinetic + gravity + suspension/radial/tangent potential; all joint losses. External force work uses actual displacement; imposed steering/engine use joint end-speed quadrature. Diagnostic residual, not a claimed closed energy gate.",
                  "max_abs":{key:max(abs(r[key]) for r in rows) for key in rows[0] if key not in ("time","substep")},
                  "sum":{key:sum(r[key] for r in rows) for key in rows[0] if key not in ("time","substep")}}
        result["normal_geometry_derivatives"] = normal_geometry_derivatives(run.experiment.simulation.player)
        (output/"result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
        (output/"peak-input.json").write_text(json.dumps(peak[0],indent=2,ensure_ascii=False),encoding="utf-8")
        print(json.dumps({"reason":run.reason,"steps":len(rows),"energy_residual_max":result["max_abs"]["actual_energy_residual"],"energy_residual_sum":result["sum"]["actual_energy_residual"]}))
    finally:
        UnsprungAdvanceInput.commit,simulation_module.advance_world = original_commit,original_advance
        UnsprungAdvanceInput.solve = original_solve
        run.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--maneuver",choices=("ride_bump","manual"),default="ride_bump")
    parser.add_argument("--duration",type=float,default=2.4)
    parser.add_argument("--substeps",type=int,choices=(2,4,8),default=2)
    args = parser.parse_args()
    check(args.output.resolve(),args.maneuver,args.duration,args.substeps)
