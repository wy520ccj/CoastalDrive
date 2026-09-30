"""界面操作、发车、检查点和结算短音。"""

from panda3d.core import Filename


class CueAudio:
    def __init__(self, base, directory):
        self.sounds = {name: base.loader.loadSfx(Filename.fromOsSpecific(
            str(directory / "cues" / f"{name}.wav")))
                       for name in ("select", "confirm", "countdown", "go", "checkpoint",
                                    "success", "finish", "failure", "radio")}
        self.scale = 1.0

    def play(self, name):
        if self.scale > 0:
            sound = self.sounds[name]
            sound.setVolume(0.24 * self.scale)
            sound.play()

    def set_volume(self, scale):
        self.scale = scale
        for sound in self.sounds.values():
            sound.setVolume(0.24 * scale)
            if scale == 0:
                sound.stop()

    def stop(self):
        for sound in self.sounds.values():
            sound.stop()
