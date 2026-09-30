"""从车辆实录制作引擎循环与车身撞击，游戏内不做信号处理。"""

import hashlib
import json
import math
import subprocess
import sys
import wave
from array import array
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_impact_audio as recordings

RATE = 44100
OUTPUT = ROOT / "assets/game/audio"
SOURCE = ROOT / "assets/source/audio-recorded"
SOURCES = {
    "mini-cooper": {
        "page": "https://freesound.org/people/TheLittleCrow/sounds/669618/",
        "url": "https://cdn.freesound.org/previews/669/669618_5672786-hq.mp3",
        "sha256": "5f487dd82d5c4a75e44e651dcaa9c48617d36c0e475cb167987ebc57dba9f07d",
        "license": "CC0", "author": "TheLittleCrow",
        "recording": "2019 Mini Cooper S; chassis left, engine block right contact microphones",
    },
    "hood-impact": {
        "page": "https://freesound.org/people/LPA134/sounds/329516/",
        "url": "https://cdn.freesound.org/previews/329/329516_424694-hq.mp3",
        "sha256": "6157ca24e7794bd1dc4a38791e8a044aa05af9372068c97d7001baa82d55a249",
        "license": "CC0", "author": "LPA134",
        "recording": "Car hood slammed in underground garage; Rode NT4; not an accident recording",
    },
}


def source_file(name):
    SOURCE.mkdir(parents=True, exist_ok=True)
    entry = SOURCES[name]
    path = SOURCE / f"{name}.mp3"
    if not path.exists():
        path.write_bytes(urlopen(Request(entry["url"], headers={"User-Agent": "CoastalDrive"}),
                                    timeout=45).read())
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError(f"录音校验失败：{name}")
    (SOURCE / "sources.json").write_text(json.dumps(SOURCES, indent=2), encoding="utf-8")
    return path


