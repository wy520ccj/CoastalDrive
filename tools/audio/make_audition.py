"""用生产声音控制逻辑离线混音，导出引擎/碰撞/电台试听。"""

import argparse
import math
import sys
import wave
from array import array
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from impact_events import ContactState, ImpactEvent
from session import Phase
from simulation import Snapshot
from soundscape import Soundscape
from vehicle_state import CarState

RATE = 44100


class Clip:
    def __init__(self, data, channels):
        self.data, self.channels = data, channels
        self.playing = False
        self.loop = False
        self.volume = 0.0
        self.rate = 1.0
        self.frame = 0.0
        self.pan = 0.0

    def setLoop(self, value):
        self.loop = value

    def setVolume(self, value):
        self.volume = value

    def setPlayRate(self, value):
        self.rate = value

    def set3dAttributes(self, x, y, z, vx, vy, vz):
        self.pan = x / math.sqrt(x*x + y*y + z*z)

    def play(self):
        if not self.playing:
            self.playing = True

    def stop(self):
        self.playing = False
        self.frame = 0.0

    def getTime(self):
        return self.frame / RATE

    def setTime(self, value):
        self.frame = value * RATE


class Mixer:
    def __init__(self):
        self.loader = self
        self.musicManager = self
        self.clips = []
        self.cache = {}

    def getSound(self, filename, positional, mode):
        return self.loadSfx(filename, positional=positional)

    def loadSfx(self, filename, positional=False):
        path = filename.toOsSpecific()
        if path not in self.cache:
            with wave.open(path, "rb") as clip:
                self.cache[path] = (array("h", clip.readframes(clip.getnframes())),
                                    clip.getnchannels())
        sound = Clip(*self.cache[path])
        self.clips.append(sound)
        return sound

    def render(self, count):
        left = [0.0] * count
        right = [0.0] * count
        for sound in self.clips:
            if not sound.playing:
                continue
            data = sound.data
            length = len(data) // sound.channels
            if sound.volume == 0:
                sound.frame = (sound.frame + count * sound.rate) % length
                continue
            l_gain = sound.volume * math.sqrt((1-sound.pan)/2)
            r_gain = sound.volume * math.sqrt((1+sound.pan)/2)
            for i in range(count):
                index = int(sound.frame)
                if index >= length:
                    if sound.loop:
                        sound.frame %= length
                        index %= length
                    else:
                        sound.playing = False
                        break
                fraction = sound.frame - index
                next_index = (index + 1) % length
                a = data[index * sound.channels]
                b = data[next_index * sound.channels]
                left[i] += (a + (b-a) * fraction) * l_gain
                if sound.channels == 2:
                    a = data[index*2+1]
                    b = data[next_index*2+1]
                right[i] += (a + (b-a) * fraction) * r_gain
                sound.frame += sound.rate
        pcm = array("h")
        for l, r in zip(left, right):
            pcm.extend((max(-32767, min(32767, round(l))), max(-32767, min(32767, round(r)))))
        return pcm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mixer = Mixer()
    sound = Soundscape(mixer, music_volume=0)
    sound.music.select(0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.output), "wb") as result:
        result.setnchannels(2)
        result.setsampwidth(2)
        result.setframerate(RATE)
        for tick in range(60 * 44):
            t = tick / 60
            impacts, contacts = (), ()
            rpm = 900 + min(1, t / 10) * 5600 if t < 12 else 2800
            player = CarState((0, 0, 1), rpm=rpm, speed=min(32, t*2),
                              throttle=.95 if t < 12 else .05, gear=min(5, 1+int(t/3)))
            phase = Phase.DRIVING
            if 13 <= t < 24:
                player = replace(player, speed=0, throttle=0, rpm=900)
                for index, trigger in enumerate((14, 17, 20, 23)):
                    if tick == trigger * 60:
                        material = ("vehicle", "metal_barrier", "hard_solid", "vehicle")[index]
                        impulse = (3000, 12000, 15000, 22000)[index]
                        impacts = (ImpactEvent(1, tick*2, 0, (index+1,), material,
                            impulse, impulse, impulse/1200, 2, (0, 2, .4),
                            (0, -1, 0), "front", 1),)
            if 25 <= t < 28:
                contacts = (ContactState((2,), "metal_barrier", tick*2, 150, 0, 8,
                                         (.8, 0, .4), (-1, 0, 0), "right", tick),)
            if t >= 28:
                sound.set_volumes(100, 12, 90)
                sound.music.select(1 if t < 36 else 2)
            state = Snapshot(tick*2, t, player, (), contact_epoch=1,
                             impacts=impacts, contacts=contacts)
            sound.update(state, phase, None, 1/60)
            result.writeframes(mixer.render(RATE//60).tobytes())
    sound.close()
    print(args.output)


if __name__ == "__main__":
    main()
