import inspect
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
import tire_drivetrain
from physics.tcs_probe import run_trial
source = inspect.getsource(tire_drivetrain.advance_drivetrain)
needle = '                guess = ((d * rhs_x - b * rhs_y) / determinant, (a * rhs_y - c * rhs_x) / determinant)'
replacement = needle + '''
                vx, _vy, slip, gradients = derivatives(*guess)
                slopes = tuple(value / max(abs(vx), car.slip_speed) for value in stiffnesses)
                patch = tuple(slip[a] + car.tire_contact_stiffness * deformations[i][a] / impedance - guess[a] / impedance for a in range(2))
                matrix = tuple(tuple(float(a == b) - slopes[a] * (
                    gradients[b][a] - float(a == b) / impedance) for b in range(2)) for a in range(2))
                a, b = matrix[0]
                c, d = matrix[1]
                rx, ry = tuple(guess[a] - slopes[a] * patch[a] for a in range(2))
                determinant = a * d - b * c
                guess = (guess[0] - (d * rx - b * ry) / determinant, guess[1] - (a * ry - c * rx) / determinant)
                if i == 2 and guess[0] > 10000:
                    print('RECENTER', guess, vx, slip, gradients, flush=True)
'''
assert needle in source
exec(source.replace(needle, replacement), tire_drivetrain.__dict__)
import vehicle_tires
vehicle_tires.advance_drivetrain = tire_drivetrain.advance_drivetrain
summary, rows = run_trial('airborne-recontact', True, 1.)
print(summary)
