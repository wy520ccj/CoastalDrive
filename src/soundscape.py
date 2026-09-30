"""驾驶音频入口：直接把快照送给各功能声音。"""

import math

from audio.cues import CueAudio
from audio.driving import DrivingAudio
from audio.engine import EngineAudio
from audio.impact import ImpactAudio
from audio.music import MusicAudio
from paths import resource_root


class Soundscape:
    def __init__(self, base, master_volume=100, effects_volume=100,
                 music_volume=55, radio_station=1):
        directory = resource_root() / "assets" / "game" / "audio"
        self.engine_audio = EngineAudio(base, directory)
        self.driving_audio = DrivingAudio(base, directory)
        self.impact_audio = ImpactAudio(base, directory)
        self.music = MusicAudio(base, directory, radio_station)
        self.cues = CueAudio(base, directory)
        self.master_volume = master_volume / 100
        self.effects_volume = effects_volume / 100
        self.music_volume = music_volume / 100
        self.last_time = None
        self.last_phase = None
        self.last_epoch = None
        self.countdown_second = None
        self.results_impacts_consumed = False
        self.closed = False
        self.cues.set_volume(self.master_volume * self.effects_volume)

    @property
    def loops_playing(self):
        return self.engine_audio.playing or self.driving_audio.playing

    def set_impact_diagnostic(self, diagnostic):
        self.impact_audio.set_diagnostic(diagnostic)

    def update(self, state, phase, control, audio_dt=None, *, countdown_ticks=0):
        dt = audio_dt if audio_dt is not None else (
            1 / 120 if self.last_time is None else state.time - self.last_time)
        dt = max(0, min(0.1, dt))
        self.last_time = state.time
        value = phase.value
        driving = value in ("driving", "countdown")
        if state.contact_epoch != self.last_epoch:
            self.results_impacts_consumed = False
            self.countdown_second = None
            self.last_epoch = state.contact_epoch
            self.engine_audio.stop()
            self.driving_audio.stop()
            self.cues.stop()
        if driving:
            self.results_impacts_consumed = False
        accept = value == "driving"
        if value == "results" and not self.results_impacts_consumed:
            accept = bool(state.impacts)
            self.results_impacts_consumed = True
        scale = self.master_volume * self.effects_volume
        duck = self.impact_audio.update(
            state.impacts, state.contacts, dt, scale, epoch=state.contact_epoch,
            driving=value == "driving", accept_new_impacts=accept,
            maintain_impact_tails=value == "results",
        )
        throttle = state.player.throttle if control is None else control.throttle
        self.engine_audio.update(state.player, throttle, dt, scale * duck, driving)
        self.driving_audio.update(state.player, dt, scale * duck, driving)
        self.music.update(value, dt, self.master_volume * self.music_volume,
                          0.55 if duck < 0.96 else 1.0)
        if value == "countdown":
            second = math.ceil(countdown_ticks / 120)
            if second > 0 and second != self.countdown_second:
                self.cues.play("countdown")
                self.countdown_second = second
        if value == "driving" and self.last_phase == "countdown":
            self.cues.play("go")
        if value == "paused" and self.last_phase != "paused":
            self.cues.stop()
        self.last_phase = value

    def set_volumes(self, master_volume, effects_volume, music_volume=None):
        self.master_volume = max(0, min(100, master_volume)) / 100
        self.effects_volume = max(0, min(100, effects_volume)) / 100
        if music_volume is not None:
            self.music_volume = max(0, min(100, music_volume)) / 100
        scale = self.master_volume * self.effects_volume
        self.cues.set_volume(scale)
        if scale == 0:
            self.engine_audio.stop()
            self.driving_audio.stop()
            self.impact_audio.stop()
        if self.master_volume * self.music_volume == 0:
            self.music.stop(preserve=True)

    def close(self):
        if self.closed:
            return
        self.engine_audio.stop()
        self.driving_audio.stop()
        self.impact_audio.stop()
        self.music.stop()
        self.cues.stop()
        self.closed = True
