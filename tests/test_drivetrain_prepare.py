"""原生机械装配与冻结数值参考逐位对照，覆盖实体轴与旧八维边界。"""

import math
import random
import struct
from dataclasses import replace

import pytest
from drivetrain_prepare_reference import reference_prepare
from mechanical_kernels import drivetrain_prepare, mass_response_prepared, rotor_spin_prepared

from rotor_dynamics import cross
from tire_coupling import ContactFrame
from vehicle_config import CAR
from wheel_dynamics import Mobility


def bits(value):
    if isinstance(value, float):
        return struct.pack('d', value)
    if isinstance(value, tuple):
        return tuple(bits(item) for item in value)
    return value


@pytest.mark.parametrize('shaft', [False, True])
@pytest.mark.parametrize('rotor', [False, True])
@pytest.mark.parametrize('share', [0., .35, 1.])
@pytest.mark.parametrize('downstream', [False, True])
def test_native_prepare_preserves_constraints_inertia_and_free_state(shaft, rotor, share, downstream):
    rng = random.Random(1701)
    config = replace(CAR, front_drive_share=share, wheel_rotor_transport=rotor)

    def vector(scale=1.):
        return tuple(rng.uniform(-scale, scale) for _ in range(3))

    for sample in range(32):
        frames = []
        for index in range(4):
            angle = rng.uniform(-.6, .6)
            axis = (math.cos(angle), -math.sin(angle), 0.)
            tangent = (math.sin(angle), math.cos(angle), 0.)
            point = (-.8 if index % 2 == 0 else .8, 1.3 if index < 2 else -1.3, -.4)
            radius = rng.uniform(.28, .34)
            moment = tuple(cross(point, tangent)[a] - radius * axis[a] for a in range(3))
            frames.append(ContactFrame(angle, True, 3000., .9, tangent, axis, point, point,
                Mobility(1., 0., 0., 1., 0., 1.), None, (0.,)*3, (0.,)*3, (0.,)*3,
                axis, radius, moment))
        dimensions = 9 if shaft else 8
        inverse = ((.001, -.0001, .0002), (-.0001, .002, .0001), (.0002, .0001, .0015))
        args = (vector(3.), tuple(rng.uniform(-300., 300.) for _ in range(4)), rng.uniform(-200., 800.),
                tuple(frames), rng.uniform(-100., 300.), config, (0., -12., 9.)[sample % 3], inverse,
                1/240, vector(), .17, tuple(vector(10.) for _ in range(4)), .02,
                rng.uniform(-300., 300.) if shaft else None, .019, vector() if shaft else None,
                vector(100.) if downstream else (), (.01, .015, .02), tuple(vector() for _ in range(3)))
        expected, actual = reference_prepare(*args), drivetrain_prepare(*args)
        assert bits(actual[:14]) == bits(expected[:14])
        assert bits(actual[16]) == bits(expected[16])
        for probe in (expected[0], *(tuple(float(i == j) for i in range(dimensions)) for j in range(dimensions))):
            assert bits(mass_response_prepared(actual[14], probe)) == bits(mass_response_prepared(expected[14], probe))
            assert bits(rotor_spin_prepared(actual[15], probe)) == bits(rotor_spin_prepared(expected[15], probe))


def test_native_prepare_reports_invalid_inertia_and_dimensions():
    with pytest.raises(TypeError):
        drivetrain_prepare()
    with pytest.raises(ZeroDivisionError):
        drivetrain_prepare((0.,)*3, (0.,)*4, 0., (), 0., replace(CAR, wheel_inertia=0.),
            0., ((1., 0., 0.),)*3, 1/240, (1., 0., 0.), .1, ((0.,)*3,)*4, 0.,
            None, None, None, (), (), ())
    with pytest.raises(ValueError, match='维数'):
        drivetrain_prepare((0.,)*2, (0.,)*4, 0., (), 0., CAR,
            0., ((1., 0., 0.),)*3, 1/240, (1., 0., 0.), .1, ((0.,)*3,)*4, 0.,
            None, None, None, (), (), ())
