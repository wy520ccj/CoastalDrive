"""对比试听反馈修订前后的PCM与独立包，不把频谱指标当作主观验收。"""

import argparse
import hashlib
import json
import math
import wave
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def pcm(path):
    with wave.open(str(path), "rb") as clip:
        return array("h", clip.readframes(clip.getnframes())), clip.getnchannels(), clip.getframerate()


def music_hiss(path):
    values, channels, _ = pcm(path)
    values = values[::channels]
    energy = sum(x*x for x in values)
    hiss = sum((values[i] - 2*values[i-1] + values[i-2])**2
               for i in range(2, len(values)))
    return hiss / energy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = ROOT / "assets/game/audio"
    previous = args.previous / "assets/game/audio"
    music = []
    for name in ("sunset-run", "midnight-circuit"):
        before = music_hiss(previous / "music" / f"{name}.wav")
        after = music_hiss(root / "music" / f"{name}.wav")
        music.append({"track": name, "before": before, "after": after,
                      "change_db": 10 * math.log10(after / before)})
    bank = json.loads((root / "impact-bank.json").read_text())
    durations = [entry["duration"] for name, entries in bank["pools"].items()
                 if not name.startswith("scrape") for entry in entries]
    identical_scrapes = all(
        (root / entry["path"]).read_bytes() == (previous / entry["path"]).read_bytes()
        for name, entries in bank["pools"].items() if name.startswith("scrape")
        for entry in entries)
    audition = args.output.parent / "audition.wav"
    values, _, _ = pcm(audition)
    peak = max(abs(x) for x in values) / 32768
    saturated = sum(abs(x) >= 32767 for x in values)
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(ROOT)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            packed = args.package / relative
            files.append({"path": relative.as_posix(), "sha256": digest,
                          "same": hashlib.sha256(packed.read_bytes()).hexdigest() == digest})
    passed = (all(m["after"] < .0005 for m in music) and max(durations) <= .36
              and identical_scrapes and saturated == 0 and all(f["same"] for f in files))
    report = {"passed": passed, "music_second_difference_energy_ratio": music,
              "single_impact_samples": len(durations), "max_seconds": max(durations),
              "continuous_contact_scrapes_unchanged": identical_scrapes,
              "audition_peak": peak, "audition_saturated_samples": saturated,
              "package_audio_files": files,
              "kind": "PCM/no-clipping/package evidence; subjective audition pending"}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "package_audio_files"}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
