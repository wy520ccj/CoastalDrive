"""从真实参考车初始化读取质量/轮心，核对新簧下算子的参考构型；非全车新机制验收。"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from lab_experiment import LabExperiment, LabOptions
from lab_records import model_fingerprint
from suspension import stiffness_matrix
from unsprung_dynamics import assemble_unsprung, partition_vehicle


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    run = LabExperiment(LabOptions(speed_kph=0.,duration=.1))
    try:
        state = run.current.player
        q = np.asarray(state.orientation,dtype=float)
        q /= np.linalg.norm(q)
        w,x,y,z = q
        rotation = np.array(((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
                             (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
                             (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y))))
        centers = (np.asarray([wheel.position for wheel in state.wheels])-state.position)@rotation
        config = run.config
        locked = np.diag(config.body_inertia)
        results = []
        for wheel_mass in (25.,40.,65.):
            partition = partition_vehicle(config.mass,locked,(wheel_mass,)*4,centers)
            zero = np.zeros(10)
            guides = np.array(((0.,0.,1.),)*4)
            mechanics = assemble_unsprung(partition,np.eye(3),np.zeros(4),guides,zero)
            gravity = mechanics.acceleration(mechanics.gravity_forces((0.,0.,-9.81)))
            assert np.max(np.abs(gravity-np.r_[(0.,0.,-9.81),np.zeros(7)]))<1e-12
            js = np.zeros((4,10))
            js[:,6:] = np.eye(4)
            jn = mechanics.wheel_jacobians[:,2,:]
            stiffness = js.T@np.asarray(stiffness_matrix(config.suspension_spring_rates,config.suspension_antiroll_rates))@js
            stiffness += 200000.*jn.T@jn
            inv_chol = np.linalg.solve(np.linalg.cholesky(mechanics.mass_matrix),np.eye(10))
            squared,modes = np.linalg.eigh(inv_chol@stiffness@inv_chol.T)
            assert np.max(np.abs(squared[:3]))<1e-8 and squared[3]>0.
            modal = []
            for eigenvalue, mode in zip(squared[3:],modes.T[3:]):
                v = inv_chol.T@mode
                body = .5*(partition.mass*np.dot(v[:3],v[:3])+v[3:6]@mechanics.world_inertia@v[3:6])
                modal.append({"frequency_hz":float(np.sqrt(eigenvalue)/(2*np.pi)),
                              "sprung_energy_fraction":float(body/(.5*v@mechanics.mass_matrix@v))})
            results.append({"wheel_mass_kg":wheel_mass,"partition":asdict(partition),
                            "min_mass_eigenvalue":float(np.linalg.eigvalsh(mechanics.mass_matrix)[0]),
                            "free_fall_max_error_mps2":float(np.max(np.abs(gravity-np.r_[(0.,0.,-9.81),np.zeros(7)]))),
                            "linearized_modes":modal})
        (output/"source-snapshot.json").write_text(json.dumps(asdict(run.current),ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        report = {"stage":"in_progress: mechanics basis only, not integrated into Simulation",
                  "parameter_basis":"25/40/65kg and 200000N/m are hypothetical design cases, not measured",
                  "configuration":asdict(config),"locked_wheel_centers_from_snapshot":centers.tolist(),
                  "definition_fingerprint":model_fingerprint(),"cases":results}
        (output/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        print(json.dumps({"sprung_masses":[item["partition"]["mass"] for item in results],
                          "frequencies_hz":[[round(mode["frequency_hz"],5) for mode in item["linearized_modes"]] for item in results],
                          "world_integration":"not yet"},ensure_ascii=False))
    finally:
        run.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    check(parser.parse_args().output.resolve())
