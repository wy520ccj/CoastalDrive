"""隔离剖析每个数值进程，不改生产求解或物理参数。"""
import os
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'src'))
from physics_workers import _worker_loop as original_loop


def profiled_loop(connection):
    import cProfile
    import json
    import pstats
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        original_loop(connection)
    finally:
        profiler.disable()
        output = Path(os.environ['COASTALDRIVE_WORKER_PROFILE'])/str(os.getpid())
        profiler.dump_stats(str(output.with_suffix('.prof')))
        rows = [{'file':Path(file).name,'line':line,'name':name,'calls':value[1],'self':value[2],'cumulative':value[3]}
                for (file,line,name),value in pstats.Stats(profiler).stats.items()]
        output.with_suffix('.json').write_text(json.dumps(sorted(rows,key=lambda v:-v['cumulative'])[:100],indent=2),encoding='utf-8')


if __name__=='__main__':
    output = Path(sys.argv[sys.argv.index('--output')+1])
    folder = output.with_name(output.name+'-worker-profiles').resolve()
    folder.mkdir(parents=True,exist_ok=False)
    os.environ['COASTALDRIVE_WORKER_PROFILE'] = str(folder)
    import physics_workers
    physics_workers._worker_loop = profiled_loop
    from parallel_trajectory import main
    main()
