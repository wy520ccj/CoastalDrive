import inspect
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
import tire_drivetrain
from tire_properties import tire_grip
from physics.tcs_probe import run_trial
original = tire_drivetrain._solve_force

def bounded(residual, tolerance=.001, initial=(0., 0.), jacobian=None):
    scope = inspect.currentframe().f_back.f_locals
    if 'frame' not in scope or not scope['car'].tire_compliance:
        return original(residual, tolerance, initial, jacobian)
    limit = tire_grip(scope['frame'].load, scope['frame'].mu, scope['car'])
    fx, fy = (max(-limit, min(limit, value)) for value in initial)
    low, high = -limit, limit
    for iteration in range(20):
        lower_y, upper_y = -limit, limit
        for lateral_iteration in range(20):
            rx, ry = residual(fx, fy)
            a, b, c, d = jacobian(fx, fy)
            if abs(ry) < tolerance:
                break
            if ry > 0:
                upper_y = fy
            else:
                lower_y = fy
            y = fy - ry / d
            fy = y if lower_y < y < upper_y else (lower_y+upper_y)/2
        else:
            raise ArithmeticError(f'lateral Newton >20: {ry}')
        rx, ry = residual(fx, fy)
        error = __import__('math').hypot(rx, ry)
        if error < tolerance:
            return fx, fy, error
        if rx > 0:
            high = fx
        else:
            low = fx
        a, b, c, d = jacobian(fx, fy)
        x = fx - rx / (a-b*c/d)
        end_x = x if low < x < high else (low+high)/2
        fx = end_x
    raise ArithmeticError(f'bounded Newton >20: {error}, bounds={low}/{high}, point={fx}/{fy}')

tire_drivetrain._solve_force = bounded
summary, rows = run_trial('airborne-recontact', True, 1.)
print(summary)
