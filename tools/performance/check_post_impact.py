"""用玩家原配置复现撞后计算成本；初态固定，不作窗口流畅度验收。"""

import argparse
import cProfile
import hashlib
import json
import pickle
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))

from panda3d.core import Vec3

import simulation as simulation_module
from coastal_map import offset_point, point_at
from driving_modes import DrivingMode
from simulation import Control, Simulation
from tire_drivetrain import DrivetrainInput
from vehicle_workspace import WorkspaceVehicle


def distribution(rows):
    values = sorted(rows)
    return {'count':len(values),'mean_ms':sum(values)/len(values),
            'p95_ms':values[int((len(values)-1)*.95)],'max_ms':max(values)} if values else None


def check(output, workspace, steps, traffic, profile):
    output.mkdir(parents=True,exist_ok=False)
    vehicle = WorkspaceVehicle.load(workspace)
    if vehicle is None:
        raise FileNotFoundError(workspace)
    config = DrivingMode.GAME.configured_vehicle(base_config=vehicle.config)
    original_advance,original_solve = simulation_module.advance_world,DrivetrainInput.solve
    current = {'solve_ms':0.,'solve_calls':0}

    def advance(*args, **kwargs):
        current['substeps'] = kwargs['substeps']
        return original_advance(*args,**kwargs)

    def solve(request, **kwargs):
        started = time.perf_counter()
        try:
            return original_solve(request,**kwargs)
        finally:
            current['solve_ms'] += (time.perf_counter()-started)*1000
            current['solve_calls'] += 1

    simulation_module.advance_world,DrivetrainInput.solve = advance,solve
    summaries = []
    try:
        for collision in (False,True):
            sim = Simulation(seed=0,track='coastal',traffic_count=traffic,config=config,
                             input_config=DrivingMode.GAME.input_config)
            rows, hashes = [], []
            profiler = cProfile.Profile() if profile and collision else None
            try:
                # 仅固定复现初态；之后由原Bullet和Control完整推进，不中途修改姿态/速度。
                p = point_at(30)
                x,y,z = offset_point(p,4.3 if collision else -1.)
                sim.reset_player((x,y,z+.55),heading=p.heading)
                if sim.settle_initial() is None:
                    raise RuntimeError('碰撞样本初始静置未完成')
                velocity = sim.player._chassis.getTransform().getQuat().xform(Vec3(8. if collision else 0.,12.,0.))
                sim.player._chassis.setLinearVelocity(velocity)
                sim.player.tires.initialize_rolling(12.)
                impacts = 0
                for index in range(steps):
                    current.clear()
                    current.update(solve_ms=0.,solve_calls=0,refinement_before=sim._collision_refinement_ticks)
                    control = Control(brake=float(impacts>0))
                    started,cpu = time.perf_counter(),time.process_time()
                    if profiler:
                        profiler.enable()
                    sim.step(control)
                    if profiler:
                        profiler.disable()
                    wall = (time.perf_counter()-started)*1000
                    cpu_ms = (time.process_time()-cpu)*1000
                    state = sim.snapshot()
                    normalized = replace(state,contact_epoch=0,
                        impacts=tuple(replace(event,epoch=0) for event in state.impacts))
                    hashes.append(hashlib.sha256(pickle.dumps(normalized,protocol=5)).hexdigest())
                    impacts += len(state.impacts)
                    rows.append(dict(current,tick=state.tick,wall_ms=wall,cpu_ms=cpu_ms,
                                     refinement_after=sim._collision_refinement_ticks,
                                     impacts=len(state.impacts),contacts=len(state.contacts),
                                     speed=state.player.speed,collisions=state.collisions))
                report = {'collision_case':collision,'impacts':impacts,'rows':rows,
                          'normal_steps':distribution([r['wall_ms'] for r in rows if r['substeps']==config.tire_substeps]),
                          'refined_steps':distribution([r['wall_ms'] for r in rows if r['substeps']>config.tire_substeps]),
                          'all_steps':distribution([r['wall_ms'] for r in rows]),
                          'final_refinement_ticks':sim._collision_refinement_ticks}
                summaries.append({key:value for key,value in report.items() if key!='rows'})
                name = 'impact' if collision else 'normal'
                (output/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
                (output/(name+'-hashes.json')).write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
                if profiler:
                    profiler.dump_stats(str(output/'impact.pstats'))
                print(name,json.dumps(summaries[-1]),flush=True)
            finally:
                sim.close()
    finally:
        simulation_module.advance_world,DrivetrainInput.solve = original_advance,original_solve
    report = {'scope':'原玩家配置/原碰撞精度的固定初态无窗口计算诊断，不代表正常驾驶FPS或音频表现。',
              'workspace_design':vehicle.design_id,'config':asdict(config),'traffic':traffic,
              'profile':profile,'cases':summaries,
              'source_modules':{name:{'path':sys.modules[name].__file__,
                  'sha256':hashlib.sha256(Path(sys.modules[name].__file__).read_bytes()).hexdigest()}
                  for name in ('simulation','suspension_contacts','vehicle_suspension')}}
    (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summaries[1]['impacts']>0


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--steps',type=int,default=480)
    parser.add_argument('--traffic',type=int,default=8)
    parser.add_argument('--profile',action='store_true')
    args = parser.parse_args()
    raise SystemExit(0 if check(args.output.resolve(),args.workspace.resolve(),args.steps,args.traffic,args.profile) else 1)
