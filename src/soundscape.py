"""Small state-driven audio layer for the driving loop."""

from panda3d.core import Filename

from paths import resource_root


class Soundscape:
    def __init__(self, base):
        self.base = base
        audio_dir = resource_root() / "assets" / "game" / "audio"
        self.engine = base.loader.loadSfx(Filename.fromOsSpecific(str(audio_dir / "engine.wav")))
        self.road = base.loader.loadSfx(Filename.fromOsSpecific(str(audio_dir / "road.wav")))
        self.impact = base.loader.loadSfx(Filename.fromOsSpecific(str(audio_dir / "impact.wav")))
        for sound in (self.engine, self.road):
            sound.setLoop(True)
            sound.setVolume(0)
            sound.play()
        self.engine_level = 0.0
        self.road_level = 0.0
        self.last_time = None
        self.last_collisions = 0
        self.impact_ready = 0.0

    def update(self, state, phase, control):
        now = state.time
        if self.last_time is not None and now < self.last_time:
            self.last_collisions = 0
            self.impact_ready = 0.0
        dt = 1 / 120 if self.last_time is None else max(1 / 240, min(0.1, now - self.last_time))
        self.last_time = now
        driving = phase.value in ("driving", "countdown")
        if driving:
            throttle = state.player.throttle if control is None else max(control.throttle, state.player.throttle)
            rpm = max(0.0, min(9000.0, state.player.rpm))
            engine_target = min(0.24, 0.025 + rpm / 9000 * 0.11 + throttle * 0.1)
            road_target = min(0.18, abs(state.player.speed) / 36 * 0.16)
            if state.player.surface != "asphalt":
                road_target *= 1.35
        else:
            engine_target = 0.0
            road_target = 0.0
        blend = min(1.0, dt * 7.0)
        self.engine_level += (engine_target - self.engine_level) * blend
        self.road_level += (road_target - self.road_level) * blend
        self.engine.setVolume(self.engine_level)
        self.road.setVolume(self.road_level)
        self.engine.setPlayRate(0.78 + rpm / 9000 * 0.5 if driving else 0.78)
        self.road.setPlayRate(0.88 + min(0.35, abs(state.player.speed) / 80))
        collisions = state.collisions
        if driving and collisions > self.last_collisions and now >= self.impact_ready:
            self.impact.setVolume(0.28)
            self.impact.play()
            self.impact_ready = now + 0.28
        self.last_collisions = collisions

    def close(self):
        for sound in (self.engine, self.road, self.impact):
            sound.stop()
