"""把确定的碰撞事实变成有上限的汽车撞击层与持续擦碰。"""

import json
import math
import random
import time
import wave
from dataclasses import dataclass
from itertools import pairwise

from panda3d.core import Filename

from vehicle_config import CAR

LIMITS = {"transient": 3, "body": 3, "crunch": 2, "debris": 2, "scrape": 1}


def severity_for(impulse, curve, mass=CAR.mass):
    """冲量等效速度经对数距离插值，保留轻撞到重撞的动态。"""
    q = max(0.0, impulse / mass)
    if q >= curve[-1][0]:
        return curve[-1][1]
    for (left_q, left_s), (right_q, right_s) in pairwise(curve):
        if q <= right_q:
            position = (math.log1p(q) - math.log1p(left_q)) / (
                math.log1p(right_q) - math.log1p(left_q)
            )
            return left_s + (right_s - left_s) * position
    return 0.0


@dataclass
class Voice:
    sound: object
    layer: str
    variant: str
    severity: float
    gain: float
    play_rate: float
    started: float
    ends: float
    event_id: str


class ImpactAudio:
    def __init__(self, base, audio_dir, diagnostic=None):
        self.base = base
        self.audio_dir = audio_dir
        self.bank = json.loads((audio_dir / "impact-bank.json").read_text(encoding="utf-8"))
        self.random = random.Random(61734)
        self.diagnostic = diagnostic
        self.samples = {}
        self.bags = {}
        self.last_variants = {}
        self.voices = []
        self.scrape_sound = None
        self.scrape_variant = None
        self.scrape_source = None
        self.scrape_level = 0.0
        self.scrape_target = 0.0
        self.scrape_age = 0
        self.scrape_misses = 0
        self.scrape_release_level = 0.0
        self.scrape_state = "off"
        self.duck = 1.0
        self.duck_until = 0.0
        self.time = 0.0
        self.epoch = None
        self.seen = set()
        self.recent = {}
        self.last_major = None
        for pool, entries in self.bank["pools"].items():
            layer = ("scrape" if pool.startswith("scrape") else
                     "transient" if pool.startswith("transient") else
                     "body" if pool.startswith("body") else pool)
            handles = []
            for entry in entries:
                path = audio_dir / entry["path"]
                with wave.open(str(path), "rb") as clip:
                    length = clip.getnframes() / clip.getframerate()
                sounds = tuple(base.loader.loadSfx(Filename.fromOsSpecific(str(path)))
                               for _ in range(LIMITS[layer]))
                for sound in sounds:
                    sound.setVolume(0)
                    if layer == "scrape":
                        sound.setLoop(True)
                handles.append((entry["id"], sounds, length))
            self.samples[pool] = handles

    def set_diagnostic(self, diagnostic):
        self.diagnostic = diagnostic

    def _log(self, row):
        if self.diagnostic is not None:
            self.diagnostic.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _variant(self, pool):
        entries = self.samples[pool]
        bag = self.bags.setdefault(pool, [])
        if not bag:
            bag.extend(range(len(entries)))
            self.random.shuffle(bag)
            if len(bag) > 1 and entries[bag[-1]][0] == self.last_variants.get(pool):
                bag[0], bag[-1] = bag[-1], bag[0]
        chosen = bag.pop()
        self.last_variants[pool] = entries[chosen][0]
        return entries[chosen]

    def _free_handle(self, handles):
        occupied = {voice.sound for voice in self.voices}
        if self.scrape_sound is not None:
            occupied.add(self.scrape_sound)
        return next((sound for sound in handles if sound not in occupied), None)

    def _play_layer(self, pool, layer, event, severity, gain, scale):
        variants = self.samples[pool]
        if not variants:
            return None
        variant, handles, length = self._variant(pool)
        active = [voice for voice in self.voices if voice.layer == layer]
        sound = self._free_handle(handles)
        if len(active) >= LIMITS[layer] or sound is None:
            candidates = active if len(active) >= LIMITS[layer] else self.voices
            if not candidates:
                return None
            weakest = min(candidates, key=lambda voice: (voice.severity, voice.started))
            if weakest.severity > severity and layer in ("crunch", "debris"):
                return None
            weakest.sound.stop()
            self.voices.remove(weakest)
            self._log({"type": "voice_steal", "victim": weakest.event_id,
                       "layer": weakest.layer, "by": event.event_id})
            sound = self._free_handle(handles)
            if sound is None:
                # 各 variant 都忙时重用同池最弱句柄；总声数仍不增加。
                in_pool = [voice for voice in self.voices if voice.sound in handles]
                if not in_pool:
                    return None
                victim = min(in_pool, key=lambda voice: (voice.severity, voice.started))
                victim.sound.stop()
                self.voices.remove(victim)
                sound = victim.sound
        variation = self.random.uniform(-0.5, 0.5)
        rate = self.random.uniform(0.97, 1.03)
        volume = gain * 10 ** (variation / 20) * scale
        sound.setPlayRate(rate)
        sound.setVolume(volume)
        x = (-0.16 if event.zone == "left" else 0.16 if event.zone == "right" else 0.0)
        sound.set3dAttributes(x, 1.0, 0.0, 0.0, 0.0, 0.0)
        sound.play()
        self.voices.append(Voice(sound, layer, variant, severity, gain * 10 ** (variation / 20),
                                 rate, self.time, self.time + length / rate, event.event_id))
        return variant

    def _key(self, event):
        return (event.material, event.sources, event.zone)

    def _accept(self, event, severity):
        key = self._key(event)
        previous = self.recent.get(key)
        reason = None
        mix = self.bank["mix"]
        if (self.last_major is not None and
                0 < event.tick - self.last_major[0] <= 18 and
                severity < self.last_major[1] * 0.25):
            reason = "major-impact-tail"
        if (previous and event.tick - previous[0] < mix["retrigger_ticks"] and
                (severity < previous[1] + mix["upgrade_severity"] or
                 event.excess_impulse < previous[2] * mix["upgrade_impulse_ratio"])):
            reason = "same-source-cluster"
        if reason is None:
            self.recent[key] = (event.tick, severity, event.excess_impulse)
            if severity >= 0.65:
                self.last_major = (event.tick, severity)
        for old_key, values in tuple(self.recent.items()):
            if event.tick - values[0] > 120:
                del self.recent[old_key]
        return reason

    def _events_this_frame(self, impacts):
        chosen = []
        for event in impacts:
            if event.event_id in self.seen:
                continue
            self.seen.add(event.event_id)
            key = self._key(event)
            match = next((index for index, prior in enumerate(chosen)
                          if self._key(prior) == key and
                          event.tick - prior.tick < self.bank["mix"]["retrigger_ticks"]), None)
            if match is None:
                chosen.append(event)
            elif event.excess_impulse > chosen[match].excess_impulse:
                chosen[match] = event
        if len(self.seen) > 256:
            self.seen = {event.event_id for event in impacts}
        return chosen

    def _start_impact(self, event, scale):
        severity = severity_for(event.excess_impulse, self.bank["severity_curve"])
        suppressed = self._accept(event, severity)
        if suppressed is None and severity < self.bank["mix"]["audible_floor"]:
            suppressed = "below-audible-floor"
        if suppressed is not None:
            self._log({"type": "decision", "event_id": event.event_id,
                       "tick": event.tick, "material": event.material,
                       "raw_impulse": event.raw_impulse, "normal": event.normal_speed,
                       "tangential": event.tangential_speed, "severity": severity,
                       "zone": event.zone, "layers": [], "suppressed": suppressed})
            return
        pools = self.bank["materials"][event.material]
        layers = []
        transient_gain = 0.25 + 0.5 * severity
        if event.zone in ("left", "right"):
            transient_gain *= 1.05
        variant = self._play_layer(pools["transient"], "transient", event, severity,
                                   transient_gain, scale)
        if variant:
            layers.append(("transient", variant))
        body_pool = "body_heavy" if severity >= 0.45 else "body_light"
        body_gain = (0.12 + 0.48 * severity) * (1.06 if event.zone == "front" else 1.0)
        variant = self._play_layer(body_pool, "body", event, severity, body_gain, scale)
        if variant:
            layers.append(("body", variant))
        if severity > 0.42:
            variant = self._play_layer("crunch", "crunch", event, severity,
                                       (severity - 0.42) * 0.45, scale)
            if variant:
                layers.append(("crunch", variant))
        if severity > 0.7 and self.random.random() < min(0.65, 0.2 + severity - 0.7):
            variant = self._play_layer("debris", "debris", event, severity, 0.12, scale)
            if variant:
                layers.append(("debris", variant))
        if severity >= self.bank["mix"]["duck_start"]:
            self.duck_until = max(self.duck_until, self.time + 0.06)
        details = [
            {"layer": voice.layer, "variant": voice.variant,
             "gain": round(voice.gain * scale, 4), "pitch": round(voice.play_rate, 4)}
            for voice in self.voices if voice.event_id == event.event_id
        ]
        self._log({"type": "decision", "event_id": event.event_id, "tick": event.tick,
                   "sources": event.sources, "material": event.material,
                   "raw_impulse": event.raw_impulse, "excess_impulse": event.excess_impulse,
                   "normal": event.normal_speed, "tangential": event.tangential_speed,
                   "severity": round(severity, 4), "zone": event.zone,
                   "layers": layers, "layer_mix": details, "voices": len(self.voices),
                   "scrape": self.scrape_state, "duck": round(self.duck, 3),
                   "play_monotonic_ns": time.perf_counter_ns()})

    def _update_scrape(self, contacts, dt, scale):
        previous_state = self.scrape_state
        candidates = [contact for contact in contacts
                      if contact.tangential_speed >= 1.6 and contact.raw_impulse >= 25]
        contact = max(candidates, key=lambda item: item.tangential_speed * item.raw_impulse,
                      default=None)
        current = next((item for item in candidates
                        if (item.material, item.sources) == self.scrape_source), None)
        if (current is not None and contact is not None and
                contact.tangential_speed * contact.raw_impulse <
                current.tangential_speed * current.raw_impulse * 1.2):
            contact = current
        source = (contact.material, contact.sources) if contact else None
        if contact is not None:
            self.scrape_misses = 0
            self.scrape_age = self.scrape_age + 1 if source == self.scrape_source else 1
            if self.scrape_sound is None and self.scrape_age >= 2:
                pool = self.bank["materials"][contact.material]["scrape"]
                variant, handles, _ = self._variant(pool)
                self.scrape_sound = handles[0]
                self.scrape_sound.setVolume(0)
                self.scrape_sound.setPlayRate(1.0)
                self.scrape_sound.play()
                self.scrape_variant = variant
                self.scrape_state = "attack"
                self._log({"type": "scrape", "state": "attack", "tick": contact.tick,
                           "material": contact.material, "variant": variant})
            elif self.scrape_sound is not None and source != self.scrape_source:
                self.scrape_sound.stop()
                self.scrape_sound = None
                self.scrape_level = 0.0
                self.scrape_age = 1
                self.scrape_state = "off"
        else:
            self.scrape_misses += 1
            if self.scrape_misses < 3:
                source = self.scrape_source
            else:
                if self.scrape_misses == 3:
                    self.scrape_release_level = self.scrape_level
                self.scrape_age = 0
        if source is not None:
            self.scrape_source = source
        if self.scrape_sound is not None and contact is not None:
            speed = min(1.0, (contact.tangential_speed - 1.6) / 9.0)
            load = min(1.0, contact.raw_impulse / 170)
            self.scrape_target = (0.10 + 0.25 * speed) * load
            self.scrape_sound.setPlayRate(0.92 + 0.16 * speed)
        elif self.scrape_misses >= 3:
            self.scrape_target = 0.0
        if contact is None and self.scrape_misses >= 3:
            self.scrape_level = max(0.0, self.scrape_level - dt *
                                    self.scrape_release_level / 0.07)
        else:
            rise = self.scrape_target > self.scrape_level
            blend = min(1.0, dt / (0.025 if rise else 0.07))
            self.scrape_level += (self.scrape_target - self.scrape_level) * blend
        if self.scrape_sound is not None:
            self.scrape_sound.setVolume(self.scrape_level * scale)
            if self.scrape_target == 0 and self.scrape_level < 0.005:
                self.scrape_sound.stop()
                self.scrape_sound = None
                self.scrape_level = 0.0
                self.scrape_source = None
                self.scrape_state = "off"
                self._log({"type": "scrape", "state": "off"})
            elif self.scrape_target == 0:
                self.scrape_state = "release"
            else:
                self.scrape_state = "sustain"
        if self.scrape_state != previous_state and self.scrape_state in ("sustain", "release"):
            self._log({"type": "scrape", "state": self.scrape_state,
                       "tick": contact.tick if contact else None,
                       "material": contact.material if contact else None,
                       "normal": contact.normal_speed if contact else None,
                       "tangential": contact.tangential_speed if contact else None,
                       "raw_impulse": contact.raw_impulse if contact else None,
                       "volume": round(self.scrape_level * scale, 4)})

    def update(self, impacts, contacts, dt, scale, *, epoch, driving=True,
               accept_new_impacts=None, maintain_impact_tails=False):
        self.time += max(0.0, min(dt, 0.1))
        if epoch is not None and self.epoch is not None and epoch != self.epoch:
            self.stop()
            self.seen.clear()
            self.bags.clear()
            self.last_variants.clear()
        self.epoch = epoch
        if accept_new_impacts is None:
            accept_new_impacts = driving
        if (not driving and not accept_new_impacts and not maintain_impact_tails) or scale <= 0:
            self.seen.update(event.event_id for event in impacts)
            self.stop()
            return 1.0
        if not accept_new_impacts:
            self.seen.update(event.event_id for event in impacts)
        for voice in self.voices[:]:
            if self.time >= voice.ends:
                voice.sound.stop()
                self.voices.remove(voice)
            else:
                voice.sound.setVolume(voice.gain * scale)
        if accept_new_impacts:
            for event in self._events_this_frame(impacts):
                self._start_impact(event, scale)
        if driving:
            self._update_scrape(contacts, dt, scale)
        elif self.scrape_sound is not None:
            self.scrape_sound.stop()
            self.scrape_sound = None
            self.scrape_source = None
            self.scrape_level = self.scrape_target = 0.0
            self.scrape_state = "off"
        target = 0.71 if self.time < self.duck_until else 1.0
        blend = min(1.0, dt / (0.01 if target < self.duck else 0.18))
        self.duck += (target - self.duck) * blend
        return self.duck

    def stop(self):
        for voice in self.voices:
            voice.sound.stop()
        self.voices.clear()
        if self.scrape_sound is not None:
            self.scrape_sound.stop()
        self.scrape_sound = None
        self.scrape_variant = None
        self.scrape_source = None
        self.scrape_level = self.scrape_target = 0.0
        self.scrape_age = 0
        self.scrape_misses = 0
        self.scrape_release_level = 0.0
        self.scrape_state = "off"
        self.duck = 1.0
        self.duck_until = 0.0
        self.recent.clear()
        self.last_major = None
