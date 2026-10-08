import inspect
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
import tire_drivetrain
import wheel_dynamics
from physics.tcs_probe import run_trial
source = inspect.getsource(wheel_dynamics._solve_force)
start = source.index('        for exponent in range(12):')
stop = source.index('    raise ArithmeticError(f"轮胎隐式积分超过20次迭代', start)
replacement = '''        low, high = 0., 1.
        scale = 1.
        best = error
        point = None
        bracketed = False
        for exponent in range(12):
            candidate_x, candidate_y = fx - scale * dx, fy - scale * dy
            new_rx, new_ry = residual(candidate_x, candidate_y)
            candidate_error = math.hypot(new_rx, new_ry)
            if candidate_error < tolerance:
                return candidate_x, candidate_y, candidate_error
            if candidate_error < best:
                best, point = candidate_error, (candidate_x, candidate_y)
            if rx * new_rx + ry * new_ry < 0.:
                bracketed = True
                high = scale
            elif bracketed:
                low = scale
            elif candidate_error < error:
                break
            else:
                high = scale
            scale = (low + high) / 2
        if point is None:
            raise ArithmeticError(f"轮胎隐式积分不收敛：残差 {error:.6g} N")
        fx, fy = point
'''
exec(source[:start] + replacement + source[stop:], wheel_dynamics.__dict__)
tire_drivetrain._solve_force = wheel_dynamics._solve_force
summary, rows = run_trial('airborne-recontact', True, 1.)
print(summary)
