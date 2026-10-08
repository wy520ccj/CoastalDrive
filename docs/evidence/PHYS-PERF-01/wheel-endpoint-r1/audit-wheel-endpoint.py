import hashlib
import inspect
import json
import math
import sys
import types
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=root/'logs/physics/PHYS-PERF-01'
sys.path[:0]=[str(root/'src'),str(root/'tools'),str(root/'tests'),str(folder/'wheel-solver-baseline')]
import _wheel_solver_old
import tire_drivetrain
baseline=types.ModuleType('_wheel_solver_original');sys.modules[baseline.__name__]=baseline
exec(compile((folder/'wheel-solver-original.py').read_text(encoding='utf-8'),'8deb721-tire-original','exec'),baseline.__dict__)
for name in ('dot','known_state','load_coefficients','mass_coefficients','mass_response_prepared','rotor_coefficients',
             'rotor_spin_prepared','shared_map_coefficients','shared_solution','wheel_load_prepared',
             'wheel_map_coefficients','wheel_map_derivatives','wheel_map_state'):
    baseline.__dict__[name]=getattr(_wheel_solver_old,name)
baseline.contact_force=lambda *args:_wheel_solver_old.tire_contact_force(*args,math.hypot)
baseline.contact_jacobian=lambda *args:_wheel_solver_old.tire_contact_jacobian(*args,math.hypot)
baseline.combined_force=lambda *args:_wheel_solver_old.tire_combined_force(*args,math.hypot)
baseline._solve_rolling_force=lambda residual,jacobian,grip,tolerance=.001,initial=(0.,0.):_wheel_solver_old.rolling_force_solution(residual,jacobian,grip,tolerance,initial,math.hypot)
def legacy_energy_terms(force, previous, deformation, rate, patch, dt, stiffness, damping):
    energy = .5 * stiffness * sum(value * value for value in deformation)
    material = dt * damping * sum(value * value for value in rate)
    road = dt * sum(force[i] * patch[i] for i in range(2))
    numerical = .5 * stiffness * sum((deformation[i] - previous[i]) ** 2 for i in range(2))
    return energy, material, road, numerical

baseline.energy_terms = legacy_energy_terms
counts={'full_calls':0,'native_force_calls':0,'rolling_force_calls':0,'static_force_calls':0,'bench_cases':0,'contact_calls':0,'energy_calls':0,'energy_cases':0}
def hex_tree(value):
    if is_dataclass(value):return {field.name:hex_tree(getattr(value,field.name)) for field in fields(value)}
    if isinstance(value,float):return value.hex()
    if isinstance(value,(tuple,list)):return [hex_tree(item) for item in value]
    return value
import random
from tire_compliance import energy_terms
rng = random.Random(17)
for case in range(512):
    pairs = tuple(tuple(rng.uniform(-1., 1.) * scale for _ in range(2))
                  for scale in (10000., .01, .02, 4., 20.))
    arguments = (*pairs, 1 / (120 if case % 2 else 240), 170000. + case, 850. + case)
    assert hex_tree(energy_terms(*arguments)) == hex_tree(legacy_energy_terms(*arguments)), case
    counts['energy_cases'] += 1

contact = tire_drivetrain.wheel_contact_state
energy = tire_drivetrain.energy_terms
def counted_contact(*args):
    counts['contact_calls'] += 1
    return contact(*args)
def counted_energy(*args):
    counts['energy_calls'] += 1
    return energy(*args)
tire_drivetrain.wheel_contact_state = counted_contact
tire_drivetrain.energy_terms = counted_energy
advance=tire_drivetrain.advance_drivetrain
native=tire_drivetrain.wheel_force_solution
def counted(*args):
    counts['native_force_calls']+=1
    counts['rolling_force_calls' if args[15] else 'static_force_calls']+=1
    return native(*args)
tire_drivetrain.wheel_force_solution=counted
def audited(*args,**kwargs):
    expected=baseline.advance_drivetrain(*args,**kwargs)
    actual=advance(*args,**kwargs)
    assert hex_tree(actual)==hex_tree(expected),(counts,args[:4])
    counts['full_calls']+=1
    return actual
tire_drivetrain.advance_drivetrain=audited
import vehicle_tires
vehicle_tires.advance_drivetrain=audited
from test_rotor_transport import CONFIG,TENSOR,frames
from test_tire_drivetrain import ENGINE_AXIS,ENGINE_INERTIA
for share in (0.,.5,1.):
    damping=(20. if share else 0.,20. if share<1 else 0.,20. if 0<share<1 else 0.)
    config=replace(CONFIG,front_drive_share=share,tire_compliance=True,differential_damping=damping,
                   differential_capacity=tuple(80. if value else 0. for value in damping))
    for mode in ('engaged','neutral','synchronizing'):
        for sign in (-1,1):
            ratio=0. if mode=='neutral' else sign*12.
            audited((.3,sign*12.,.1),(.12,-.08,.2),(36.,39.,33.,46.),500.,frames(20.,12.,(0.,300.,5500.,5886.)),
                ((.001,-.0002),)*4,80.,300.,ratio,(100.,300.,50.,0.),config,config,1/240,
                inverse_inertia=TENSOR,engine_inertia=ENGINE_INERTIA,engine_axis=ENGINE_AXIS,engine_drag=.12,efficiency=.88,
                shaft_omega=300.,shaft_inertia=.04,shaft_axis=ENGINE_AXIS,synchronizing=mode=='synchronizing',
                synchronizer_capacity=20. if mode=='synchronizing' else 0.)
            counts['bench_cases']+=1
    audited((.02,.1,0.),(0.,0.,0.),(.2,)*4,80.,frames(0.,0.),((0.,0.),)*4,20.,300.,12.,(20.,)*4,
        config,config,1/240,inverse_inertia=TENSOR,engine_inertia=.2,engine_axis=ENGINE_AXIS,engine_drag=.12,efficiency=.88,
        shaft_omega=10.,shaft_inertia=.04,shaft_axis=ENGINE_AXIS)
    counts['bench_cases']+=1
from physics.tcs_probe import run_trial
for enabled in (False,True):run_trial('airborne-recontact',enabled,2.)
from simulation import Simulation,Control
from vehicle_designs import GR86_DESIGN
from driver_assist import GAME_INPUT
sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
try:
    for tick in range(24):sim.step(Control(throttle=.3))
finally:sim.close()
dll=next((folder/'wheel-solver-baseline').glob('*.pyd'))
report={'baseline':'8deb721 original Python advance + independent old mechanical DLL; strict fp',
        'baseline_dll_sha256':hashlib.sha256(dll.read_bytes()).hexdigest(),'all_full_step_hex_and_references_equal':True,
        'counts':counts,'scope':'轮端初值/制动反力、末速度本构和胎体能量功能组的一次旧/新对照；不重复T1/种子/48拍/profile。'}
(folder/'wheel-endpoint-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
