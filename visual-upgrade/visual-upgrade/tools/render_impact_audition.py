"""导出分层声音对比与 10 秒擦碰样本；实际游戏混音仍以驾驶试听为准。"""

import argparse
import json
import wave
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "assets" / "game" / "audio"
RATE = 44100


def read_samples(path):
    with wave.open(str(path), "rb") as source:
        assert (source.getnchannels(), source.getsampwidth(), source.getframerate()) == (1, 2, RATE)
        samples = array("h")
        samples.frombytes(source.readframes(source.getnframes()))
        return samples


def save(path, values):
    samples = array("h", (max(-32768, min(32767, round(value))) for value in values))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(samples.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bank = json.loads((AUDIO / "impact-bank.json").read_text(encoding="utf-8"))

    def clip(pool, index):
        entry = bank["pools"][pool][index]
        return read_samples(AUDIO / entry["path"])

    # 与运行时同量级的增益；只比较层次和动态，不对各次撞击分别归一化。
    recipes = [
        ("light", [("transient_metal", 0, .43), ("body_light", 0, .29)]),
        ("medium", [("transient_metal", 1, .58), ("body_heavy", 0, .43),
                    ("crunch", 0, .10)]),
        ("heavy", [("transient_metal", 2, .75), ("body_heavy", 1, .60),
                   ("crunch", 1, .26), ("debris", 0, .12)]),
    ]
    comparison = [0.0] * (RATE * 7)
    for slot, (name, layers) in enumerate(recipes):
        single = [0.0] * RATE
        for pool, variant, gain in layers:
            samples = clip(pool, variant)
            for index, value in enumerate(samples):
                if index >= len(single):
                    break
                single[index] += value * gain
        save(output / f"{name}.wav", single)
        start = round((.25 + slot * 2) * RATE)
        for index, value in enumerate(single):
            comparison[start + index] += value
    save(output / "light-medium-heavy.wav", comparison)

    scrape = clip("scrape_metal", 0)
    loop = [scrape[index % len(scrape)] * .32 for index in range(RATE * 10)]
    fade = round(.07 * RATE)
    for index in range(fade):
        loop[index] *= index / fade
        loop[-index - 1] *= index / fade
    save(output / "metal-scrape-10s.wav", loop)
    print(output)


if __name__ == "__main__":
    main()
