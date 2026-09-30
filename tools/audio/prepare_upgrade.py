"""离线制作V8声库、重制碰撞和原创双电台；运行游戏无需DSP或下载。"""

import argparse
import hashlib
import json
import math
import random
import sys
import wave
from array import array
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_impact_audio as recordings

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


def engine(rpm, loaded):
    # 每720°八次点火，两排交替不等间距共振形成V8低沉脉冲。
    cycles = round(3.6 * rpm / 120)
    count = round(cycles * 120 / rpm * RATE)
    samples = array("f")
    positions = (0, .125, .25, .375, .50, .625, .75, .875)
    strengths = (1.0, .68, .82, .92, .73, 1.0, .88, .65)
    noise = random.Random(8 + rpm + loaded)
    smooth_noise = 0.0
    for i in range(count):
        t = i / RATE
        phase = t * rpm / 120
        pulse = 0.0
        for start, strength in zip(positions, strengths):
            age = ((phase - start) % 1) * 120 / rpm
            pulse += strength * math.exp(-age * (240 if loaded else 340)) * (
                math.sin(age * math.tau * 112) + .42 * math.sin(age * math.tau * 235))
        smooth_noise += .18 * (noise.uniform(-1, 1) - smooth_noise)
        induction = smooth_noise * (.055 + .12 * loaded) * (
            .6 + .4 * math.sin(phase * math.tau * 4) ** 2)
        rumble = .1 * math.sin(phase * math.tau * 2)
        samples.append(math.tanh((pulse + rumble + induction) * (2 if loaded else 1.2)))
    mean = sum(samples) / len(samples)
    samples = array("f", (value - mean for value in samples))
    # 小幅环缝淡化，燃烧周期本身在首尾整周期闭合。
    edge = round(RATE * .003)
    for i in range(edge):
        samples[i] *= i / edge
        samples[-1-i] *= i / edge
    return samples


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


def music(night):
    # 32小节，和弦/低音/旋律/鼓组；整段原创，无商业游戏音轨。
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


