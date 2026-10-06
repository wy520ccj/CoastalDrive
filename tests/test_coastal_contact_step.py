"""保存的实际海岸跨面子步：共同末状态、共轭冲量和悬架能量。"""

import json
from pathlib import Path

from suspension import SuspensionInput
from suspension_geometry import CylinderSurface
from suspension_kinematics import SupportPlane, finite_contact_system
from tire_coupling import ContactFrame
from tire_drivetrain import advance_drivetrain
from triangle_support import TriangleSupport
from vehicle_config import CAR
from vehicle_parameters import load_vehicle_config
from wheel_dynamics import Mobility


def test_captured_coastal_edge_step_has_one_conjugate_end_state():
    path = Path(__file__).resolve().parents[1] / "docs/evidence/PHYS-DESIGN-01/coastal-step-input.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    config = load_vehicle_config(path.parent / data["config_file"], CAR)
    mesh = TriangleSupport.build(data["triangles_m"])
    planes = []
    for values in data["planes"]:
        surface = values.pop("surface")
        for name in ("offset", "wheel_axis", "half"):
            surface[name] = tuple(surface[name])
        surface["axes"] = tuple(tuple(row) for row in surface["axes"])
        for name in ("hub", "direction", "normal", "point"):
            values[name] = tuple(values[name])
        planes.append(SupportPlane(**values, surface=CylinderSurface(**surface, triangles=mesh)))
    suspension = data["suspension"]
    for name in ("compression", "geometry", "touching", "alignment"):
        suspension[name] = tuple(suspension[name])
    suspension["gradients"] = tuple(tuple(row) for row in suspension["gradients"])
    system = SuspensionInput(**suspension, config=config, kinematics=tuple(planes))
    args = data["arguments"]
    frames = []
    for values in args.pop("frames"):
        values["mobility"] = Mobility(**values["mobility"])
        for name in ("tangent", "axle", "point", "hub", "response_x", "response_y", "response_t",
                     "spin_axis", "moment_x"):
            values[name] = tuple(values[name])
        values["elastic_frame"] = tuple(tuple(row) for row in values["elastic_frame"])
        frames.append(ContactFrame(**values))
    result = advance_drivetrain(**args, frames=tuple(frames), config=config, rear_config=config, suspension=system)
    target = finite_contact_system(system, result.velocity, result.angular, args["dt"])
    impulse_error = args["dt"] * max(abs(sum(force * (new[a]-old[a]) for force, new, old in
        zip(result.suspension.axial_force, target.gradients, result.suspension_system.gradients))) for a in range(6))
    assert impulse_error < 1e-12
    assert result.normal_residual < 1e-10
    assert abs(result.suspension.energy_residual) < 1e-12
    assert all(force > 0. for force in result.suspension.axial_force)
    assert target.touching == (True,) * 4
