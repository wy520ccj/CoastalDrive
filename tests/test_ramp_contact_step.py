"""真实浅坡第889拍的共同末状态；固定世界中的棱接触保留原精度。"""

import json
from pathlib import Path

from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import TransformState, Vec3

from simulation import Simulation
from suspension import SuspensionInput
from suspension_kinematics import SupportPlane, finite_contact_system
from tire_coupling import ContactFrame
from tire_drivetrain import advance_drivetrain
from vehicle_config import CAR
from vehicle_parameters import load_vehicle_config
from vehicle_suspension import WorldSurface
from wheel_dynamics import Mobility


def test_relative_world_edge_query_preserves_small_geometry_after_translation():
    results = []
    for x, y in ((0., 0.), (4096., 8192.)):
        world = BulletWorld()
        box = BulletRigidBodyNode("edge")
        shape = BulletBoxShape(Vec3(5., 3., .25))
        shape.setMargin(0.)
        box.addShape(shape)
        box.setTransform(TransformState.makePos(Vec3(x, y, -.25)))
        world.attachRigidBody(box)
        chassis = BulletRigidBodyNode("chassis")
        chassis.setTransform(TransformState.makePos(Vec3(x, y, 1.)))
        surface = WorldSurface((), 0., ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)),
                               (x, y, 1.), .33, .6, .205, .01, (1., 0., 0.),
                               world=world, chassis=chassis)
        results.append(surface.relative_entry((.2, 3.123456789123, -.1),
                                              (.2, 3.123456789123, -1.4), (1., 0., 0.)))
    assert results[0] is not None
    assert results[1] == results[0]


def _tuples(value):
    if isinstance(value, list):
        return tuple(_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuples(item) for key, item in value.items()}
    return value


def test_captured_ramp_edge_step_has_one_conjugate_end_state():
    folder = Path(__file__).resolve().parents[1] / "docs/evidence/PHYS-DESIGN-01"
    data = _tuples(json.loads((folder / "ramp-step-input.json").read_text(encoding="utf-8")))
    config = load_vehicle_config(folder / data["config_file"], CAR)
    rear = load_vehicle_config(folder / data["rear_config_file"], CAR)
    sim = Simulation(data["seed"], track=data["track"])
    try:
        sim.player._chassis.setTransform(TransformState.makePos(Vec3(*data["player"]["position"])))
        planes = tuple(SupportPlane(**{key: value for key, value in plane.items() if key != "surface"},
                                   surface=WorldSurface(**plane["surface"], world=sim._world,
                                                        chassis=sim.player._chassis,
                                                        envelope=sim.player.suspension.envelope))
                       if plane is not None else None for plane in data["planes"])
        system = SuspensionInput(**data["suspension"], config=config, kinematics=planes)
        args = data["arguments"]
        frames = tuple(ContactFrame(**{key: value for key, value in frame.items() if key != "mobility"},
                                    mobility=Mobility(**frame["mobility"])) for frame in args.pop("frames"))
        result = advance_drivetrain(**args, frames=frames, config=config, rear_config=rear, suspension=system)
        target = finite_contact_system(system, result.velocity, result.angular, args["dt"])
        impulse = args["dt"] * max(abs(sum(force * (new[a] - old[a]) for force, new, old in
            zip(result.suspension.axial_force, target.gradients, result.suspension_system.gradients))) for a in range(6))
        assert impulse < 1e-12
        assert result.normal_residual < 1e-10
        assert abs(result.suspension.energy_residual) < 1e-12
        assert target.touching == (True,) * 4
        assert result.sweeps <= 20
    finally:
        sim.close()
