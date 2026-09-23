"""驾驶循环和汽车撞击的声音入口。"""

from panda3d.core import Filename

from impact_audio import ImpactAudio
from paths import resource_root


class Soundscape:
    def __init__(self, base, master_volume=100, effects_volume=100):
        audio_dir = resource_root() / "assets" / "game" / "audio"
        self.engine = base.loader.loadSfx(Filename.fromOsSpecific(str(audio_dir / "engine.wav")))
        self.engine_idle = base.loader.loadSfx(
            Filename.fromOsSpecific(str(audio_dir / "engine_idle.wav"))
        )
        self.road = base.loader.loadSfx(Filename.fromOsSpecific(str(audio_dir / "road.wav")))
        self.impact_audio = ImpactAudio(base, audio_dir)
        self.loops = (self.engine, self.engine_idle, self.road)
        for sound in self.loops:
            sound.setLoop(True)
            sound.setVolume(0)
        self.engine_level = 0.0
        self.road_level = 0.0
        self.master_volume = max(0, min(100, master_volume)) / 100
        self.effects_volume = max(0, min(100, effects_volume)) / 100
        self.loops_playing = False
        self.last_time = None
        self.closed = False

    def set_impact_diagnostic(self, diagnostic):
        self.impact_audio.set_diagnostic(diagnostic)

    def update(self, state, phase, control, audio_dt=None):
        now = state.time
        dt = (audio_dt if audio_dt is not None else
              1 / 120 if self.last_time is None else max(1 / 240, min(0.1, now - self.last_time)))
        dt = max(0.0, min(0.1, dt))
        self.last_time = now
        driving_loop = phase.value in ("driving", "countdown")
        if driving_loop:
            throttle = state.player.throttle if control is None else max(
                control.throttle, state.player.throttle
            )
            rpm = max(0.0, min(9000.0, state.player.rpm))
            engine_target = min(0.2, 0.1 + rpm / 9000 * 0.065 + throttle * 0.03)
            road_target = min(0.075, abs(state.player.speed) / 36 * 0.07)
            if state.player.surface != "asphalt":
                road_target *= 1.2
        else:
            rpm = 0.0
            engine_target = 0.0
            road_target = 0.0
        blend = min(1.0, dt * 7.0)
        self.engine_level += (engine_target - self.engine_level) * blend
        self.road_level += (road_target - self.road_level) * blend
        volume = self.master_volume * self.effects_volume
        duck = self.impact_audio.update(
            getattr(state, "impacts", ()), getattr(state, "contacts", ()), dt, volume,
            epoch=getattr(state, "contact_epoch", 0), driving=phase.value == "driving",
        )
        if driving_loop and volume > 0:
            if not self.loops_playing:
                for sound in self.loops:
                    sound.play()
                self.loops_playing = True
            idle_mix = max(0.0, min(1.0, (4400 - rpm) / 2500))
            self.engine_idle.setVolume(self.engine_level * idle_mix ** 0.5 * volume * duck)
            self.engine.setVolume(self.engine_level * (1 - idle_mix) ** 0.5 * volume * duck)
            self.road.setVolume(self.road_level * volume * duck)
        else:
            self._stop_loops()
        self.engine_idle.setPlayRate(0.92 + rpm / 9000 * 0.08 if driving_loop else 0.92)
        self.engine.setPlayRate(0.58 + rpm / 9000 * 0.44 if driving_loop else 0.58)
        self.road.setPlayRate(1.0)

    def set_volumes(self, master_volume, effects_volume):
        self.master_volume = max(0, min(100, master_volume)) / 100
        self.effects_volume = max(0, min(100, effects_volume)) / 100
        if self.master_volume == 0 or self.effects_volume == 0:
            self._stop_loops()
            self.impact_audio.stop()

    def _stop_loops(self):
        if self.loops_playing:
            for sound in self.loops:
                sound.stop()
            self.loops_playing = False
        for sound in self.loops:
            sound.setVolume(0)
        self.engine_level = 0.0
        self.road_level = 0.0

    def close(self):
        if self.closed:
            return
        self._stop_loops()
        self.impact_audio.stop()
        self.closed = True