def write(path, samples, peak, remove_dc=True):
    mean = sum(samples) / len(samples) if remove_dc else 0
    samples = [value - mean for value in samples]
    gain = peak * 32767 / max(abs(value) for value in samples)
    pcm = array("h", (round(value * gain) for value in samples))
    path.parent.mkdir(parents=True, exist_ok=True)
    recordings.write_wave(path, pcm)
    return {"path": path.relative_to(OUTPUT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "duration": len(pcm) / RATE, "peak_dbfs": 20 * math.log10(peak)}


def engines():
    # 转速由点火频谱估计，不是录音现场的转速表测量。截取不同转速，避免一段怠速拉七倍。
    excerpts = ((900, .15, 1.2, 30), (1800, 3.05, .55, 62),
                (3200, 9.3, 2.0, 100), (4700, 30.0, 4.0, 144),
                (6500, 67.3, 1.0, 202))
    entries = []
    origin = source_file("mini-cooper")
    for rpm, start, duration, firing_hz in excerpts:
        command = ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(duration),
                   "-i", str(origin), "-af", "highpass=f=28", "-ar", str(RATE),
                   "-f", "f32le", "pipe:1"]
        raw = np.frombuffer(subprocess.run(command, capture_output=True, check=True).stdout,
                            dtype="<f4").reshape(-1, 2)
        # 升转速录音先依据点火谐波校稳音高，防止短循环重复播放时反复升降调。
        positions, frequencies = [], []
        window = round(.16 * RATE)
        candidates = np.linspace(firing_hz * .68, firing_hz * 1.65, 240)
        hz = np.fft.rfftfreq(32768, 1/RATE)
        for offset in range(0, len(raw)-window+1, round(.04 * RATE)):
            spectrum = np.abs(np.fft.rfft(raw[offset:offset+window, 1] * np.hanning(window),
                                          n=32768))
            scores = sum(np.interp(candidates*k, hz, spectrum)/k for k in (1, 2, 3))
            scores *= np.exp(-.5*((candidates-firing_hz)/(firing_hz*.4))**2)
            positions.append(offset + window/2)
            frequencies.append(candidates[np.argmax(scores)])
        steps = np.interp(np.arange(len(raw)), positions, frequencies)
        target_hz = rpm / 30
        phase = np.cumsum(steps / target_hz)
        sample_positions = np.interp(np.arange(phase[-1]), phase, np.arange(len(raw)))
        stabilized = np.column_stack([np.interp(sample_positions, np.arange(len(raw)), raw[:, c])
                                      for c in (0, 1)])
        for name, chassis in (("coast", .65), ("load", .25)):
            samples = stabilized[:, 0]*chassis + stabilized[:, 1]*(1-chassis)
            # 保留机械宽频细节，只去直流和次声；短循环按自身长度接缝。
            overlap = min(round(.12 * RATE), len(samples) // 5)
            loop = list(samples[overlap:])
            for i in range(overlap):
                amount = i / overlap
                loop[-overlap+i] = samples[-overlap+i] * (1-amount) + samples[i] * amount
            info = write(OUTPUT / "engine" / f"v8-{rpm}-{name}.wav", loop, .72)
            info.update(source="mini-cooper", start=start, input_seconds=duration,
                        estimated_firing_hz=firing_hz, target_firing_hz=target_hz,
                        stabilization="offline harmonic tracking and variable resampling",
                        chassis_mix=chassis, engine_block_mix=1-chassis,
                        note="Legacy v8 filename only; recording is a Mini Cooper S")
            entries.append(info)
    return entries


def collisions():
    hood = source_file("hood-impact")
    catalog = {
        "transient_vehicle": ("car_body", (0, 1.36, 2.75), .15, "highpass=f=850,lowpass=f=6500"),
        "transient_metal": ("metal_hit", (0, .006, .012), .23, "highpass=f=100,lowpass=f=3000"),
        "transient_hard": ("car_body", (4.82, 7.80, 9.35), .16, "highpass=f=700,lowpass=f=5000"),
        "body_light": ("car_body", (0, 1.36, 2.75), .24, "highpass=f=35,lowpass=f=4500"),
        "body_heavy": ("hood-impact", (.13, .135, .14), .36, "highpass=f=30,lowpass=f=4800"),
        "body_metal": ("car_body", (4.82, 7.80, 9.35), .34, "highpass=f=30,lowpass=f=4000"),
        "body_hard": ("hood-impact", (.13, .135, .14), .30, "highpass=f=30,lowpass=f=3200"),
        "crunch": ("car_crunch", (.05, 3.76, 6.79), .18, "highpass=f=380,lowpass=f=4000"),
        "debris": ("plastic", (.15, .16, .17), .14, "highpass=f=1200,lowpass=f=5000"),
        "scrape_metal": ("metal_scrape", (3, 9), 3.4, "highpass=f=130,lowpass=f=6000"),
        "scrape_hard": ("hard_scrape", (6, 18), 3.4, "highpass=f=80,lowpass=f=3800"),
    }
    pools = {}
    for pool, (source, starts, duration, filters) in catalog.items():
        origin = hood if source == "hood-impact" else recordings.source_file(source)
        entries = []
        for index, start in enumerate(starts):
            # 旧擦碰循环保持；车身使用各次独立实录，机盖只有一次实录，微小变调形成变体。
            rate = (1.0, .93, 1.06)[index] if pool.startswith("scrape") else (1, .985, 1.015)[index]
            chain = f"{filters},asetrate={round(RATE * rate)},aresample={RATE}"
            if pool.startswith("scrape"):
                chain += ",acompressor=threshold=0.16:ratio=3:attack=1:release=100"
            raw = recordings.cut(origin, start, duration, chain)
            if pool.startswith("scrape"):
                samples = recordings.finish_loop(raw, -6)
            else:
                raw = raw[:round(duration * RATE)]
                samples = recordings.finish_one_shot(raw, -4.5, max_gain=16)
                # 机盖录音的车库回声单独收短，车身实录不施加整段指数衰减。
                if source == "hood-impact":
                    samples = [x * math.exp(-max(0, i/RATE-.12)*10) for i, x in enumerate(samples)]
            path = OUTPUT / "impact" / f"{pool}_{index+1}.wav"
            peak = (.78 if pool.startswith("transient") else .84 if pool.startswith("body")
                    else .48 if pool == "crunch" else .35 if pool == "debris" else .62)
            if pool.startswith("scrape"):
                # 与PLAY-01-FIX的连续接触循环逐字节一致。
                info = write(path, samples, peak, remove_dc=False)
            else:
                info = write(path, samples, peak)
            info.update(id=f"{pool}_{index+1}", source=source, start=start)
            entries.append(info)
        if pool.startswith("transient"):
            clips = []
            levels = []
            for entry in entries:
                with wave.open(str(OUTPUT / entry["path"]), "rb") as clip:
                    pcm = array("h", clip.readframes(clip.getnframes()))
                clips.append(pcm)
                window = pcm[:round(.08 * RATE)]
                levels.append(math.sqrt(sum(x*x for x in window)/len(window)))
            for entry, pcm, level in zip(entries, clips, levels):
                pcm = array("h", (round(x * min(levels)/level) for x in pcm))
                recordings.write_wave(OUTPUT / entry["path"], pcm)
                entry["sha256"] = hashlib.sha256((OUTPUT / entry["path"]).read_bytes()).hexdigest()
                entry["peak_dbfs"] = 20 * math.log10(max(abs(x) for x in pcm)/32768)
        pools[pool] = entries
    bank = json.loads((OUTPUT / "impact-bank.json").read_text(encoding="utf-8"))
    bank.update(pools=pools, source_manifest={**SOURCES, "car_body": {
        "page": recordings.SOURCES["car_body"][0], "license": "CC0",
        "sha256": recordings.SOURCES["car_body"][2],
        "recording": "Hand strikes on an empty car body; not an accident recording"}},
        revision="AUDIO-02 physical car body/hood recordings; wideband, reduced layering")
    (OUTPUT / "impact-bank.json").write_text(json.dumps(bank, indent=2), encoding="utf-8")


def main():
    manifest_path = OUTPUT / "upgrade-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["assets"] = [entry for entry in manifest["assets"]
                          if not entry["path"].startswith("engine/")] + engines()
    manifest["authorship"] = "Recorded engine CC0 derivatives; original textures, cues and music"
    manifest["engine_sources"] = SOURCES
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    collisions()
    print("Prepared recorded engine and car-body bank")


if __name__ == "__main__":
    main()
