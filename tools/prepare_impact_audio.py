"""从许可已记录的现场录音制作短促撞击层和连续擦碰循环。"""

import hashlib
import json
import math
import subprocess
import wave
from array import array
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "source" / "phase6b_audio"
OUTPUT = ROOT / "assets" / "game" / "audio" / "impact"
RATE = 44100

SOURCES = {
    "car_body": (
        "https://freesound.org/people/harrisonlace/sounds/798843/",
        "https://cdn.freesound.org/previews/798/798843_9839964-hq.mp3",
        "4b19e0e78a8cfab8246d7a2bfcb47b17295500b569a221fb00da17beb4d847f5",
    ),
    "car_crash": (
        "https://freesound.org/people/magnuswaker/sounds/592388/",
        "https://cdn.freesound.org/previews/592/592388_11537497-hq.mp3",
        "0169d0fe29c4aba3cf1b0dd94c186a5fb917e9eef975c9a1485568d4a325d822",
    ),
    "car_crunch": (
        "https://freesound.org/people/craigsmith/sounds/675475/",
        "https://cdn.freesound.org/previews/675/675475_2524442-hq.mp3",
        "a3d3d530939fa704a43a11924c0283e9cd3cf5386f8a59c989f96864d73cd5f2",
    ),
    "metal_scrape": (
        "https://freesound.org/people/JSilverSound/sounds/615837/",
        "https://cdn.freesound.org/previews/615/615837_6566796-hq.mp3",
        "9e34a1d5c33a5333f03a6923e3b07a059295bed798bbf1330228099ac802bd29",
    ),
    "metal_hit": (
        "https://freesound.org/people/BehanSean/sounds/422438/",
        "https://cdn.freesound.org/previews/422/422438_6613494-hq.mp3",
        "5413f319e2018ddaba69bc03086412fa629489c51a262ea95d2e55f5ff500305",
    ),
    "glass": (
        "https://freesound.org/people/AlterKartoffelsack/sounds/465946/",
        "https://cdn.freesound.org/previews/465/465946_5855051-hq.mp3",
        "fc527db097a4e1b7321d661a25efb2483c6631a57f59b038fbe46ae7d32c9648",
    ),
    "plastic": (
        "https://freesound.org/people/Doshke/sounds/825839/",
        "https://cdn.freesound.org/previews/825/825839_13400336-hq.mp3",
        "dac230037fff4db2e29c8eef010f7c795d6f73a58b18eb110bcda238b710de0b",
    ),
    "hard_scrape": (
        "https://freesound.org/people/patchytherat/sounds/530989/",
        "https://cdn.freesound.org/previews/530/530989_5911297-hq.mp3",
        "fdcb5a3cdd97b7cc9fd28f9f8bc1be47e7a9b179f66e9c6b9a50643efd4f61e0",
    ),
}

# source, 起点秒, 最长截取秒, 目标峰值 dBFS, 滤波器。
ONE_SHOTS = {
    "transient_metal": [
        ("metal_hit", 0.0, 0.34, -9, "highpass=f=130"),
        ("car_crash", 0.0, 0.27, -9, "highpass=f=150"),
        ("car_body", 17.57, 0.32, -9, "highpass=f=140"),
    ],
    "transient_hard": [
        ("car_crash", 0.03, 0.28, -9, "highpass=f=130"),
        ("car_body", 1.36, 0.34, -9, "highpass=f=120"),
        ("car_body", 4.82, 0.34, -9, "highpass=f=150"),
    ],
    "body_light": [
        ("car_body", 0.0, 0.55, -11, "lowpass=f=2300"),
        ("car_body", 2.75, 0.55, -11, "lowpass=f=2300"),
        ("car_body", 7.8, 0.55, -11, "lowpass=f=2300"),
    ],
    "body_heavy": [
        ("car_body", 15.33, 0.72, -9, "lowpass=f=1250"),
        ("car_body", 20.08, 0.72, -9, "lowpass=f=1250"),
        ("car_body", 23.28, 0.72, -9, "lowpass=f=1250"),
    ],
    "crunch": [
        ("car_crunch", 0.05, 0.52, -11, "highpass=f=190,lowpass=f=4200"),
        ("car_crunch", 3.76, 0.52, -11, "highpass=f=190,lowpass=f=4200"),
        ("car_crunch", 6.79, 0.52, -11, "highpass=f=190,lowpass=f=4200"),
    ],
    "debris": [
        ("glass", 0.43, 0.50, -14, "highpass=f=500"),
        ("plastic", 0.15, 0.50, -14, "highpass=f=450"),
        ("car_crunch", 12.45, 0.45, -14, "highpass=f=600"),
    ],
}

