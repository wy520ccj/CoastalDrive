import inspect
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
import tire_drivetrain
import wheel_dynamics
from physics.tcs_probe import run_trial
source = inspect.getsource(wheel_dynamics._solve_force)
needle = '''            if math.hypot(new_rx, new_ry) < error:
                fx, fy = candidate_x, candidate_y
                break'''
replacement = '''            if math.hypot(new_rx, new_ry) < error:
                if jacobian is not None and rx * new_rx + ry * new_ry < 0.:
                    ca, cb, cc, cd = jacobian(candidate_x, candidate_y)
                    if rx * (ca * dx + cb * dy) + ry * (cc * dx + cd * dy) <= 0.:
                        continue
                fx, fy = candidate_x, candidate_y
                break'''
assert needle in source
exec(source.replace(needle, replacement), wheel_dynamics.__dict__)
tire_drivetrain._solve_rolling_force = lambda residual, jacobian, grip, tolerance=.001, initial=(0.,0.): wheel_dynamics._solve_force(residual, tolerance, initial, jacobian)
summary, rows = run_trial('airborne-recontact', True, 2.)
print('PASS', summary['recontact_counts'], [rows[-1][f'state.wheel_dynamics.{i}.sample_support'] for i in range(4)])
