"""Small state-driven audio layer for the driving loop."""

import math

from panda3d.core import Filename

from paths import resource_root


class Soundscape:
    def __init__(self, base, master_volume=100, effects_volume=100):
        self.base = base
        audio_dir = resource_root() / "assets" / "game" / "audio"
        self.engine = base.loader.loadSfx(Filename.fromOsSpecific(str(audio_dir / "engine.wav")))
        self.engine_idle = base.loader.loadSfx(
            Filename.fromOsSpecific(str(audio_dir / "engine_idle.wav"))
        )
        self.road = base.loader.loadSfx(Filename.fromOsSpecific(str(audio_dir / "road.wav")))
        self.impacts = {
            kind: base.loader.loadSfx(Filename.fromOsSpecific(str(audio_dir / f"impact_{kind}.wav")))
            for kind in ("light", "side", "scrape", "heavy")
        }
        self.loops = (self.engine, self.engine_idle, self.road)
        for sound in self.loops:
            sound.setLoop(True)
            sound.setVolume(0)
        self.engine_level = 0.0
        self.road_level = 0.0
        self.master_volume = master_volume / 100
        self.effects_volume = effects_volume / 100
        self.loops_playing = False
        self.last_time = None
        self.last_collisions = 0
        self.previous_velocity = None
        self.impact_ready = 0.0
        self.closed = False

    def update(self, state, phase, control):
        now = state.time
        if self.last_time is not None and now < self.last_time:
            self.last_collisions = 0
            self.impact_ready = 0.0
            self.previous_velocity = None
        dt = 1 / 120 if self.last_time is None else max(1 / 240, min(0.1, now - self.last_time))
        self.last_time = now
        driving = phase.value in ("driving", "countdown")
        if driving:
            throttle = state.player.throttle if control is None else max(control.throttle, state.player.throttle)
            rpm = max(0.0, min(9000.0, state.player.rpm))
            engine_target = min(0.2, 0.1 + rpm / 9000 * 0.065 + throttle * 0.03)
            road_target = min(0.075, abs(state.player.speed) / 36 * 0.07)
            if state.player.surface != "asphalt":
                road_target *= 1.2
        else:
            engine_target = 0.0
            road_target = 0.0
        blend = min(1.0, dt * 7.0)
        self.engine_level += (engine_target - self.engine_level) * blend
        self.road_level += (road_target - self.road_level) * blend
        audible = driving and self.master_volume > 0 and self.effects_volume > 0
        if audible:
            if not self.loops_playing:
                for sound in self.loops:
                    sound.play()
                self.loops_playing = True
            volume = self.master_volume * self.effects_volume
            idle_mix = max(0.0, min(1.0, (4400 - rpm) / 2500))
            self.engine_idle.setVolume(self.engine_level * idle_mix ** 0.5 * volume)
            self.engine.setVolume(self.engine_level * (1 - idle_mix) ** 0.5 * volume)
            self.road.setVolume(self.road_level * volume)
        else:
            self._stop_loops()
        self.engine_idle.setPlayRate(0.92 + rpm / 9000 * 0.08 if driving else 0.92)
        self.engine.setPlayRate(0.58 + rpm / 9000 * 0.44 if driving else 0.58)
        self.road.setPlayRate(1.0)
        collisions = state.collisions
        if audible and collisions > self.last_collisions and now >= self.impact_ready:
            kind = collision_sound_kind(
                self.previous_velocity,
                state.player.velocity,
                state.player.heading,
                state.player.speed,
            )
            volume = {"light": 0.22, "side": 0.46, "scrape": 0.34, "heavy": 0.68}[kind]
            impact = self.impacts[kind]
            impact.setVolume(volume * self.master_volume * self.effects_volume)
            impact.play()
            self.impact_ready = now + 0.7
        self.last_collisions = collisions
        self.previous_velocity = (
            tuple(state.player.velocity) if driving and state.player.velocity is not None else None
        )

    def set_volumes(self, master_volume, effects_volume):
        self.master_volume = max(0, min(100, master_volume)) / 100
        self.effects_volume = max(0, min(100, effects_volume)) / 100
        if self.master_volume == 0 or self.effects_volume == 0:
            self._stop_loops()
            self._stop_impacts()

    def _stop_loops(self):
        if self.loops_playing:
            for sound in self.loops:
                sound.stop()
            self.loops_playing = False
        for sound in self.loops:
            sound.setVolume(0)
        self.engine_level = 0.0
        self.road_level = 0.0

    def _stop_impacts(self):
        for impact in self.impacts.values():
            impact.stop()

    def close(self):
        if self.closed:
            return
        self._stop_loops()
        self._stop_impacts()
        self.closed = True


def collision_sound_kind(previous_velocity, velocity, heading, speed):
    """根据碰撞前后的速度变化，选择轻碰、侧撞、擦碰或重撞录音。"""
    if previous_velocity is None or velocity is None:
        return "light"

    change = tuple(before - after for before, after in zip(previous_velocity, velocity))
    angle = math.radians(heading)
    forward = (-math.sin(angle), math.cos(angle))
    right = (math.cos(angle), math.sin(angle))
    longitudinal = abs(change[0] * forward[0] + change[1] * forward[1])
    lateral = abs(change[0] * right[0] + change[1] * right[1])
    strength = math.hypot(longitudinal, lateral)

    if abs(speed) >= 12 and lateral >= 0.35 and lateral > longitudinal * 0.65 and strength < 2.5:
        return "scrape"
    if strength < 1.25:
        return "light"
    if lateral >= 0.75 and lateral > longitudinal * 1.1:
        return "side"
    if longitudinal >= 2:
        return "heavy"
    return "light"
