"""同轨迹串行/多核完整求解；保存快照和逐拍墙钟，不能当FPS。"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def exact(value):
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {k: exact(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)):
        return [exact(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,required=True)
    parser.add_argument('--source',type=Path,default=ROOT / 'src')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=('coastal','single','hills','reference'),default='coastal')
    parser.add_argument('--cpu-affinity',type=lambda value:int(value,0))
    parser.add_argument('--profile',action='store_true')
    parser.add_argument('--seed',type=int,default=17)
    parser.add_argument('--ticks',type=int,default=128)
    parser.add_argument('--constant',action='store_true')
    args = parser.parse_args()
    if args.cpu_affinity is not None:
        import ctypes
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p,ctypes.c_size_t]
        if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(),args.cpu_affinity):
            raise ctypes.WinError(ctypes.get_last_error())
    sys.path.insert(0,str(args.source.resolve()))
    import paths
    paths.resource_root = lambda:ROOT
    from driving_modes import DrivingMode
    from simulation import Control,Simulation
    from vehicle_designs import GR86_DESIGN
    sim = Simulation(seed=args.seed,track='endless' if args.case=='hills' else 'coastal',
        road_shape='hills' if args.case=='hills' else 'straight',traffic_count=0 if args.case=='single' else 8,
        config=DrivingMode.GAME.vehicle_config if args.case=='reference' else GR86_DESIGN,
        input_config=DrivingMode.GAME.input_config,**({'physics_workers':args.workers} if args.workers else {}))
    frames,times = [],[]
    if args.profile:
        import cProfile
        profiler = cProfile.Profile()
    try:
        for tick in range(args.ticks):
            if args.profile and tick==32:
                profiler.enable()
            if args.profile and tick==96:
                profiler.disable()
            control = Control(throttle=.3 if tick<96 else 0.,brake=.5 if tick>=96 else 0.,
                              steering=0. if tick<64 else .1 if tick<96 else -.1)
            if args.constant:
                control=Control(throttle=.3)
            started = time.perf_counter()
            sim.step(control)
            times.append(time.perf_counter()-started)
            frames.append(exact(asdict(sim.snapshot())))
        counts = {'remote':sim._physics_workers.remote_count,'world_required':sim._physics_workers.world_query_count} if args.workers else {}
    finally:
        sim.close()
    encoded = json.dumps(frames,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    args.output.mkdir(parents=True,exist_ok=False)
    if args.profile:
        import pstats
        profiler.dump_stats(str(args.output / 'parent.prof'))
        rows = [{'file':Path(file).name,'line':line,'name':name,'calls':value[1],'self':value[2],'cumulative':value[3]}
                for (file,line,name),value in pstats.Stats(profiler).stats.items()]
        (args.output / 'profile.json').write_text(json.dumps(sorted(rows,key=lambda v:-v['cumulative'])[:60],indent=2),encoding='utf-8')
    (args.output / 'snapshots.json.gz').write_bytes(gzip.compress(encoded,mtime=0))
    report = {'case':args.case,'workers':args.workers,'source':str(args.source.resolve()),'ticks':args.ticks,'seed':args.seed,'constant':args.constant,
              'cpu_affinity':args.cpu_affinity,'snapshot_sha256':hashlib.sha256(encoded).hexdigest(),
              'tick_seconds':times,'sample_32_96_mean_ms':sum(times[32:96])/64*1000,
              'first_tick_seconds':times[0],'wall_128':sum(times),'counts':counts,
              'scope':'full 120 Hz physics, short headless; no FPS gate'}
    (args.output / 'timing.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='tick_seconds'}),flush=True)


if __name__=='__main__':
    main()
