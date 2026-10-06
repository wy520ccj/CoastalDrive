import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
from simulation import Control, Simulation
from driver_assist import GAME_INPUT
from vehicle_config import CAR
from vehicle_state import FIXED_DT

sim = Simulation()
for _ in range(240):
    sim.step(Control())
for _ in range(240):
    sim.step(Control(throttle=1))
train = sim.player.powertrain
accept = train.accept_step
rows = []

def observe(result, dt):
    inertia_impulse = CAR.input_shaft_inertia * (result.shaft_omega - train.shaft_omega)
    port_impulse = dt * (result.clutch_torque - result.gear_reaction)
    rows.append({'tick_before_step': sim.snapshot().tick,
        'dt': dt, 'capacity': train.capacity, 'clutch_torque': result.clutch_torque,
        'gear_reaction': result.gear_reaction, 'gear_loss_torque': result.gear_loss_torque,
        'ratio': train.mechanical_ratio, 'drive_torque': result.drive_torque,
        'shaft_omega_before': train.shaft_omega, 'shaft_omega_after': result.shaft_omega,
        'shaft_energy_delta_J': .5 * CAR.input_shaft_inertia * (result.shaft_omega**2-train.shaft_omega**2),
        'shaft_impulse_error_N_m_s': inertia_impulse-port_impulse})
    accept(result, dt)

train.accept_step = observe
for _ in range(round(1/GAME_INPUT.brake_rise/FIXED_DT)):
    sim.step(Control(throttle=1, brake=1))
record = {'status':'actual unchanged native braking trajectory', 'rows':rows,
    'end_speed':sim.snapshot().player.speed,
    'end_brake':sim.snapshot().player.brake,
    'max_shaft_impulse_error_N_m_s':max(abs(row['shaft_impulse_error_N_m_s']) for row in rows),
    'end_capacity':train.capacity, 'end_drive_torque':train.drive_torque}
(Path(__file__).parent/'native-facts.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='rows'}))
print(json.dumps(rows[-2:]))
sim.close()
