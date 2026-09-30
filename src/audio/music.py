"""双电台单曲切换、菜单BGM及暂停续播。"""

import math

from panda3d.core import AudioManager, Filename

STATIONS = ("关闭", "海岸 FM · Bossa Antigua", "夜驰 FM · Future Gladiator")


class MusicAudio:
    def __init__(self, base, directory, station=1):
        # 电台与首页曲预载，避免流式WAV续播字节错位和切台时读盘填缓冲。
        self.tracks = tuple(base.musicManager.getSound(Filename.fromOsSpecific(
            str(directory / "music" / f"{name}.wav")), False, AudioManager.SM_sample)
                            for name in ("sunset-run", "midnight-circuit", "home-coast"))
        for sound in self.tracks:
            sound.setLoop(True)
            sound.setVolume(0)
        self.station = station
        self.levels = [0.0] * len(self.tracks)
        self.playing = [False] * len(self.tracks)
        self.positions = [0.0] * len(self.tracks)
        self.duck = 1.0

    def select(self, station):
        self.station = station

    def update(self, phase, dt, scale, duck, *, preview=False):
        if (phase == "paused" and not preview) or scale <= 0:
            self.stop(preserve=True)
            return
        # 首页独立BGM；设置页试听和驾驶消费所选电台，统一单曲切换避免叠播。
        target = 2 if phase == "menu" and not preview else self.station - 1
        gain = 0.36 if phase in ("driving", "countdown") else 0.20
        self.duck += (duck - self.duck) * (1 - math.exp(-dt / (
            .03 if duck < self.duck else .24)))
        # 先淡出并停止旧台，再允许新台起播；快速往返切台也不能两首同时响。
        for i, sound in enumerate(self.tracks):
            if i == target:
                continue
            self.levels[i] = max(0, self.levels[i] - dt * 6)
            sound.setVolume(self.levels[i] * scale * self.duck)
            if self.levels[i] == 0 and self.playing[i]:
                self.positions[i] = sound.getTime()
                sound.stop()
                self.playing[i] = False
        if target < 0 or any(active for i, active in enumerate(self.playing) if i != target):
            return
        sound = self.tracks[target]
        self.levels[target] += max(-dt * 4, min(dt * 4, gain - self.levels[target]))
        if self.levels[target] > 0 and not self.playing[target]:
            sound.setTime(self.positions[target])
            sound.play()
            self.playing[target] = True
        sound.setVolume(self.levels[target] * scale * self.duck)

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
            self.positions = [0.0] * len(self.tracks)
