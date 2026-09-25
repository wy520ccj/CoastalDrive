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


if __name__ == "__main__":
    main()
