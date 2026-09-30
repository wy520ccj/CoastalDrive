"""经典美式V8的转速、负载与换挡表现。"""

import math
from bisect import bisect_right

from panda3d.core import Filename

RPM_BANDS = (900, 1800, 3200, 4700, 6500)


def band_mix(rpm):
    rpm = max(RPM_BANDS[0], min(7600, rpm))
    upper = min(len(RPM_BANDS) - 1, bisect_right(RPM_BANDS, rpm))
    lower = max(0, upper - 1)
    amount = max(0, min(1, (rpm - RPM_BANDS[lower]) /
                         (RPM_BANDS[upper] - RPM_BANDS[lower])))
    return lower, upper, math.cos(amount * math.pi / 2), math.sin(amount * math.pi / 2)


class EngineAudio:
    def __init__(self, base, directory):
        self.layers = []
        for rpm in RPM_BANDS:
            pair = tuple(base.loader.loadSfx(Filename.fromOsSpecific(
                str(directory / "engine" / f"v8-{rpm}-{load}.wav")))
                         for load in ("coast", "load"))
            self.layers.append(pair)
        self.loops = tuple(sound for pair in self.layers for sound in pair)
        for sound in self.loops:
            sound.setLoop(True)
            sound.setVolume(0)
        self.playing = False
        self.rpm = 900.0
        self.load = 0.0
        self.gear = None
        self.shift_time = 0.0
        self.level = 0.0

    def update(self, player, throttle, dt, scale, active):
        if not active or scale <= 0:
            self.stop()
            return
        if not self.playing:
            self.rpm = player.rpm
            self.gear = player.gear
            for sound in self.loops:
                sound.play()
            self.playing = True
        if player.gear != self.gear:
            self.shift_time = 0.11
            self.gear = player.gear
        self.shift_time = max(0, self.shift_time - dt)
        self.rpm += (player.rpm - self.rpm) * (1 - math.exp(-dt / 0.045))
        self.load += (throttle - self.load) * (1 - math.exp(-dt / 0.085))
        lower, upper, left, right = band_mix(self.rpm)
        target = (0.27 + 0.18 * self.load + 0.045 * min(1, self.rpm / 6500))
        target *= 0.62 if self.shift_time > 0 else 1
        self.level += (target - self.level) * (1 - math.exp(-dt / 0.035))
        for i, (coast, loaded) in enumerate(self.layers):
            mix = left if i == lower else right if i == upper else 0.0
            coast.setPlayRate(self.rpm / RPM_BANDS[i])
            loaded.setPlayRate(self.rpm / RPM_BANDS[i])
            coast.setVolume(self.level * mix * math.sqrt(1 - self.load) * scale)
            loaded.setVolume(self.level * mix * math.sqrt(self.load) * scale)

    def stop(self):
        if self.playing:
            for sound in self.loops:
                sound.stop()
        for sound in self.loops:
            sound.setVolume(0)
        self.playing = False
        self.gear = None
        self.shift_time = 0.0
        self.level = 0.0
