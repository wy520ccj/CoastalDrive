import copy
import inspect
import json
import math
import sys
import traceback
from dataclasses import asdict
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
import tire_drivetrain
from physics.tcs_probe import run_trial

original = tire_drivetrain._solve_force
out = root / 'logs/physics/PHYS-DESIGN-01-wall/recontact-capture.json'

def capture(residual, tolerance=.001, initial=(0., 0.), jacobian=None):
    try:
        return original(residual, tolerance, initial, jacobian)
    except ArithmeticError as error:
        scope = inspect.currentframe().f_back.f_locals
        tb = error.__traceback__
        while tb.tb_next:
            tb = tb.tb_next
        last = tb.tb_frame.f_locals
        result = {'error': str(error), 'initial': initial, 'last': [last['fx'], last['fy']],
                  'tolerance': tolerance, 'wheel': scope['i'],
                  'frame': asdict(scope['frame']), 'car': asdict(scope['car'])}
        parent = inspect.currentframe().f_back.f_back.f_locals
        result['sweep'] = parent['sweep']
        result['forces'] = parent['forces']
        outer = inspect.getclosurevars(residual).nonlocals
        contact_scope = inspect.getclosurevars(outer['contact']).nonlocals
        result['deformation'] = contact_scope['deformations'][scope['i']]
        result['rolling'] = contact_scope['rolling'][scope['i']]
        trials = []
        for label, point in [('initial', initial), ('last', (last['fx'], last['fy'])), ('zero', (0., 0.)), ('grip', (result['frame']['load'] * result['frame']['mu'], 0.))]:
            rx, ry = residual(*point)
            j = jacobian(*point)
            h = .001
            px, py = residual(point[0]+h, point[1])
            nx, ny = residual(point[0]-h, point[1])
            qx, qy = residual(point[0], point[1]+h)
            mx, my = residual(point[0], point[1]-h)
            row = {'label': label, 'point': point, 'residual': [rx, ry], 'jacobian': j,
                   'kinematics': scope['derivatives'](*point),
                   'finite_jacobian': [(px-nx)/(2*h), (qx-mx)/(2*h), (py-ny)/(2*h), (qy-my)/(2*h)]}
            try:
                row['solution'] = original(residual, tolerance, point, jacobian)
            except ArithmeticError as trial_error:
                row['error'] = str(trial_error)
            trials.append(row)
        result['trials'] = trials
        result['longitudinal_scan'] = [
            {'fx': fx, 'residual': residual(fx, 207.4), 'jacobian': jacobian(fx, 207.4)}
            for fx in range(-40000, 40001, 1000)]
        result['successful_initials'] = []
        for fx in range(-40000, 40001, 1000):
            try:
                solution = original(residual, tolerance, (fx, 207.4), jacobian)
                result['successful_initials'].append([fx, solution])
            except ArithmeticError:
                pass
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        raise

tire_drivetrain._solve_force = capture
run_trial('airborne-recontact', True, 1.)
