import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path.cwd()/'src'))
sys.path.insert(0,str(Path.cwd()/'tools'))
from panda3d.core import Vec3
from physics import testbed
from controls import KeyboardController
from driver_assist import GAME_INPUT, SIMULATION_INPUT
from vehicle_designs import GR86_DESIGN
from vehicle_state import FIXED_DT, VehicleCommand
from vehicle import Vehicle
from world_step import advance_world

results = []
for name,input_config in (('old_full_lock_key',GAME_INPUT),('new_wheel_rate_key',SIMULATION_INPUT)):
    world = testbed._world()
    car = Vehicle(world,lambda _x,_y:True,(0,0,.55),config=GR86_DESIGN,input_config=SIMULATION_INPUT)
    keyboard = KeyboardController(input_config)
    try:
        for _ in range(240):
            advance_world(world,[(car,VehicleCommand(brake=1.,gear=0))],substeps=2)
        car._chassis.setLinearVelocity(Vec3(0,100/3.6,0))
        car.tires.initialize_rolling(100/3.6)
        car.powertrain.initialize_rolling(100/3.6)
        keyboard.press('d')
        rows = []
        for tick in range(120):
            if tick==12:
                keyboard.release('d')
            request = keyboard.sample(None,FIXED_DT)
            advance_world(world,[(car,VehicleCommand(steering=request.steering*GR86_DESIGN.steering_degrees,gear=0))],substeps=2)
            state = car.snapshot()
            rows.append({'tick':tick+1,'heading_deg':state.heading,'rack_degrees':state.steering,
                         'speed_mps':state.speed,'position':state.position})
        results.append({'case':name,'tap_seconds':.1,'initial_speed_kmh':100,
                        'max_rack_degrees':max(abs(r['rack_degrees']) for r in rows),
                        'heading_after_one_second':rows[-1]['heading_deg'],'rows':rows})
    finally:
        car.close()
Path('logs/performance/hard-drive-r1/keyboard-tap.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print([{k:v for k,v in r.items() if k!='rows'} for r in results])
