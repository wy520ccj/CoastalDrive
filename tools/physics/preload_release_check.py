"""真实五刚体空中预载释放对解析两质量极限；不在运行中修改位姿或关闭碰撞。"""

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, replace
from itertools import pairwise
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from simulation import Simulation
from unsprung_contact import suspension_potential
from vehicle_designs import REFERENCE_DESIGN
from vehicle_state import VehicleCommand


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    source,runtime = model_fingerprint(),runtime_fingerprint()
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    mass_s,mass_u,k_total,offset = 1040.,160.,192000.,.02
    reduced_mass = 1/(1/mass_s+1/mass_u)
    omega = math.sqrt(k_total/reduced_mass)
    release_time = math.pi/(2*omega)
    rows,results = [],[]
    for substeps in (2,4,8):
        config = replace(REFERENCE_DESIGN,unsprung_enabled=True,suspension_coil_enabled=True,
            suspension_spring_preloads=(960.,)*4,suspension_antiroll_rates=(0.,0.),suspension_stop_rates=(0.,)*4,
            suspension_compression_damping=(0.,)*4,suspension_extension_damping=(0.,)*4,
            engine_braking=0.,engine_idle_torque_limit=0.,air_density=0.,tire_substeps=substeps)
        simulation = Simulation(track="lab",traffic_count=0,config=config)
        try:
            # 仅定义t=0初值。解析极限取无空气/无阻尼；保留原生重力、碰撞和实际五刚体/四导向。
            simulation.player.reset((0.,0.,6.),heading=0.,speed=0.)
            snapshot = simulation.snapshot().player
            initial = snapshot.unsprung_state
            initial_q = np.array([wheel.compression for wheel in snapshot.wheel_contacts])
            assert np.max(np.abs(initial_q)) < 1e-12
            initial_energy = suspension_potential(initial_q,config)[0]
            local = []
            for step in range(1,16):
                simulation.step(VehicleCommand(gear=0,clutch=0.))
                state = simulation.snapshot().player
                observation = state.unsprung_state
                q = np.array([wheel.compression for wheel in state.wheel_contacts])
                potential,force = suspension_potential(q,config)
                center_speed = np.asarray(observation.total_center_velocity)
                energy = .5*mass_s*np.sum((np.asarray(observation.sprung_velocity)-center_speed)**2)
                energy += .5*40*np.sum((np.asarray(observation.wheel_velocities)-center_speed)**2)+potential
                time = step/120
                expected = offset*(math.cos(omega*time)-1) if time<=release_time else -offset-offset*omega*(time-release_time)
                row = {"substeps":substeps,"time_s":time,"q_mean_m":float(np.mean(q)),"analytic_q_m":expected,
                    "q_error_m":float(np.max(np.abs(q-expected))),"spring_force_max_N":float(np.max(force)),
                    "internal_energy_J":float(energy),"initial_energy_J":float(initial_energy),
                    "normal_force_max_N":float(max(observation.normal_force)),
                    "center_freefall_error_mps":float(np.max(np.abs(center_speed-np.array((0.,0.,-9.81*time)))))}
                rows.append(row);local.append(row)
            with (output/f"samples-{substeps}.csv").open("w",encoding="utf-8",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=local[0]);writer.writeheader();writer.writerows(local)
            assert max(row["normal_force_max_N"] for row in local)==0.
            assert local[-1]["spring_force_max_N"]==0.
            assert max(row["internal_energy_J"] for row in local)<=initial_energy+1e-8
            assert max(row["center_freefall_error_mps"] for row in local)<1e-9
            assert model_fingerprint()==source and runtime_fingerprint()==runtime
            results.append({"substeps":substeps,"config":asdict(config),"q_error_peak_m":max(row["q_error_m"] for row in local),
                "last":local[-1],"initial_q_m":initial_q.tolist(),"initial_sprung_position":initial.sprung_position})
            print(json.dumps({"substeps":substeps,"q_error_peak_m":results[-1]["q_error_peak_m"]}),flush=True)
        finally:
            simulation.close()
    assert all(b["q_error_peak_m"]<a["q_error_peak_m"] for a,b in pairwise(results))
    with (output/"samples.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    (output/"result.json").write_text(json.dumps({"source":source,"runtime":runtime,"results":results,
        "omega_rad_s":omega,"analytic_release_time_s":release_time,"definition":"passive spring release in freefall; relative energy removes center translation; NOT a powered road manoeuvre"},
        ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output.resolve())
