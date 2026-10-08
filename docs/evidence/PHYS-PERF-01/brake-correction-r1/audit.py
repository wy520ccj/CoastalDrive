import ast
import hashlib
import json
import math
import sys
import types
import time
from dataclasses import fields, is_dataclass, replace
from pathlib import Path

root = Path(__file__).resolve().parents[4]
folder = Path(__file__).resolve().parent
sys.path[:0] = [str(root / name) for name in ('src', 'tools', 'tests')] + [str(folder), str(folder.parent / "joint-native-r1")]
import _joint_native_old as old
import tire_drivetrain

source = (folder.parent / 'joint-native-r1/original-tire_drivetrain.py').read_text(encoding='utf-8')
baseline = types.ModuleType('_joint_native_original')
sys.modules[baseline.__name__] = baseline
exec(compile(source, '6d58e9a-tire-original', 'exec'), baseline.__dict__)
for node in ast.parse(source).body:
    if isinstance(node, ast.ImportFrom) and node.module == 'mechanical_kernels':
        for name in node.names:
            baseline.__dict__[name.asname or name.name] = getattr(old, name.name)
baseline.contact_jacobian = lambda *args: old.tire_contact_jacobian(*args, math.hypot)
baseline.combined_force = lambda *args: old.tire_combined_force(*args, math.hypot)
baseline.energy_terms = old.tire_energy_terms
baseline._solve_rolling_force = lambda residual, jacobian, grip, tolerance=.001, initial=(0., 0.): old.rolling_force_solution(
    residual, jacobian, grip, tolerance, initial, math.hypot)

