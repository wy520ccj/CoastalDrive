"""四接触共享车体的总动量/能量与独立轮轴干式制动约束。"""

import math
from dataclasses import replace

import pytest

from tire_compliance import deformation_frame
from tire_coupling import ContactFrame, advance_coupled, cross, dot
from vehicle_config import CAR
from wheel_dynamics import Mobility

CONFIG = replace(CAR, tire_compliance=True)
INERTIA = (1900., 510., 2200.)


def contact_frames(loads, mu):
    frames = []
    for i, (x, y) in enumerate(((-.84, 1.1), (.84, 1.1), (-.84, -1.1), (.84, -1.1))):
        tangent, axle = (0., 1., 0.), (1., 0., 0.)
        point = (x, y, -.42)
        hub = (x, y, -.42 + CAR.wheel_radius)
        moment_x, moment_y = cross(hub, tangent), cross(point, axle)
        rx, ry, rt = (tuple(vector[a] / INERTIA[a] for a in range(3)) for vector in (moment_x, moment_y, axle))
        mobility = Mobility(1 / CAR.mass + dot(moment_x, rx), dot(moment_x, ry), dot(moment_x, rt),
                            1 / CAR.mass + dot(moment_y, ry), dot(moment_y, rt), dot(axle, rt))
        frames.append(ContactFrame(0., loads[i] > 0, loads[i], mu, tangent, axle, point, hub,
                                   mobility, deformation_frame(tangent, (0., 0., 1.)), rx, ry, rt))
    return frames


@pytest.mark.parametrize("speed,side,yaw,omega,drive,brake", [
    (20., .3, .1, 20.2 / CAR.wheel_radius, 300., 0.),
    (-12., -.4, -.1, -12. / CAR.wheel_radius, -200., 500.),
    (0., 0., 0., 0., 300., 0.),
    (0., 0., 0., 0., 0., 1200.),
])
@pytest.mark.parametrize("loads", [(2943.,) * 4, (0., 300., 5500., 5886.), (0.,) * 4])
def test_total_four_wheel_energy_momentum_and_brake_constraints(speed, side, yaw, omega, drive, brake, loads):
    h = 1 / 240
    velocity, angular = (side, speed, 0.), (.03, -.02, yaw)
    deformation = ((.005, -.003), (-.006, .004), (.007, .002), (-.004, -.006))
    drives, brakes = (0., 0., drive / 2, drive / 2), (brake,) * 4
    frames = contact_frames(loads, .45)
    rear = replace(CONFIG, lateral_stiffness=CONFIG.rear_lateral_stiffness)
    steps = advance_coupled(velocity, angular, [omega] * 4, frames, deformation, drives, brakes, CONFIG, rear, h)
    force, torque = [0.] * 3, [0.] * 3
    for i, step in enumerate(steps):
        frame = frames[i]
        for a in range(3):
            force[a] += frame.tangent[a] * step.fx + frame.axle[a] * step.fy
            torque[a] += (cross(frame.hub, frame.tangent)[a] * step.fx
                          + cross(frame.point, frame.axle)[a] * step.fy
                          + frame.axle[a] * (drives[i] - step.brake_torque))
    end_velocity = tuple(velocity[a] + h * force[a] / CAR.mass for a in range(3))
    end_angular = tuple(angular[a] + h * torque[a] / INERTIA[a] for a in range(3))
    kinetic_change = (.5 * CAR.mass * (dot(end_velocity, end_velocity) - dot(velocity, velocity))
                      + .5 * sum(INERTIA[a] * (end_angular[a]**2 - angular[a]**2) for a in range(3))
                      + .5 * CAR.wheel_inertia * sum(s.omega**2 - omega**2 for s in steps))
    elastic_change = sum(s.elastic_energy for s in steps) - .5 * CONFIG.tire_contact_stiffness * sum(
        value * value for strain in deformation for value in strain)
    mechanical_numerical = (.5 * h**2 * dot(force, force) / CAR.mass
                            + .5 * h**2 * sum(torque[a]**2 / INERTIA[a] for a in range(3))
                            + .5 * CAR.wheel_inertia * sum((s.omega - omega)**2 for s in steps))
    expected = sum(h * (drives[i] - s.brake_torque) * s.relative_omega
                   - s.material_dissipation - s.road_dissipation - s.elastic_numerical_dissipation
                   for i, s in enumerate(steps)) - mechanical_numerical
    assert kinetic_change + elastic_change == pytest.approx(expected, abs=3e-9)
    for i, step in enumerate(steps):
        frame = frames[i]
        hub_speed = tuple(end_velocity[a] + cross(end_angular, frame.hub)[a] for a in range(3))
        assert step.vx == pytest.approx(dot(hub_speed, frame.tangent), abs=1e-12)
        assert step.body_omega == pytest.approx(dot(end_angular, frame.axle), abs=1e-12)
        assert CAR.wheel_inertia * (step.omega - omega) == pytest.approx(h * (
            drives[i] - step.brake_torque - CAR.wheel_radius * step.fx), abs=1e-12)
        assert abs(step.brake_torque) <= brakes[i]
        assert step.brake_torque * step.relative_omega >= -1e-7
        assert step.residual < .001
        assert step.road_dissipation >= -1e-7
        assert all(math.isfinite(value) for value in (step.fx, step.fy, step.omega, step.elastic_energy))
