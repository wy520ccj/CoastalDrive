"""在真实提交/世界推进边界分解CG动量舍入与有限行程；只读，不补偿实际状态。"""

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

import lab_energy_check as energy

from unsprung_contact import suspension_potential
from unsprung_contact_geometry import rotation_increment
from vehicle_unsprung import UnsprungAdvanceInput


def check(output, maneuver, duration, substeps):
    original_commit,original_balance = UnsprungAdvanceInput.commit,energy.balance
    phase = {}

    def commit(source,car,result):
        active = source.resolved_source(result)
        before = np.array([tuple(car._chassis.getLinearVelocity()),
                           *(tuple(point.getLinearVelocity()) for point in car._wheel_guides.points)])
        contact_force = (result.forces[:,0,None]*active.contacts.longitudinal[:,:3]
                         +result.forces[:,1,None]*active.contacts.lateral[:,:3]
                         +result.normal.normal_force[:,None]*active.contacts.normal[:,:3])
        spring = result.normal.suspension_force[:,None]*active.hardware.mechanical.guides
        original_commit(source,car,result)
        after = np.array([tuple(car._chassis.getLinearVelocity()),
                          *(tuple(point.getLinearVelocity()) for point in car._wheel_guides.points)])
        phase.clear()
        phase.update(before=before,after=after,forces=np.vstack((spring.sum(axis=0),contact_force-spring)))

    def balance(source,step,old,new):
        row = original_balance(source,step,old,new)
        masses = np.r_[old["mass"].mass,old["mass"].wheel_masses]
        mass = masses.sum()
        weights = masses[:,None]
        before,submitted = phase["before"],phase["after"]
        actual = np.vstack((new["velocity"],new["wheel_velocity"]))
        predicted_wheels = source.hardware.mechanical.wheel_jacobians@step.velocity[:10]
        if source.guide_velocity_bias is not None:predicted_wheels += source.guide_velocity_bias
        predicted = np.vstack((step.velocity[:3],predicted_wheels))
        external = old["external_force"]+weights*old["gravity"]
        applied_error = np.sum(weights*(submitted-before),axis=0)-source.dt*phase["forces"].sum(axis=0)
        world_error = np.sum(weights*(actual-submitted),axis=0)-source.dt*external.sum(axis=0)
        total_error = np.sum(weights*(actual-before),axis=0)-source.dt*(phase["forces"]+external).sum(axis=0)
        assert np.max(np.abs(total_error-applied_error-world_error))<1e-10
        actual_cg,predicted_cg = (np.sum(weights*velocities,axis=0)/mass for velocities in (actual,predicted))
        ideal_cg = (np.sum(weights*before,axis=0)+source.dt*(phase["forces"]+external).sum(axis=0))/mass
        assert np.max(np.abs(predicted_cg-ideal_cg))*mass<2e-9
        cg_energy = .5*mass*np.dot(actual_cg-predicted_cg,actual_cg+predicted_cg)
        actual_relative,predicted_relative = actual-actual_cg,predicted-predicted_cg
        relative_energy = .5*np.sum(weights*(actual_relative-predicted_relative)*(actual_relative+predicted_relative))
        assert abs(cg_energy+relative_energy-row["native_body_translation_defect"]-row["native_wheel_translation_defect"])<1e-8
        old_arm = old["centers"]-old["position"]
        finite_arm = old_arm+source.dt*(predicted_wheels-step.velocity[:3])
        finite_guide = rotation_increment(source.dt*step.velocity[3:6])@old["rotation"][:,2]
        finite_compression = (old["compression"]+finite_arm@finite_guide-old_arm@old["rotation"][:,2])
        finite_potential = suspension_potential(finite_compression,source.config)[0]
        finite_spring = finite_potential-step.normal.suspension_potential
        native_spring = new["spring"]-finite_potential
        assert abs(finite_spring+native_spring-row["spring_geometry_defect"])<1e-10
        for prefix,vector in (("apply_momentum_error",applied_error),("world_momentum_error",world_error),
                              ("total_momentum_error",total_error)):
            row.update({f"{prefix}_{axis}":float(vector[index]) for index,axis in enumerate("xyz")})
        row.update(native_cg_energy_defect=float(cg_energy),native_relative_energy_defect=float(relative_energy),
                   finite_spring_geometry_defect=float(finite_spring),native_spring_geometry_defect=float(native_spring),
                   cg_prediction_momentum_error=float(np.max(np.abs(predicted_cg-ideal_cg))*mass))
        row.update({f"finite_compression_defect_{i}":float(finite_compression[i]-step.compression[i]) for i in range(4)})
        row.update({f"native_compression_defect_{i}":float(new["compression"][i]-finite_compression[i]) for i in range(4)})
        return row

    UnsprungAdvanceInput.commit,energy.balance = commit,balance
    try:
        energy.check(output,maneuver,duration,substeps)
        (output/"executed-momentum-tool.py").write_bytes(Path(__file__).read_bytes())
    finally:
        UnsprungAdvanceInput.commit,energy.balance = original_commit,original_balance


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--maneuver",choices=("manual","ride_bump"),default="manual")
    parser.add_argument("--duration",type=float,default=.12)
    parser.add_argument("--substeps",type=int,choices=(2,4,8),default=2)
    args = parser.parse_args()
    check(args.output.resolve(),args.maneuver,args.duration,args.substeps)