def hex_tree(value):
    if is_dataclass(value):
        return {field.name: hex_tree(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, (tuple, list)):
        return [hex_tree(item) for item in value]
    return value

def source_hashes():
    paths = [root / 'src/mechanical_kernels.c', root / 'src/tire_drivetrain.py',
             next((root / 'src').glob('mechanical_kernels.*.pyd'))]
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

before = source_hashes()
counts = {'complete_steps': 0, 'loaded_force_calls': 0, 'wheel_residual_calls': 0, 'suspension_residual_calls': 0, 'bench_cases': 0, 'brake_correction_calls': 0}
advance = tire_drivetrain.advance_drivetrain
loaded = tire_drivetrain.loaded_wheel_force_solution
wheel_residual = tire_drivetrain.wheel_residuals
suspension_residual = tire_drivetrain.suspension_residuals
timing = {'old_seconds': 0., 'new_seconds': 0.}

def counted_loaded(*args):
    counts['loaded_force_calls'] += 1
    return loaded(*args)

def counted_wheel(*args):
    counts['wheel_residual_calls'] += 1
    return wheel_residual(*args)

def counted_suspension(*args):
    counts['suspension_residual_calls'] += 1
    return suspension_residual(*args)

from shaft_transmission import brake_increment, shaft_brake_response, synchronizer_brake_response
shared_builder = tire_drivetrain.shared_map_coefficients
load_builder = tire_drivetrain.load_coefficients
wheel_builder = tire_drivetrain.wheel_map_coefficients
brake_correction = tire_drivetrain.wheel_brake_correction
shared_inputs, load_inputs, wheel_inputs = {}, {}, {}

def record_shared(*args):
    result = shared_builder(*args)
    shared_inputs[result] = args
    return result

def record_load(*args):
    result = load_builder(*args)
    load_inputs[result] = args
    return result

def record_wheel(*args):
    result = wheel_builder(*args)
    wheel_inputs[result] = (args, shared_inputs[args[0]], load_inputs[args[1]])
    return result

def audited_brake(packet, state, forces, branch_index, port_index):
    inputs, shared, loads = wheel_inputs[packet]
    _owner, _load, branches, gradients, brakes = inputs
    _branch, mc, ml, _response, wheels, local, _plans, (mg, plans) = branches[branch_index]
    ports, dt, hard = shared[4], shared[9], shared[13]
    responses = loads[0]
    corrections = []
    for wheel in range(4):
        rb = wheels[wheel][2]
        direction = tuple(old.dot(g, rb) for g in ports)
        if hard:
            dc, dg, dl, _db = shaft_brake_response(direction, local[0], plans[port_index])
        else:
            dc, dg, _db = synchronizer_brake_response(direction, plans[port_index])
            dl = 0.
        corrections.append(tuple(rb[a] - dc * mc[a] - dg * mg[a] - dl * ml[a] for a in range(9)))
    matrix = tuple(tuple(old.dot(g, response) for response in corrections) for g in gradients)
    delta = brake_increment(matrix, tuple(old.dot(g, state) for g in gradients),
        tuple(f[2] for f in forces), brakes, dt, tuple(old.dot(gradients[i], responses[i][2]) for i in range(4)))
    expected = tuple((fx, fy, brake + value) for (fx, fy, brake), value in zip(forces, delta))
    actual = brake_correction(packet, state, forces, branch_index, port_index)
    assert hex_tree(expected) == hex_tree(actual), (counts, branch_index, port_index, hex_tree(expected), hex_tree(actual))
    counts['brake_correction_calls'] += 1
    return actual

tire_drivetrain.shared_map_coefficients = record_shared
tire_drivetrain.load_coefficients = record_load
tire_drivetrain.wheel_map_coefficients = record_wheel
tire_drivetrain.wheel_brake_correction = audited_brake

def audited(*args, **kwargs):
    started = time.perf_counter()
    expected = baseline.advance_drivetrain(*args, **kwargs)
    timing['old_seconds'] += time.perf_counter() - started
    started = time.perf_counter()
    actual = advance(*args, **kwargs)
    timing['new_seconds'] += time.perf_counter() - started
    assert hex_tree(actual) == hex_tree(expected), counts
    counts['complete_steps'] += 1
    shared_inputs.clear()
    load_inputs.clear()
    wheel_inputs.clear()
    return actual

tire_drivetrain.loaded_wheel_force_solution = counted_loaded
tire_drivetrain.wheel_residuals = counted_wheel
tire_drivetrain.suspension_residuals = counted_suspension
tire_drivetrain.advance_drivetrain = audited
import vehicle_tires
vehicle_tires.advance_drivetrain = audited
from test_rotor_transport import CONFIG, TENSOR, frames
from test_tire_drivetrain import ENGINE_AXIS, ENGINE_INERTIA

for share in (0., .5, 1.):
    damping = (20. if share else 0., 20. if share < 1 else 0., 20. if 0 < share < 1 else 0.)
    for compliance in (False, True):
        config = replace(CONFIG, front_drive_share=share, tire_compliance=compliance,
                         differential_damping=damping,
                         differential_capacity=tuple(80. if value else 0. for value in damping))
        for mode in ('engaged', 'neutral', 'synchronizing'):
            for sign in (-1, 1):
                ratio = 0. if mode == 'neutral' else sign * 12.
                audited((.3, sign * 12., .1), (.12, -.08, .2), (36., 39., 33., 46.), 500.,
                    frames(20., 12., (0., 300., 5500., 5886.)), ((.001, -.0002),) * 4,
                    80., 300., ratio, (100., 300., 50., 0.), config, config, 1 / 240,
                    inverse_inertia=TENSOR, engine_inertia=ENGINE_INERTIA, engine_axis=ENGINE_AXIS,
                    engine_drag=.12, efficiency=.88, shaft_omega=300., shaft_inertia=.04,
                    shaft_axis=ENGINE_AXIS, synchronizing=mode == 'synchronizing',
                    synchronizer_capacity=20. if mode == 'synchronizing' else 0.)
                counts['bench_cases'] += 1

from physics.tcs_probe import run_trial
run_trial('airborne-recontact', False, 2.)
from simulation import Simulation, Control
from vehicle_designs import GR86_DESIGN
from driver_assist import GAME_INPUT
sim = Simulation(17, track='coastal', traffic_count=8, config=GR86_DESIGN, input_config=GAME_INPUT)
try:
    for tick in range(16):
        sim.step(Control(throttle=.3))
finally:
    sim.close()
after = source_hashes()
assert before == after
report = {'baseline': '6d58e9a original Python + independent strict C DLL',
          'all_full_step_fields_hex_and_world_references_equal': True,
          'counts': counts, 'paired_step_timing_diagnostic_only': timing, 'source_sha_start': before, 'source_sha_end': after,
          'scope': '一次功能组旧/新对照；不重复T1/种子/48拍/profile，非FPS证据。'}
(folder / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
