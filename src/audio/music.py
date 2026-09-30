"""双电台交叉淡化、菜单BGM及暂停续播。"""

import math

from panda3d.core import Filename

STATIONS = ("关闭", "海岸 FM · Sunset Run", "夜驰 FM · Midnight Circuit")


class MusicAudio:
    def __init__(self, base, directory, station=1):
        self.tracks = tuple(base.loader.loadSfx(Filename.fromOsSpecific(
            str(directory / "music" / f"{name}.wav")))
                            for name in ("sunset-run", "midnight-circuit"))
        for sound in self.tracks:
            sound.setLoop(True)
            sound.setVolume(0)
        self.station = station
        self.levels = [0.0, 0.0]
        self.playing = [False, False]
        self.positions = [0.0, 0.0]
        self.duck = 1.0

    def select(self, station):
        self.station = station

    def update(self, phase, dt, scale, duck):
        if phase == "paused" or scale <= 0:
            self.stop(preserve=True)
            return
        target = self.station - 1 if phase in ("driving", "countdown") else 0
        if phase == "results":
            target = self.station - 1
        gain = 0.36 if phase in ("driving", "countdown") else 0.20
        self.duck += (duck - self.duck) * (1 - math.exp(-dt / (
            .03 if duck < self.duck else .24)))
        for i, sound in enumerate(self.tracks):
            desired = gain if i == target else 0.0
            self.levels[i] += max(-dt * 0.55, min(dt * 0.55, desired - self.levels[i]))
            if self.levels[i] > 0 and not self.playing[i]:
                sound.setTime(self.positions[i])
                sound.play()
                self.playing[i] = True
            sound.setVolume(self.levels[i] * scale * self.duck)
            if self.levels[i] == 0 and self.playing[i]:
                self.positions[i] = sound.getTime()
                sound.stop()
                self.playing[i] = False

    def stop(self, preserve=False):
        for i, sound in enumerate(self.tracks):
            if self.playing[i]:
                if preserve:
                    self.positions[i] = sound.getTime()
                sound.stop()
            sound.setVolume(0)
            self.playing[i] = False
            self.levels[i] = 0.0
        if not preserve:
            self.positions = [0.0, 0.0]
