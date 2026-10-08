import inspect
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
import tire_drivetrain
import wheel_dynamics
from physics.tcs_probe import run_trial

source = inspect.getsource(wheel_dynamics._solve_force)
old = '''        for exponent in range(12):
            scale = 0.5 ** exponent
            candidate_x, candidate_y = fx - scale * dx, fy - scale * dy
            new_rx, new_ry = residual(candidate_x, candidate_y)
            if math.hypot(new_rx, new_ry) < error:
                fx, fy = candidate_x, candidate_y
                break
        else:
            raise ArithmeticError(f"轮胎隐式积分不收敛：残差 {error:.6g} N")'''
new = '''        best = error
        point = None
        for exponent in range(12):
            scale = 0.5 ** exponent
            candidate_x, candidate_y = fx - scale * dx, fy - scale * dy
            new_rx, new_ry = residual(candidate_x, candidate_y)
            candidate_error = math.hypot(new_rx, new_ry)
            if candidate_error < best:
                best = candidate_error
                point = candidate_x, candidate_y
            if candidate_error < tolerance:
                return candidate_x, candidate_y, candidate_error
        if point is None:
            raise ArithmeticError(f"轮胎隐式积分不收敛：残差 {error:.6g} N")
        fx, fy = point'''
assert old in source
exec(source.replace(old, new), wheel_dynamics.__dict__)
tire_drivetrain._solve_force = wheel_dynamics._solve_force
summary, rows = run_trial('airborne-recontact', True, 1.)
print(summary)
