import inspect
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
import tire_drivetrain
import wheel_dynamics
from physics.tcs_probe import run_trial
original = wheel_dynamics._solve_rolling_force
wheel_dynamics._bracket_root = original
source = inspect.getsource(wheel_dynamics._solve_force)
source = source.replace('def _solve_force(', 'def _solve_safeguarded_force(').replace('jacobian=None):', 'jacobian=None, force_bound=None):')
needle = '''            if math.hypot(new_rx, new_ry) < error:
                fx, fy = candidate_x, candidate_y
                break'''
replacement = '''            if math.hypot(new_rx, new_ry) < error:
                if rx * new_rx + ry * new_ry < 0.:
                    ca, cb, cc, cd = jacobian(candidate_x, candidate_y)
                    if rx * (ca * dx + cb * dy) + ry * (cc * dx + cd * dy) <= 0.:
                        return _bracket_root(residual, jacobian, force_bound, tolerance, (fx, fy))
                fx, fy = candidate_x, candidate_y
                break'''
assert needle in source
source = source.replace('            raise ArithmeticError(f"轮胎隐式积分不收敛：残差 {error:.6g} N")',
    '            return _bracket_root(residual, jacobian, force_bound, tolerance, (fx, fy))')
exec(source, wheel_dynamics.__dict__)
tire_drivetrain._solve_rolling_force = lambda residual, jacobian, grip, tolerance=.001, initial=(0.,0.): wheel_dynamics._solve_safeguarded_force(residual, tolerance, initial, jacobian, grip)
if '--tests' in sys.argv:
    import pytest
    raise SystemExit(pytest.main(['-q','tests/test_tcs_probe.py','tests/test_drivetrain_jacobian.py','tests/test_tire_drivetrain.py','tests/test_tire_shaft.py']))
for enabled in (False, True):
    summary, rows = run_trial('airborne-recontact', enabled, 2.)
    print('PASS', enabled, summary['recontact_counts'], [rows[-1][f'state.wheel_dynamics.{i}.sample_support'] for i in range(4)])
