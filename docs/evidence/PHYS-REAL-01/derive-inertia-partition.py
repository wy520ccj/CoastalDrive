"""整车刚性随动惯量与现有绝对转子速度的分账；只生成准备证据。"""

import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
prior_path = root / "mass-distribution-prior.json"
prior = json.loads(prior_path.read_text(encoding="utf-8"))
# 暂沿用通用参考硬件的转子初值，均非GR86实测；前驱动轴在RWD中不安装。
rotors = [
    {"name": f"wheel-{i}", "inertia_kg_m2": 1.8, "axis": [-1., 0., 0.]}
    for i in range(4)
] + [
    {"name": "engine", "inertia_kg_m2": .2, "axis": [0., 1., 0.]},
    {"name": "input-shaft", "inertia_kg_m2": .04, "axis": [0., 1., 0.]},
    {"name": "output-shaft", "inertia_kg_m2": .03, "axis": [0., 1., 0.]},
    {"name": "rear-drive-shaft", "inertia_kg_m2": .02, "axis": [0., 1., 0.]},
]
deduction = [sum(r["inertia_kg_m2"] * r["axis"][a] ** 2 for r in rotors) for a in range(3)]
cases = []
for case in prior["cases"]:
    whole = case["whole_rigid_pose_inertia_xyz_kg_m2"]
    body = [whole[a] - deduction[a] for a in range(3)]
    probes = []
    # 独立按每个实体转子的绝对轴速计算能量与角动量，核对三个轴及混合运动。
    for angular in ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.), (.3, -.7, 1.1)):
        energy = .5 * sum(body[a] * angular[a] ** 2 for a in range(3))
        momentum = [body[a] * angular[a] for a in range(3)]
        for rotor in rotors:
            axis, inertia = rotor["axis"], rotor["inertia_kg_m2"]
            absolute_speed = sum(axis[a] * angular[a] for a in range(3))
            energy += .5 * inertia * absolute_speed ** 2
            for a in range(3):
                momentum[a] += inertia * absolute_speed * axis[a]
        expected_energy = .5 * sum(whole[a] * angular[a] ** 2 for a in range(3))
        expected_momentum = [whole[a] * angular[a] for a in range(3)]
        energy_error = energy - expected_energy
        momentum_error = max(abs(momentum[a] - expected_momentum[a]) for a in range(3))
        assert abs(energy_error) < 1e-12 and momentum_error < 1e-12
        probes.append({"body_angular_velocity_rad_s": angular,
                       "energy_error_J": energy_error, "max_momentum_error_N_m_s": momentum_error})
    cases.append({"assumed_center_of_mass_height_m": case["assumed_center_of_mass_height_m"],
                  "whole_rigid_pose_inertia_xyz_kg_m2": whole,
                  "candidate_body_inertia_xyz_kg_m2": body, "locked_pose_probes": probes})

record = {
    "status": "isolated engineering preparation; not a loadable or calibrated GR86 config",
    "prior_file_sha256": hashlib.sha256(prior_path.read_bytes()).hexdigest(),
    "rotor_basis": "reference-v28 engineering assumptions, pending GR86 calibration",
    "reference_pose": "zero steer, axes fixed in body, zero rotor motion relative to housing",
    "rotors": rotors,
    "deduction_xyz_kg_m2": deduction,
    "cases": cases,
    "equation": "I_body = I_whole - sum(J * axis * axis^T)",
    "boundaries": [
        "Mass and parallel-axis position contributions remain in the whole-vehicle body model",
        "Only independently modelled axial spin inertia is deducted; transverse rotor inertia is retained",
        "Relative spin adds its own absolute-speed energy and momentum in the existing solver",
        "Steering changes the physical rotor axes; do not dynamically retune body_inertia to cancel it",
        "The front drive shaft is absent for this RWD candidate",
        "A different rotor calibration requires recomputing this partition before vehicle rebuild",
    ],
}
(root / "inertia-partition.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"deduction_xyz_kg_m2": deduction,
                  "candidate_body_inertias": [c["candidate_body_inertia_xyz_kg_m2"] for c in cases]}))
