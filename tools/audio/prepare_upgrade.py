"""离线制作实录声库、授权电台与原创首页曲；运行游戏无需DSP或下载。"""

import argparse
import hashlib
import json
import math
import random
import sys
import wave
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from prepare_music import prepare as prepare_music
from prepare_recorded import collisions, engines

RATE = 44100
OUTPUT = ROOT / "assets/game/audio"
SOURCE = ROOT / "assets/source/audio-upgrade"


def write(path, samples, peak=0.72, stereo=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    maximum = max(abs(x) for x in samples)
    gain = peak * 32767 / maximum
    pcm = array("h", (round(x * gain) for x in samples))
    with wave.open(str(path), "wb") as clip:
        clip.setnchannels(2 if stereo else 1)
        clip.setsampwidth(2)
        clip.setframerate(RATE)
        clip.writeframes(pcm.tobytes())
    return {"path": path.relative_to(OUTPUT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "duration": len(pcm) / RATE / (2 if stereo else 1)}


def texture(name):
    rng = random.Random(1977 + len(name))
    samples = array("f")
    low = 0.0
    for i in range(RATE * 4):
        noise = rng.uniform(-1, 1)
        low += .022 * (noise - low)
        t = i / RATE
        if name == "wind":
            value = low * 1.9
        elif name == "asphalt":
            value = .3 * noise + low
        elif name == "gravel":
            value = noise * (.3 + .7 * math.sin(math.tau * 11 * t) ** 8) + low
        else:
            value = .6 * math.sin(math.tau * 1160 * t + .8 * math.sin(math.tau * 7 * t))
            value += .17 * noise
        samples.append(value)
    edge = int(.01 * RATE)
    for i in range(edge):
        samples[i] *= i / edge
        samples[-i-1] *= i / edge
    return samples


def cue(notes, duration):
    samples = array("f", [0.0]) * round(duration * RATE)
    length = duration / len(notes)
    for n, frequency in enumerate(notes):
        for i in range(round(length * RATE)):
            t = i / RATE
            offset = round(n * length * RATE) + i
            if offset < len(samples):
                envelope = min(1, t / .008) * max(0, 1 - t / length) ** 2
                samples[offset] = envelope * (math.sin(math.tau * frequency * t) +
                                              .18 * math.sin(math.tau * frequency * 2 * t))
    return samples


def home_music():
    # 保留原海岸曲作为首页BGM，固定原编曲以便逐字节复现。
    night = False
    bpm = 112 if night else 104
    beat = 60 / bpm
    duration = beat * 128
    count = round(duration * RATE)
    left = array("f", [0.0]) * count
    right = array("f", [0.0]) * count
    rng = random.Random(2077 if night else 1986)
    chords = ((45, 48, 52, 55), (41, 45, 48, 52), (48, 52, 55, 59), (43, 47, 50, 55))

    def note(midi, start, length, gain, pan=0, pluck=False):
        freq = 440 * 2 ** ((midi - 69) / 12)
        offset = round(start * RATE)
        for i in range(round(length * RATE)):
            index = (offset + i) % count
            t = i / RATE
            env = min(1, t / (.01 if pluck else .15)) * min(1, (length - t) / .14)
            if pluck:
                env *= math.exp(-t * 4)
            value = math.sin(math.tau * freq * t) + .23 * math.sin(math.tau * freq * 2 * t)
            value += .09 * math.sin(math.tau * freq * 3 * t)
            value *= env * gain
            left[index] += value * (1 - pan) / 2
            right[index] += value * (1 + pan) / 2

    for bar in range(32):
        chord = chords[(bar // 2) % 4]
        start = bar * beat * 4
        for j, midi in enumerate(chord):
            note(midi + 12, start, beat * 4.1, .10, (j - 1.5) * .32)
        for b in range(4):
            note(chord[0] - 12, start + beat * b, beat * .72, .21, pluck=True)
        for b in range(8):
            note(chord[(b + bar) % 4] + (24 if night else 12),
                 start + beat * b / 2, beat * .85, .065, math.sin(b) * .55, True)
        if bar >= 2:
            for b, midi in enumerate((chord[2]+24, chord[1]+24, chord[0]+24, chord[3]+12)):
                note(midi, start + b * beat + beat * .25, beat * 1.1, .09, -.1, True)
    for b in range(128):
        start = round(b * beat * RATE)
        # 海岸台使用有音高的轻打击乐，取消白噪军鼓和高通嘶声。
        smooth = 0.0
        for i in range(round(RATE * .22)):
            index = (start + i) % count
            t = i / RATE
            kick = .26 * math.exp(-t * 24) * math.sin(math.tau * (
                49 * t + 60 * (1 - math.exp(-t * 36)) / 36)) if (night or b % 2 == 0) else 0
            smooth += .12 * (rng.uniform(-1, 1) - smooth)
            snare = 0.0
            if b % 2:
                snare = (.045 * math.sin(math.tau * 185 * t) * math.exp(-t * 48) +
                         (.022 * smooth * math.exp(-t * 55) if night else 0))
            left[index] += kick + snare
            right[index] += kick + snare
        for subdivision in range(2):
            offset = start + round(subdivision * beat * RATE / 2)
            for i in range(round(RATE * .04)):
                t = i / RATE
                value = .009 * math.sin(math.tau * 1600 * t) * math.exp(-t * 210)
                value *= min(1, t / .001)
                left[(offset + i) % count] += value * .7
                right[(offset + i) % count] += value
    stereo = array("f")
    for i in range(count):
        # 段首/尾1拍淡化，回到同一和声根音的循环接缝。
        fade = min(1, i / (RATE * beat), (count - i - 1) / (RATE * beat))
        stereo.extend((math.tanh(left[i]) * fade, math.tanh(right[i]) * fade))
    return stereo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=("all", "music", "impact"), default="all")
    args = parser.parse_args()
    SOURCE.mkdir(parents=True, exist_ok=True)
    if args.section == "impact":
        collisions()
        return
    if args.section == "music":
        manifest_path = OUTPUT / "upgrade-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = prepare_music()
        entries.append(write(OUTPUT / "music/home-coast.wav", home_music(), .65, stereo=True))
        manifest["assets"] = [entry for entry in manifest["assets"]
                              if not entry["path"].startswith("music/")] + entries
        manifest["authorship"] = ("Recorded engine CC0 derivatives; original textures, cues "
                                  "and home BGM; CC BY 4.0 radio music")
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return
    assets = engines()
    for name in ("asphalt", "gravel", "wind", "tire"):
        assets.append(write(OUTPUT / "driving" / f"{name}.wav", texture(name), .5))
    cues = {"select": ((650,), .075), "confirm": ((550, 825), .16),
            "countdown": ((660,), .16), "go": ((880, 1320), .30),
            "checkpoint": ((740, 990), .26), "success": ((523, 659, 784, 1047), .85),
            "finish": ((659, 784), .40), "failure": ((392, 330, 262), .55),
            "radio": ((1000, 720), .12)}
    for name, (notes, duration) in cues.items():
        assets.append(write(OUTPUT / "cues" / f"{name}.wav", cue(notes, duration), .45))
    assets.extend(prepare_music())
    assets.append(write(OUTPUT / "music/home-coast.wav", home_music(), .65, stereo=True))
    collisions()
    (OUTPUT / "upgrade-manifest.json").write_text(json.dumps({"version": 1, "assets": assets,
        "authorship": "Recorded engine CC0 derivatives; original textures, cues and home BGM; CC BY 4.0 radio music",
        "generator": "tools/audio/prepare_upgrade.py"}, indent=2), encoding="utf-8")
    print(f"Prepared {len(assets)} engine/driving/music/cue assets and v2 collision bank")


if __name__ == "__main__":
    main()
