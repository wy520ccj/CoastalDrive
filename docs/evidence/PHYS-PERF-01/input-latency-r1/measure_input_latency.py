"""诊断原会话的按键采样时间；不测OS最终呈现，也不修改生产进度接口。"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

root = Path.cwd()

def prepare(source, target):
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__'))
    p = target/'session.py'
    s = p.read_text(encoding='utf-8').replace('import os','import os\nimport time',1)
    s = s.replace('self.last_control = self.controller.sample(self.current, FIXED_DT)',
        '''before = self.last_control.steering
            self.last_control = self.controller.sample(self.current, FIXED_DT)
            if self.last_control.steering and not before:
                self._input_sampled_at = time.perf_counter()''',1)
    s = s.replace('self._clock = None','self._clock = None\n        self._input_sampled_at = 0.',1)
    p.write_text(s,encoding='utf-8')
    p = target/'session_process.py'
    s = p.read_text(encoding='utf-8').replace(
        'return clock.current.tick, session.stepper.dropped_time, perf_counter()',
        'return clock.current.tick, session.stepper.dropped_time, perf_counter(), session._input_sampled_at, clock.current.player.steering',1)
    p.write_text(s,encoding='utf-8')
    p = target/'paths.py'
    p.write_text(p.read_text(encoding='utf-8').replace('Path(__file__).resolve().parent.parent','Path.cwd()'),encoding='utf-8')

def run(source, destination):
    sys.path.insert(0,str(source.resolve()))
    from driving_modes import DrivingMode
    from session_process import SessionProcess
    from vehicle_designs import GR86_DESIGN

    remote = SessionProcess(track='test',driving_mode=DrivingMode.SIMULATION,vehicle_config=GR86_DESIGN)
    rows = []
    try:
        remote.start(countdown=False,settle_initial=True)
        remote.frame(0)
        for index in range(16):
            # 每次松键后等待真实齿条回正，均匀覆盖60Hz绘制周期中的输入相位。
            stop = time.perf_counter()+.25
            while time.perf_counter()<stop:
                remote.frame(0)
                time.sleep(1/60)
            phase = index/16/60
            remote.frame(0)
            frame_at = time.perf_counter()
            time.sleep(phase)
            pressed_at = time.perf_counter()
            remote.keyboard.press('d')
            next_frame = frame_at+1/60
            deadline = pressed_at+.5
            progress = None
            while time.perf_counter()<deadline:
                now = time.perf_counter()
                if now>=next_frame:
                    remote.frame(0)
                    next_frame += 1/60
                progress = remote.progress()
                if progress[3]>=pressed_at:
                    break
                time.sleep(.001)
            assert progress[3]>=pressed_at
            rows.append({'input_phase_ms':phase*1000,'sample_latency_ms':(progress[3]-pressed_at)*1000,
                         'pressed_at':pressed_at,'sampled_at':progress[3]})
            remote.keyboard.release('d')
    finally:
        remote.close()
    values = sorted(row['sample_latency_ms'] for row in rows)
    result = {'kind':'key publication to actual Controller.sample; not input-to-photon',
              'source':str(source.resolve()),'frames_hz':60,'physics_hz':120,'traffic':0,
              'samples':rows,'median_ms':(values[7]+values[8])/2,'max_ms':values[-1]}
    destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print({k:v for k,v in result.items() if k!='samples'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--case',choices=('old','new'))
    args = parser.parse_args()
    base = root/'logs/performance/input-latency-r1'
    if args.prepare:
        prepare(base/'baseline/src',base/'latency-old/src')
        prepare(root/'src',base/'latency-new/src')
    else:
        run(base/f'latency-{args.case}/src',base/f'latency-{args.case}.json')
