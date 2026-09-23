"""从已核对许可的录音制作驾驶声音。需要 ffmpeg 和 tar。"""

import hashlib
import subprocess
import urllib.request
import wave
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "source" / "phase6b_audio"
OUTPUT = ROOT / "assets" / "game" / "audio"
RATE = 44100

SOURCES = {
    "engine-loop.7z": (
        "https://opengameart.org/sites/default/files/engine-loop.7z",
        "06b14b760fde613b357d043517f604dfde024318e764dff209a179ea39c566d6",
    ),
    "engine-idle-hq.mp3": (
        "https://cdn.freesound.org/previews/818/818291_13610145-hq.mp3",
        "4686992f5c2608d0f37e06eda5c12e27c616c50a6f88b0b81c55bf7fec03caba",
    ),
    "road-driving-hq.mp3": (
        "https://cdn.freesound.org/previews/495/495795_8972317-hq.mp3",
        "95864b36654fa08fcca505d0b6bc835055930408e683ac0b2b40fb86f7534c72",
    ),
    "impact-light-hq.mp3": (
        "https://cdn.freesound.org/previews/385/385940_7097737-hq.mp3",
        "76a11562089a88c6334f0b99845033c1b7aab54c3fda57e09840684543abac7f",
    ),
    "impact-metal-hq.mp3": (
        "https://cdn.freesound.org/previews/385/385937_7097737-hq.mp3",
        "8dea59e14dacc8cf60d5ad966a51ecf9282e951997eeb883c156d58bf139dbf0",
    ),
    "impact-scrape-hq.mp3": (
        "https://cdn.freesound.org/previews/385/385939_7097737-hq.mp3",
        "35cee69262957589433ba055d6e270c65400bb543b52827c4333829d5abac291",
    ),
    "impact-heavy-hq.mp3": (
        "https://cdn.freesound.org/previews/385/385938_7097737-hq.mp3",
        "5acf613452f0c78b9a8cfcd91b18b8efc76b8c5c6f3d714595b9e63d8030630c",
    ),
}


def source_file(name):
    url, expected_hash = SOURCES[name]
    path = SOURCE / name
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(f"Source hash changed: {name}")
    return path


def convert(source, output, *, start=None, duration=None, filters=None):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if start is not None:
        command += ["-ss", str(start)]
    if duration is not None:
        command += ["-t", str(duration)]
    command += ["-i", str(source)]
    if filters:
        command += ["-af", filters]
    command += ["-ac", "1", "-ar", str(RATE), "-c:a", "pcm_s16le", str(output)]
    subprocess.run(command, check=True)


def loop_crossfade(source, output, seconds):
    with wave.open(str(source), "rb") as audio:
        assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
        samples = array("h")
        samples.frombytes(audio.readframes(audio.getnframes()))
    overlap = round(seconds * RATE)
    body = samples[overlap:-overlap]
    tail = samples[-overlap:]
    head = samples[:overlap]
    result = array("h", body)
    for index in range(overlap):
        amount = (index + 1) / (overlap + 1)
        result.append(round(tail[index] * (1 - amount) + head[index] * amount))
    with wave.open(str(output), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(RATE)
        audio.writeframes(result.tobytes())


def main():
    SOURCE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        source_file(name)
    subprocess.run(["tar", "-xf", str(SOURCE / "engine-loop.7z"), "-C", str(SOURCE)], check=True)

    convert(
        SOURCE / "engine-loop" / "engine-loop-1-normalized.wav",
        OUTPUT / "engine.wav",
        filters="volume=-8dB",
    )
    convert(
        SOURCE / "engine-idle-hq.mp3",
        SOURCE / "idle-cut.wav",
        start=0.75,
        duration=5,
        filters="volume=20dB",
    )
    loop_crossfade(SOURCE / "idle-cut.wav", OUTPUT / "engine_idle.wav", 0.25)
    convert(
        SOURCE / "road-driving-hq.mp3",
        SOURCE / "road-cut.wav",
        start=3,
        duration=7,
        filters="highpass=f=160,lowpass=f=4500,volume=26dB",
    )
    loop_crossfade(SOURCE / "road-cut.wav", OUTPUT / "road.wav", 0.4)
    convert(
        SOURCE / "impact-light-hq.mp3",
        OUTPUT / "impact_light.wav",
        duration=1.0,
        filters="alimiter=limit=0.95",
    )
    convert(
        SOURCE / "impact-metal-hq.mp3",
        OUTPUT / "impact_side.wav",
        duration=1.5,
        filters="volume=-5dB",
    )
    convert(
        SOURCE / "impact-scrape-hq.mp3",
        OUTPUT / "impact_scrape.wav",
        start=0.2,
        duration=1.45,
        filters="volume=4dB,afade=t=in:st=0:d=0.03,afade=t=out:st=1.2:d=0.25,alimiter=limit=0.95",
    )
    convert(
        SOURCE / "impact-heavy-hq.mp3",
        OUTPUT / "impact_heavy.wav",
        duration=0.75,
        filters="volume=2dB,alimiter=limit=0.95",
    )


if __name__ == "__main__":
    main()
