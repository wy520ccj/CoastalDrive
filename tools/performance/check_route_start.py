"""同一路线起步时机的真实120Hz复现；核对图形候选之外的机械异常。"""

import argparse
import json
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools/environment'))

from check_driving_composition import ViewDriver

from race import BestTimes, GameMode
from session import Phase, Session
from vehicle_workspace import WorkspaceVehicle


def check(output, idle_ticks, road_step, substeps=1, refine_from_tick=None, refine_ticks=1, adaptive_support=False):
    output.mkdir(parents=True, exist_ok=False)
    vehicle = WorkspaceVehicle.load()
    import curve_mesh
    import simulation as simulation_module

    curve_mesh.ROAD_STEP = road_step
    original_substeps = simulation_module.physical_substeps
    results = []
    for idle in idle_ticks:
        session = Session(0, track='endless', road_shape='ridge-club', vehicle_config=vehicle.config,
                          scores=BestTimes(output/('scores-'+str(idle)+'.json')))
        refined_ticks = [0]
        def selected_substeps(config, current_session=session, counter=refined_ticks):
            if adaptive_support:
                world = current_session.simulation
                normals = {contact.contact_normal for contact in world.player._wheel_contacts if contact.in_contact}
                selected = world.road.curve is not None and world.player.coupled_suspension and len(normals) > 1
                if selected:
                    counter[0] += 1
                return max(original_substeps(config), 2 if selected else 1)
            selected = refine_from_tick is None or refine_from_tick <= current_session.simulation._tick < refine_from_tick+refine_ticks
            return max(original_substeps(config), substeps if selected else 1)

        simulation_module.physical_substeps = selected_substeps
        controls = []
        report = {'idle_ticks': idle, 'road_step': road_step, 'substeps': substeps,
                  'refine_from_tick': refine_from_tick, 'refine_ticks': refine_ticks,
                  'adaptive_support': adaptive_support,
                  'passed': False, 'scope': '原GT/正常生涯倒计时与完成物理步；无显示线程，不修改任何机械门槛；局部细分在已知完成步之前计划，不先失败再重试'}
        started = time.perf_counter()
        try:
            session.start(countdown=True, mode=GameMode.CAREER, settle_initial=True, career_event_id='ridge-run')
            while session.phase == Phase.COUNTDOWN:
                session.countdown_step(1)
            report['initialisation_ticks'] = session.simulation.initialisation_ticks
            for _ in range(idle):
                session.tick()
            report['driver_start_tick'] = session.current.tick
            session.set_controller(ViewDriver(session))
            for _ in range(12000):
                if session.current.tick == refine_from_tick:
                    report['refinement_before'] = asdict(session.current)
                # 直接记录相同的Control后交给原Session.tick，不修改物理推进。
                controls.append(asdict(session.controller.sample(session.current, 1/120)))
                session.tick()
                distance = session.simulation.road.locate(session.current.player)[0]
                if distance >= 900:
                    report.update(passed=True, distance=distance, end_tick=session.current.tick,
                                  collisions=session.current.collisions)
                    break
            else:
                report['reason'] = '900m未在100秒仿真内完成'
        except ArithmeticError:
            report.update(exception=traceback.format_exc(), before=asdict(session.current),
                          controls=controls, config=asdict(session.vehicle_config),
                          distance=session.simulation.road.locate(session.current.player)[0])
        finally:
            session.close()
            simulation_module.physical_substeps = original_substeps
        report['compute_wall_s'] = time.perf_counter()-started
        report['refined_ticks'] = refined_ticks[0]
        (output/('idle-'+str(idle)+'.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('ROUTE', idle, report['passed'], report.get('distance'), report['compute_wall_s'], flush=True)
        results.append({k: v for k, v in report.items() if k not in ('before', 'controls', 'config', 'exception')})
    (output/'summary.json').write_text(json.dumps({'runs': results, 'passed': all(r['passed'] for r in results)}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--idle-ticks', type=int, nargs='+', default=(2, 4))
    parser.add_argument('--road-step', type=int, choices=(1, 5), default=1)
    parser.add_argument('--substeps', type=int, choices=(1, 2, 4), default=1)
    parser.add_argument('--refine-from-tick', type=int)
    parser.add_argument('--refine-ticks', type=int, default=1)
    parser.add_argument('--adaptive-support', action='store_true')
    args = parser.parse_args()
    check(args.output.resolve(), args.idle_ticks, args.road_step, args.substeps,
          args.refine_from_tick, args.refine_ticks, args.adaptive_support)
