"""只观测原生首拍的实体轴角冲量与轮端反力；不改机械状态。"""
import json
import sys
from dataclasses import replace
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
from driving_modes import DrivingMode
from physics.reference_ab import _create_vehicle, _step
from vehicle_state import VehicleCommand

rows = []
for mode in DrivingMode:
    for share in (0., .5, 1.):
        for direction in (-1, 1):
            config = replace(mode.vehicle_config, front_drive_share=share)
            world, car = _create_vehicle(config)
            train, accept = car.powertrain, car.powertrain.accept_step
            inertias = (config.downstream_inertias[0], config.downstream_inertias[1] if share else 0.,
                        config.downstream_inertias[2] if share < 1 else 0.)

            def observe(result, dt):
                torques = [j*(new-old)/dt for j, new, old in
                           zip(inertias, result.downstream_omega, train.downstream_omega)]
                extra = tuple(-config.final_drive/2 * (share*torques[0]+torques[1]) if i < 2
                              else -config.final_drive/2 * ((1-share)*torques[0]+torques[2]) for i in range(4))
                expected = tuple(result.drive_torque*(share if i < 2 else 1-share)/2+extra[i] for i in range(4))
                error = max(abs(a-b) for a,b in zip(result.wheel_drive_torques, expected))
                assert error < 1e-10
                rows.append({'mode':mode.value,'front_drive_share':share,'direction':direction,'dt':dt,
                             'downstream_inertial_torques_N_m':torques,'wheel_reactions_N_m':extra,
                             'transmission_drive_torque_N_m':result.drive_torque,
                             'actual_wheel_drive_torques_N_m':result.wheel_drive_torques,
                             'max_independent_error_N_m':error})
                accept(result, dt)

            train.accept_step = observe
            try:
                _step(world, car, VehicleCommand(throttle=.7, direction=direction, gear=direction, steering=3.))
            finally:
                car.close()
record = {'status':'unchanged native first step; independent shaft impulse to wheel reaction account',
          'max_error_N_m':max(row['max_independent_error_N_m'] for row in rows),'rows':rows}
Path(__file__).with_name('drive-layout-facts.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'rows':len(rows),'max_error_N_m':record['max_error_N_m']}))
