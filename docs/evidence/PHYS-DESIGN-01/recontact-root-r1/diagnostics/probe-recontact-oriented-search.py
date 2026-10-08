import inspect
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
import tire_drivetrain
import wheel_dynamics
from physics.tcs_probe import run_trial
source = inspect.getsource(wheel_dynamics._solve_force)
source = source.replace('if math.hypot(new_rx, new_ry) < error:',
    'if math.hypot(new_rx, new_ry) < tolerance or (math.hypot(new_rx, new_ry) < error and rx * new_rx + ry * new_ry >= 0.):')
exec(source, wheel_dynamics.__dict__)
tire_drivetrain._solve_force = wheel_dynamics._solve_force
summary, rows = run_trial('airborne-recontact', True, 1.)
print(summary)
