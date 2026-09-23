"""Generate the small original WAV clips used by the driving soundscape."""

import argparse
import math
import random
import struct
import wave
from pathlib import Path

RATE = 22050
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "game" / "audio"


def write_wave(path, duration, sample):
    count = round(RATE * duration)
    frames = bytearray()
    for index in range(count):
        value = max(-1.0, min(1.0, sample(index, count)))
        frames.extend(struct.pack("<h", round(value * 32767)))
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(RATE)
        audio.writeframes(frames)


def loop_tone(frequencies, amplitude):
    def sample(index, count):
        phase = index / RATE
        return amplitude * sum(math.sin(2 * math.pi * frequency * phase) for frequency in frequencies)

    return sample


def road_noise(count):
    rng = random.Random(17)
    bass = [rng.uniform(-1, 1) for _ in range(128)]
    grit = [rng.uniform(-1, 1) for _ in range(4096)]

    def value(knots, index):
        phase = index * len(knots) / count
        left = int(phase)
        fraction = phase - left
        return knots[left] * (1 - fraction) + knots[(left + 1) % len(knots)] * fraction

    return lambda index, total: 0.28 * (0.45 * value(bass, index) + 0.55 * value(grit, index))


def impact_tone(index, count):
    phase = index / RATE
    envelope = math.sin(math.pi * index / (count - 1)) ** 0.7
    return envelope * 0.32 * math.sin(2 * math.pi * (105 - 65 * index / count) * phase)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--play", action="store_true", help="play the three generated clips")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_wave(OUTPUT / "engine.wav", 1.0, loop_tone((72, 144, 216), 0.12))
    write_wave(OUTPUT / "road.wav", 1.0, road_noise(RATE))
    write_wave(OUTPUT / "impact.wav", 0.24, impact_tone)
    if parser.parse_args().play:
        import winsound

        for name in ("engine.wav", "road.wav", "impact.wav"):
            winsound.PlaySound(str(OUTPUT / name), winsound.SND_FILENAME)


if __name__ == "__main__":
    main()