def collisions():
    recordings.SOURCE.mkdir(parents=True, exist_ok=True)
    new_path = SOURCE / "squareal-car-crash.mp3"
    url = "https://cdn.freesound.org/previews/237/237375_1502374-hq.mp3"
    if not new_path.exists():
        new_path.write_bytes(urlopen(Request(url, headers={"User-Agent": "CoastalDrive"}),
                                    timeout=45).read())
    source_hash = hashlib.sha256(new_path.read_bytes()).hexdigest()
    manifest_path = SOURCE / "sources.json"
    expected = "6587ffc83281ecea17bf41a37e461c93d73424b478759e78dad35d71310823da"
    if source_hash != expected:
        raise ValueError("New crash source hash changed")
    source_manifest = {"squareal": {"page": "https://freesound.org/people/squareal/sounds/237375/",
                                   "url": url, "license": "CC0", "sha256": source_hash}}
    manifest_path.write_text(json.dumps(source_manifest, indent=2), encoding="utf-8")
    pools = {}
    catalog = {
        "transient_vehicle": ("new", (.418, .422, .426), .20, "highpass=f=65,lowpass=f=1600"),
        "transient_metal": ("metal_hit", (0, .006, .012), .23, "highpass=f=100,lowpass=f=3000"),
        "transient_hard": ("new", (.418, .422, .426), .18, "lowpass=f=1200"),
        "body_light": ("new", (.418, .422, .426), .24, "lowpass=f=550"),
        "body_heavy": ("new", (.418, .422, .426), .36, "lowpass=f=350,bass=g=4:f=90"),
        "body_metal": ("new", (.418, .422, .426), .34, "lowpass=f=450"),
        "body_hard": ("new", (.418, .422, .426), .30, "lowpass=f=300,bass=g=5:f=80"),
        "crunch": ("car_crunch", (.05, 3.76, 6.79), .18, "highpass=f=380,lowpass=f=4000"),
        "debris": ("plastic", (.15, .16, .17), .14, "highpass=f=1200,lowpass=f=5000"),
        "scrape_metal": ("metal_scrape", (3, 9), 3.4, "highpass=f=130,lowpass=f=6000"),
        "scrape_hard": ("hard_scrape", (6, 18), 3.4, "highpass=f=80,lowpass=f=3800"),
    }
    for pool, (source, starts, duration, filters) in catalog.items():
        origin = new_path if source == "new" else recordings.source_file(source)
        entries = []
        for index, start in enumerate(starts):
            rate = (1.0, .93, 1.06)[index]
            raw = recordings.cut(origin, start, duration,
                                 f"{filters},asetrate={round(RATE * rate)},aresample={RATE},"
                                 "acompressor=threshold=0.16:ratio=3:attack=1:release=100")
            if pool.startswith("scrape"):
                samples = recordings.finish_loop(raw, -6)
            else:
                raw = raw[:round(duration * RATE)]
                samples = recordings.finish_one_shot(raw, -4.5, max_gain=16)
                # 保留起音和短促共振，剔除源录音中后续滑动/摩擦，不叠加人工低频正弦。
                decay = 9 if pool.startswith("body") else 14
                samples = [x * math.exp(-max(0, i / RATE - .025) * decay)
                           for i, x in enumerate(samples)]
            path = OUTPUT / "impact" / f"{pool}_{index+1}.wav"
            peak = .78 if pool.startswith("transient") else .84 if pool.startswith("body") else .48 if pool == "crunch" else .35 if pool == "debris" else .62
            info = write(path, samples, peak)
            info.update(id=f"{pool}_{index+1}", source=source, start=start,
                        peak_dbfs=20 * math.log10(peak))
            entries.append(info)
        if pool.startswith("transient"):
            # 起音响度按前80ms校齐，随机variant不会突然变得软弱。
            windows = []
            clips = []
            for entry in entries:
                with wave.open(str(OUTPUT / entry["path"]), "rb") as clip:
                    pcm = array("h", clip.readframes(clip.getnframes()))
                clips.append(pcm)
                window = pcm[:round(.08 * RATE)]
                windows.append(math.sqrt(sum(x*x for x in window) / len(window)))
            target = min(windows)
            for entry, pcm, rms in zip(entries, clips, windows):
                pcm = array("h", (round(x * target / rms) for x in pcm))
                recordings.write_wave(OUTPUT / entry["path"], pcm)
                entry["peak_dbfs"] = 20 * math.log10(max(abs(x) for x in pcm) / 32768)
                entry["sha256"] = hashlib.sha256((OUTPUT / entry["path"]).read_bytes()).hexdigest()
        pools[pool] = entries
    bank = {"version": 2, "severity_curve": [[0, 0], [.6, .13], [2, .36],
                                              [5, .65], [10, .9], [20, 1]],
            "pools": pools, "source_manifest": source_manifest,
            "materials": {
                "vehicle": {"transient": "transient_vehicle", "body": "body_heavy", "scrape": "scrape_metal"},
                "metal_barrier": {"transient": "transient_metal", "body": "body_metal", "scrape": "scrape_metal"},
                "hard_solid": {"transient": "transient_hard", "body": "body_hard", "scrape": "scrape_hard"}},
            "mix": {"audible_floor": .04, "retrigger_ticks": 12, "upgrade_severity": .15,
                    "upgrade_impulse_ratio": 1.6, "duck_start": .6}}
    (OUTPUT / "impact-bank.json").write_text(json.dumps(bank, indent=2), encoding="utf-8")


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
        entries = [write(OUTPUT / "music" / f"{name}.wav", music(night), .65, stereo=True)
                   for night, name in enumerate(("sunset-run", "midnight-circuit"))]
        manifest["assets"] = [entry for entry in manifest["assets"]
                              if not entry["path"].startswith("music/")] + entries
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return
    assets = []
    for rpm in (900, 1800, 3200, 4700, 6500):
        for loaded, name in enumerate(("coast", "load")):
            assets.append(write(OUTPUT / "engine" / f"v8-{rpm}-{name}.wav", engine(rpm, loaded)))
    for name in ("asphalt", "gravel", "wind", "tire"):
        assets.append(write(OUTPUT / "driving" / f"{name}.wav", texture(name), .5))
    cues = {"select": ((650,), .075), "confirm": ((550, 825), .16),
            "countdown": ((660,), .16), "go": ((880, 1320), .30),
            "checkpoint": ((740, 990), .26), "success": ((523, 659, 784, 1047), .85),
            "finish": ((659, 784), .40), "failure": ((392, 330, 262), .55),
            "radio": ((1000, 720), .12)}
    for name, (notes, duration) in cues.items():
        assets.append(write(OUTPUT / "cues" / f"{name}.wav", cue(notes, duration), .45))
    for night, name in enumerate(("sunset-run", "midnight-circuit")):
        assets.append(write(OUTPUT / "music" / f"{name}.wav", music(night), .65, stereo=True))
    collisions()
    (OUTPUT / "upgrade-manifest.json").write_text(json.dumps({"version": 1, "assets": assets,
        "authorship": "Original offline procedural V8, textures, cues and instrumental compositions",
        "generator": "tools/audio/prepare_upgrade.py"}, indent=2), encoding="utf-8")
    print(f"Prepared {len(assets)} engine/driving/music/cue assets and v2 collision bank")


if __name__ == "__main__":
    main()