LOOPS = {
    "scrape_metal": [
        ("metal_scrape", 3.0, 2.7, -15, "highpass=f=180,lowpass=f=6500"),
        ("metal_scrape", 9.0, 2.7, -15, "highpass=f=180,lowpass=f=6500"),
    ],
    "scrape_hard": [
        ("hard_scrape", 6.0, 3.0, -10, "highpass=f=100,lowpass=f=4400"),
        ("hard_scrape", 18.0, 3.0, -9, "highpass=f=100,lowpass=f=4400"),
    ],
}


def source_file(name):
    page, url, expected = SOURCES[name]
    path = SOURCE / f"{name}-hq.mp3"
    if not path.exists():
        request = Request(url, headers={"User-Agent": "CoastalDrive asset preparation"})
        path.write_bytes(urlopen(request, timeout=45).read())
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"Source hash changed: {name}: {page}")
    return path


def cut(source, start, duration, filters):
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start),
        "-t", str(duration), "-i", str(source), "-af", filters,
        "-ac", "1", "-ar", str(RATE), "-f", "s16le", "pipe:1",
    ]
    samples = array("h")
    samples.frombytes(subprocess.run(command, capture_output=True, check=True).stdout)
    return samples


def finish_one_shot(samples, target_db, max_gain=3.0):
    peak = max(abs(value) for value in samples)
    gate = max(90, peak * 0.10)
    onset = next((index for index, value in enumerate(samples) if abs(value) >= gate), 0)
    samples = samples[max(0, onset - round(RATE * 0.002)) :]
    peak = max(abs(value) for value in samples)
    gain = min(10 ** (target_db / 20) * 32767 / peak, max_gain)
    fade_in = round(RATE * 0.002)
    fade_out = min(round(RATE * 0.085), len(samples) // 3)
    for index in range(len(samples)):
        envelope = min(1.0, (index + 1) / fade_in, (len(samples) - index) / fade_out)
        samples[index] = round(samples[index] * gain * envelope)
    return samples


def finish_loop(samples, target_db):
    overlap = round(RATE * 0.24)
    # 一圈末尾与开头等功率交叉淡化；首尾都落在同一段的自然噪声上。
    result = array("h", samples[overlap:-overlap])
    for index in range(overlap):
        t = (index + 1) / (overlap + 1)
        result.append(round(samples[-overlap + index] * math.cos(t * math.pi / 2)
                            + samples[index] * math.sin(t * math.pi / 2)))
    peak = max(abs(value) for value in result)
    gain = min(10 ** (target_db / 20) * 32767 / peak, 3.0)
    result = array("h", (round(value * gain) for value in result))
    edge = round(RATE * 0.008)
    for index in range(edge):
        fade = (1 - math.cos(math.pi * index / edge)) / 2
        result[index] = round(result[index] * fade)
        result[-index - 1] = round(result[-index - 1] * fade)
    return result


def write_wave(path, samples):
    with wave.open(str(path), "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(RATE)
        clip.writeframes(samples.tobytes())


def build():
    SOURCE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pools = {}
    for layer, catalog in (("impact", ONE_SHOTS), ("scrape", LOOPS)):
        for name, entries in catalog.items():
            variants = []
            for index, (source, start, duration, peak_db, filters) in enumerate(entries, 1):
                samples = cut(source_file(source), start, duration, filters)
                samples = (finish_loop(samples, peak_db) if layer == "scrape"
                           else finish_one_shot(samples, peak_db,
                                                max_gain=8.0 if name == "debris" else 3.0))
                file_name = f"{name}_{index}.wav"
                path = OUTPUT / file_name
                write_wave(path, samples)
                variants.append({
                    "id": f"{name}_{index}", "path": f"impact/{file_name}",
                    "source": source, "start": start, "duration": duration,
                    "peak_dbfs": round(20 * math.log10(max(abs(v) for v in samples) / 32768), 2),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                })
            pools[name] = variants
    bank = {
        "version": 1,
        "calibration": "provisional; physical anchors from 6B-02 wall/rail probes",
        "severity_curve": [[0.0, 0.0], [0.6, 0.13], [2.0, 0.36],
                           [5.0, 0.65], [10.0, 0.9], [20.0, 1.0]],
        "pools": pools,
        "materials": {
            "vehicle": {"transient": "transient_metal", "scrape": "scrape_metal"},
            "metal_barrier": {"transient": "transient_metal", "scrape": "scrape_metal"},
            "hard_solid": {"transient": "transient_hard", "scrape": "scrape_hard"},
        },
        "mix": {"audible_floor": 0.04, "retrigger_ticks": 12, "upgrade_severity": 0.15,
                "upgrade_impulse_ratio": 1.6, "duck_start": 0.7},
    }
    manifest = OUTPUT.parent / "impact-bank.json"
    manifest.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {sum(map(len, pools.values()))} clips in {manifest.parent}")


if __name__ == "__main__":
    build()
