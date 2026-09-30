"""路面、风噪和轮胎摩擦，消费车辆快照。"""

import math

from panda3d.core import Filename


class DrivingAudio:
    def __init__(self, base, directory):
        self.names = ("asphalt", "gravel", "wind", "tire")
        self.sounds = {name: base.loader.loadSfx(Filename.fromOsSpecific(
            str(directory / "driving" / f"{name}.wav"))) for name in self.names}
        self.levels = dict.fromkeys(self.names, 0.0)
        self.playing = False
        for sound in self.sounds.values():
            sound.setLoop(True)
            sound.setVolume(0)

    def update(self, player, dt, scale, active):
        if not active or scale <= 0:
            self.stop()
            return
        if not self.playing:
            for sound in self.sounds.values():
                sound.play()
            self.playing = True
        speed = abs(player.speed)
        roll = min(1, speed / 32)
        offroad = player.surface != "asphalt"
        # 侧偏/横向载荷和制动都来自物理快照；低速转向不会凭空尖叫。
        slip = max(abs(player.dynamics.sideslip) / 14,
                   abs(player.lateral_acceleration) / 9.81 - 0.48,
                   player.brake * 0.7) - 0.18
        targets = {
            "asphalt": 0 if offroad else 0.075 * roll,
            "gravel": 0.15 * roll if offroad else 0,
            "wind": 0.075 * min(1, (speed / 42) ** 2),
            "tire": 0.17 * min(1, max(0, slip)) * min(1, max(0, (speed - 5) / 12))
                    if not offroad else 0,
        }
        for name, sound in self.sounds.items():
            self.levels[name] += (targets[name] - self.levels[name]) * (
                1 - math.exp(-dt / 0.10))
            sound.setVolume(self.levels[name] * scale)
            sound.setPlayRate(0.83 + 0.30 * roll if name != "wind" else 1.0)

    def stop(self):
        for name, sound in self.sounds.items():
            if self.playing:
                sound.stop()
            sound.setVolume(0)
            self.levels[name] = 0.0
        self.playing = False
