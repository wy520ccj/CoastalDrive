"""四轮原生观测对照独立原Python公式，保留转向、离地和轮荷响应。"""

import random

from panda3d.core import Quat, Vec3
from wheel_contact_kernels import wheel_observations

from rotor_dynamics import cross, dot
from tire_forces import slip_state
from tire_properties import tire_grip
from vehicle_designs import GR86_DESIGN
from wheel_geometry import contact_geometry, mechanical_axis


def hex_values(value):
    return tuple(hex_values(item) for item in value) if isinstance(value,tuple) else value.hex()


def test_native_four_wheel_observations_match_original_formulas():
    rng = random.Random(23)
    config = GR86_DESIGN
    for trial in range(1024):
        orientation = Quat()
        orientation.setHpr(Vec3(rng.uniform(-180.,180.),rng.uniform(-25.,25.),rng.uniform(-20.,20.)))
        right,forward = tuple(orientation.getRight()),tuple(orientation.getForward())
        angles = tuple(rng.uniform(-42.,42.) for _ in range(4))
        normals = tuple((rng.uniform(-.3,.3),rng.uniform(-.3,.3),1.) for _ in range(4))
        points = tuple(tuple(rng.uniform(-2.,2.) for _ in range(3)) for _ in range(4))
        velocity = tuple(rng.uniform(-30.,30.) for _ in range(3)) if trial else (0.,0.,0.)
        angular = tuple(rng.uniform(-3.,3.) for _ in range(3)) if trial else (0.,0.,0.)
        omega = tuple(rng.uniform(-100.,100.) for _ in range(4)) if trial else (0.,0.,0.,0.)
        loads = tuple(rng.choice((0.,200.,4000.,6000.)) for _ in range(4))
        frictions = tuple(rng.choice((config.road_friction,config.grass_friction)) for _ in range(4))
        width = config.wheel_width if trial%2 else None
        actual = wheel_observations(right,forward,angles,normals,points,velocity,angular,omega,loads,frictions,
            (config.wheel_radius,width,config.wheel_shoulder_radius,config.wheel_crown_height,
             config.slip_speed,config.mass,config.tire_peak_load_exponent))
        expected = []
        for angle,normal,point,speed,load,mu in zip(angles,normals,points,omega,loads,frictions):
            geometry = {} if width is None else {
                'width':width,'shoulder':config.wheel_shoulder_radius,'crown':config.wheel_crown_height}
            axis,(tangent,lateral,_normal),radius,moment = contact_geometry(
                mechanical_axis(right,forward,angle),normal,point,config.wheel_radius,**geometry)
            vx = dot(velocity,tangent)+dot(angular,moment)
            vy = dot(tuple(velocity[a]+cross(angular,point)[a] for a in range(3)),lateral)
            kappa,alpha = slip_state(vx,vy,speed,radius,config)
            expected.append((axis,radius,speed+dot(angular,axis),vx,vy,kappa,alpha,tire_grip(load,mu,config)))
        assert hex_values(actual)==hex_values(tuple(expected))
