"""独立距离场求末端点，核对真实圆角割线虚功和完整机械账。"""

import math
from dataclasses import replace

import numpy as np
import pytest
from test_rotor_transport import CONFIG, TENSOR, frames
from test_tire_drivetrain import audit

from rotor_dynamics import cross
from suspension import SuspensionInput
from suspension_geometry import BoxSurface
from suspension_kinematics import SupportPlane, finite_contact_system
from tire_drivetrain import advance_drivetrain


def independent_length(contact, velocity, angular, dt):
    """Rodrigues末姿态后直接二分Box距离场，不使用生产分段二次求交或差商。"""
    spin = np.asarray(angular) * dt
    theta = np.linalg.norm(spin)
    rotation = np.eye(3)
    if theta:
        x, y, z = spin / theta
        skew = np.array(((0., -z, y), (z, 0., -x), (-y, x, 0.)))
        rotation += math.sin(theta) * skew + (1 - math.cos(theta)) * skew @ skew
    hub = dt * np.asarray(velocity) + rotation @ np.asarray(contact.hub)
    direction = rotation @ np.asarray(contact.direction)
    surface = contact.surface
    matrix, offset = np.asarray(surface.axes), np.asarray(surface.offset)

    def distance(length):
        point = offset + matrix @ (hub + length * direction)
        delta = np.maximum(np.abs(point) - surface.half, 0.)
        return np.linalg.norm(delta) - surface.radius

    low, high = -surface.wheel_radius, surface.reach
    assert distance(low) > 0. and distance(high) < 0.
    for _ in range(70):
        middle = (low + high) / 2
        if distance(middle) > 0.:
            low = middle
        else:
            high = middle
    return (low + high) / 2


@pytest.mark.parametrize("angle", (0., .02, .5, .8))
@pytest.mark.parametrize("speed", (-2., 2.))
@pytest.mark.parametrize("rotation", (0., .4))
def test_curve_and_face_transition_length_has_exact_conjugate_work(angle, speed, rotation):
    half, radius = (.2, 40., .05), .37
    normal = (math.sin(angle), 0., math.cos(angle))
    center = (.2 + radius * normal[0], .3, .05 + radius * normal[2])
    x, y = math.cos(rotation), math.sin(rotation)
    axes = ((x, y, 0.), (-y, x, 0.), (0., 0., 1.))
    offset = (.3, -.1, .2)
    surface = BoxSurface(half, radius, axes, offset, .33, .6)
    hub = tuple(sum(axes[a][b] * (center[a] - offset[a]) for a in range(3)) + (.34 if b == 2 else 0.) for b in range(3))
    world_normal = surface.world_vector(normal)
    contact = SupportPlane(hub, (0., 0., -1.), world_normal, .34, surface)
    system = SuspensionInput((.06,) * 4, (.06,) * 4, ((0.,) * 6,) * 4,
                             (True,) * 4, (normal[2],) * 4, None, (contact,) * 4)
    velocity = surface.world_vector((speed, .5, -.1))
    angular = surface.world_vector((.5, 1.1, -.2))
    dt = 1/120
    effective = finite_contact_system(system, velocity, angular, dt)
    assert all(effective.touching)
    expected = independent_length(contact, velocity, angular, dt)
    change = dt * sum(a * b for a, b in zip(effective.gradients[0], velocity + angular))
    assert change == pytest.approx(expected - contact.length, abs=3e-15)
    # 梯度不是旧切平面；圆角上的法线变化真实进入线/角冲量。
    if angle > .02:
        assert effective.gradients[0][0] != pytest.approx(world_normal[0] / normal[2], abs=1e-5)


@pytest.mark.parametrize("share", (0., .5, 1.))
@pytest.mark.parametrize("dt", (1/120, 1/240))
def test_true_curved_support_preserves_complete_rotor_energy_and_momentum(share, dt):
    config = replace(CONFIG, front_drive_share=share)
    angle = math.degrees(math.atan2(.6, .8))
    contact_frames = frames(angle, 17.)
    normal, direction = (.6, 0., .8), (0., 0., -1.)
    initial = (.064, .047, .067, .05)
    gradients = tuple(tuple(n / .8 for n in normal) + tuple(value / .8 for value in cross(frame.point, normal)) for frame in contact_frames)
    contacts = []
    for i, frame in enumerate(contact_frames):
        center = tuple(frame.point[a] + .33 * normal[a] for a in range(3))
        local_center = (.2 + .37 * normal[0], frame.point[1], .05 + .37 * normal[2])
        surface = BoxSurface((.2, 40., .05), .37, ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)),
                             tuple(local_center[a] - center[a] for a in range(3)), .33, .6)
        length = .4 - initial[i]
        contacts.append(SupportPlane(tuple(center[a] - length * direction[a] for a in range(3)), direction, normal, length, surface))
    system = SuspensionInput(initial, initial, gradients, (True,) * 4, (.8,) * 4, config, tuple(contacts))
    velocity, angular, spins, engine = (.3, 20., -.2), (.04, -.06, .17), (61., 60., 62., 59.), 175.
    deformation, brakes = ((.002, -.001),) * 4, (200., 300., 120., 150.)
    result = advance_drivetrain(velocity, angular, spins, engine, contact_frames, deformation,
        85., 120., 3.2, brakes, config, config, dt, inverse_inertia=TENSOR,
        engine_inertia=.2, engine_axis=(0., 1., 0.), engine_drag=.12, efficiency=.88,
        shaft_omega=180., shaft_inertia=.04, shaft_axis=(0., 1., 0.), suspension=system)
    effective, step = result.suspension_system, result.suspension
    for i, contact in enumerate(contacts):
        expected = .4 - independent_length(contact, result.velocity, result.angular, dt)
        assert step.compression[i] == pytest.approx(expected, abs=1e-13)
    loaded = tuple(replace(frame, load=force / a) for frame, force, a in zip(contact_frames, step.axial_force, effective.alignment))
    audit(result, velocity, angular, spins, engine, loaded, deformation, 85., brakes, config, dt,
          tuple(frame.spin_axis for frame in loaded), ((0.,) * 3,) * 4, shaft=180., normal=(effective, step))
