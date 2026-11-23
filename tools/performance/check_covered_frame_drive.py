"""原主入口驾驶与显示快照覆盖检查；可仅替换本轮旧frame函数作对照。"""

import argparse
import hashlib
import json
import multiprocessing
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/environment'))

import check_interactive_local_drive
from check_interactive_local_drive import DrivingProbe

import session_process
from session_clock import PRESENTATION_DELAY

if __name__=='__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--end-distance',type=int,choices=(270,450,900),default=900)
    parser.add_argument('--blocking-baseline',action='store_true')
    arguments = parser.parse_args()
    if arguments.blocking_baseline:
        baseline = ROOT/'logs/visual-extend-20261028/session-process-before-covered-frame.py'
        spec = spec_from_file_location('covered_drive_baseline',baseline)
        module = module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        session_process.SessionProcess.frame = module.SessionProcess.frame
    original_frame = session_process.SessionProcess.frame
    latest = {}

    def observe_frame(remote, *args, **kwargs):
        state = original_frame(remote,*args,**kwargs)
        if 'sampled_at' in kwargs:
            output = remote.output
            target = kwargs['sampled_at']-output.timeline_origin-(output.dropped_time-output.dropped_epoch)-PRESENTATION_DELAY
            latest.update(requested_time=target,visible_time=state.time,latest_time=remote.history[-1].time,
                          underflow=target>remote.history[-1].time+1e-6)
        return state

    session_process.SessionProcess.frame = observe_frame

    def attach(app):
        if app.probe_frames and 'presentation' not in app.probe_frames[-1]:
            app.probe_frames[-1]['presentation'] = dict(latest)

    original_probe = DrivingProbe.probe_frame
    original_finish = DrivingProbe.probe_finish

    def observe_probe(app, task):
        result = original_probe(app,task)
        attach(app)
        return result

    def observe_finish(app):
        attach(app)
        original_finish(app)

    DrivingProbe.probe_frame = observe_probe
    DrivingProbe.probe_finish = observe_finish
    check_interactive_local_drive.check(arguments.output.resolve(),False,False,end_distance=arguments.end_distance)
    report_path = arguments.output/'summary.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    frames = json.loads((arguments.output/'frames.json').read_text(encoding='utf-8'))
    report.update(blocking_frame_baseline=arguments.blocking_baseline,
                  presentation_underflow_frames=sum(row['presentation']['underflow'] for row in frames),
                  frame_source=original_frame.__code__.co_filename,
                  session_process_source_sha256=hashlib.sha256((ROOT/'src/session_process.py').read_bytes()).hexdigest())
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
