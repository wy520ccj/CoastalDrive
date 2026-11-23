"""记录正常独立120Hz入口的动态水面；截图编码会扰动帧耗，不作性能验收。"""

import argparse
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread

import numpy as np
from panda3d.core import Filename, WindowProperties

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))

from application import CoastalDrive
from race import GameMode
from session import Phase


class WaterRecording(CoastalDrive):
    def __init__(self, output, keep_open):
        self.record_output = output
        self.keep_open = keep_open
        self.encoding_thread = None
        self.encoding_done = False
        self.encoder_error = ""
        self.video_frames = []
        self.record_complete = False
        self.render_snapshot_time = None
        self.video_start = None
        self.video_count = 0
        self.samples = []
        self.video_last = None
        self.video_done = False
        super().__init__()
        properties = WindowProperties()
        properties.setTitle('CoastalDrive · 动态海面预览')
        self.win.requestProperties(properties)
        self.taskMgr.doMethodLater(1,self.start_coast,'start-coastal-water')
        self.taskMgr.add(self.record_water,'record-coastal-water',sort=99)

    def start_coast(self, task):
        if self._workspace_steps is not None:
            return task.again
        self.start_game(mode=GameMode.FREE_DRIVE,track='coastal')
        return task.done

    def apply_scene(self, state, camera_dt):
        result = super().apply_scene(state,camera_dt)
        self.render_snapshot_time = state.time
        return result

    def record_water(self, task):
        if self.record_complete:
            if not self.encoding_done:
                return task.cont
            if self.encoder_error:
                raise RuntimeError(self.encoder_error)
            self.video_done = True
            print('WATER VIDEO READY',self.record_output/'water-normal.mp4',flush=True)
            if not self.keep_open:
                self.userExit()
            return task.done
        if self.session is None or self.session.phase!=Phase.DRIVING or self.session.current.time<2:
            return task.cont
        now = time.perf_counter()
        if self.video_start is None:
            self.video_size = (self.win.getXSize(),self.win.getYSize())
            self.video_start = now
        slot = min(120,int((now-self.video_start)*30))
        if slot<self.video_count:
            return task.cont
        if slot==120:
            self.record_complete = True
            report = {'completed':True,'frames':self.video_count,'fps':30,'size':self.video_size,
                'samples':self.samples,'scope':'正常独立120Hz/默认追车镜位，键盘未踩油门，真实Snapshot时间驱动水面；未人工驾驶。',
                'limits':'4秒视频30FPS；错过的视频槽重复上一真实帧，不插值；截图/编码扰动帧耗，不作为性能Gate。'}
            (self.record_output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            self.encoding_thread = Thread(target=self.encode_video,name='water-video-encoding')
            self.encoding_thread.start()
            return task.cont
        shot = self.win.getScreenshot()
        assert (shot.getXSize(),shot.getYSize())==self.video_size
        pixels = np.frombuffer(shot.getRamImageAs('RGB'),dtype=np.uint8).reshape(
            shot.getYSize(),shot.getXSize(),3)[::-1].tobytes()
        duplicates = 0
        while self.video_count<slot:
            self.video_frames.append(self.video_last)
            self.video_count+=1
            duplicates+=1
        self.video_frames.append(pixels)
        self.video_last = pixels
        self.video_count+=1
        state = self.session.current
        self.samples.append({'video_frame':slot,'wall_elapsed':now-self.video_start,'tick':state.tick,
            'authority_snapshot_time':state.time,'render_snapshot_time':self.render_snapshot_time,'water_time':self.scene.ocean.getShaderInput('sea_time').getVector()[0],
            'foreground':self.win.getProperties().getForeground(),'duplicates_before':duplicates})
        if slot in (0,60,119):
            assert shot.write(Filename.fromOsSpecific(str(self.record_output/f'normal-{slot:03d}.png')))
        return task.cont

    def encode_video(self):
        """采集结束后才编码，避免向编码器写管道造成实时画面停顿。"""
        executable = shutil.which('ffmpeg')
        if executable is None:
            self.encoder_error = '缺少现有ffmpeg，不能记录动态水面'
            self.encoding_done = True
            return
        command = [executable,'-y','-loglevel','error','-f','rawvideo','-pixel_format','rgb24',
            '-video_size',f'{self.video_size[0]}x{self.video_size[1]}','-framerate','30',
            '-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
            '-movflags','+faststart',str(self.record_output/'water-normal.mp4')]
        try:
            result = subprocess.run(command,input=b''.join(self.video_frames),capture_output=True,timeout=30,check=False)
            if result.returncode:
                self.encoder_error = '水面视频编码失败：'+result.stderr.decode('utf-8')
        except (OSError,subprocess.SubprocessError) as error:
            self.encoder_error = str(error)
        finally:
            self.video_frames.clear()
            self.encoding_done = True

    def close_video(self):
        if self.encoding_thread is not None:
            self.encoding_thread.join(35)



if __name__=='__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--keep-open',action='store_true')
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = WaterRecording(output,arguments.keep_open)
    try:
        app.run()
    finally:
        app.close_video()
        app.close_game()
